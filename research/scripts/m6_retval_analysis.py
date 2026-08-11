import frida, psutil, time, os, re

logfile = r'C:\Users\OK\Desktop\m6_retval.txt'
dump_dir = r'C:\Users\OK\Desktop\m6_dumps'
os.makedirs(dump_dir, exist_ok=True)
open(logfile, 'w').close()

jscode = r'''
'use strict';

var mod = Process.findModuleByName('Weixin.dll');
if (!mod) {
    send('ERROR: Weixin.dll not found');
} else {
    var funcAddr = mod.base.add(0x016ade70);
    var hitCount = 0;

    Interceptor.attach(funcAddr, {
        onEnter: function(args) {
            hitCount++;
            var a0 = args[0] ? args[0].toString() : 'null';
            var a1 = args[1] ? args[1].toString() : 'null';
            var a2 = args[2] ? args[2].toString() : 'null';
            var a3 = args[3] ? args[3].toString() : 'null';
            this.hitNum = hitCount;
            this.arg2 = args[2];
            this.arg2Str = a2;
            send('[ENTER #' + hitCount + ']'
                + ' arg0=' + a0
                + ' arg1=' + a1
                + ' arg2=' + a2
                + ' arg3=' + a3
            );

            // Dump arg2 PagingContext header (first 64 bytes)
            if (args[2]) {
                try {
                    var data = args[2].readByteArray(64);
                    if (data) {
                        var hex = '';
                        var bytes = new Uint8Array(data);
                        for (var i = 0; i < 64; i++) {
                            hex += ('0' + bytes[i].toString(16)).slice(-2);
                        }
                        send('[ARG2_HEX #' + hitCount + '] ' + hex);
                    }
                } catch(e) {
                    send('[ARG2_ERR #' + hitCount + '] ' + e.toString());
                }

                // Read wxid string at arg2+0x000
                try {
                    var wxidPtr = args[2].readPointer();
                    if (wxidPtr) {
                        var wxidStr = wxidPtr.readUtf8String();
                        send('[ARG2_WXID #' + hitCount + '] wxid=' + wxidStr);
                    }
                } catch(e) {
                    send('[ARG2_WXID_ERR #' + hitCount + '] ' + e.toString());
                }

                // Read cursor at arg2+0x028 (8 bytes)
                try {
                    var cursor = args[2].add(0x28).readU64();
                    send('[ARG2_CURSOR #' + hitCount + '] +0x28=' + cursor.toString());
                } catch(e) {}

                // Read counter at arg2+0x030 (4 bytes)
                try {
                    var counter = args[2].add(0x30).readU32();
                    send('[ARG2_COUNTER #' + hitCount + '] +0x30=' + counter.toString());
                } catch(e) {}
            }
        },
        onLeave: function(retval) {
            var rv = retval ? retval.toString() : 'null';
            send('[LEAVE #' + this.hitNum + '] retval=' + rv);

            if (!retval) return;

            // Check numeric value
            var rvNum = parseInt(rv);
            send('[RETVAL_TYPE #' + this.hitNum + '] as_int=' + rvNum);

            // If retval looks like a pointer (> 4GB range), dump memory
            if (rvNum > 0x100000000) {
                send('[RETVAL_CLASS #' + this.hitNum + '] LIKELY_POINTER');
                try {
                    var data = retval.readByteArray(512);
                    if (data) {
                        var hex = '';
                        var bytes = new Uint8Array(data);
                        for (var i = 0; i < 512; i++) {
                            hex += ('0' + bytes[i].toString(16)).slice(-2);
                        }
                        send('[DUMP_RET #' + this.hitNum + '] ' + hex);

                        // Also try to read first pointer in retval
                        try {
                            var innerPtr = retval.readPointer();
                            if (innerPtr) {
                                send('[RETVAL_INNER_PTR #' + this.hitNum + '] ' + innerPtr.toString());
                            }
                        } catch(e) {}
                    }
                } catch(e) {
                    send('[DUMP_ERR #' + this.hitNum + '] ' + e.toString());
                }
            } else if (rvNum < 0x100) {
                // Small value = likely status code or count
                send('[RETVAL_CLASS #' + this.hitNum + '] LIKELY_STATUS/COUNT');
            } else {
                send('[RETVAL_CLASS #' + this.hitNum + '] LIKELY_HANDLE/SMALL_PTR');
            }

            // Read cursor change on leave (compare with onEnter)
            if (this.arg2) {
                try {
                    var cursor = this.arg2.add(0x28).readU64();
                    send('[CURSOR_LEAVE #' + this.hitNum + '] +0x28=' + cursor.toString());
                } catch(e) {}
            }
        }
    });
    send('### M6 Hook ready. retval + arg2 analysis ###');
}
'''

# Find earliest Weixin.exe process
procs = [p for p in psutil.process_iter(['pid','name','create_time']) if p.info['name'] == 'Weixin.exe']
if not procs:
    print("Weixin.exe not running")
    exit(1)
procs.sort(key=lambda x: x.info['create_time'])
pid = procs[0].info['pid']

session = frida.attach(pid)
script = session.create_script(jscode)
dump_count = [0]

def on_msg(msg, data):
    if msg['type'] == 'send':
        line = msg['payload']
        with open(logfile, 'a', encoding='utf-8') as f:
            f.write(line + '\n')

        # Save dump binary
        if line.startswith('[DUMP_RET'):
            m = re.search(r'\]\s*([0-9a-fA-F]+)', line)
            if m:
                hex_data = m.group(1)
                bin_path = os.path.join(dump_dir, f'ret_{dump_count[0]:03d}.bin')
                with open(bin_path, 'wb') as f:
                    f.write(bytes.fromhex(hex_data))
                dump_count[0] += 1

        print(line)
    elif msg['type'] == 'error':
        err_line = 'ERR: ' + str(msg)
        with open(logfile, 'a', encoding='utf-8') as f:
            f.write(err_line + '\n')
        print(err_line)

script.on('message', on_msg)
script.load()

print('=' * 60)
print('M6: GetPagedMessages Return Value Analysis')
print('=' * 60)
print(f'PID: {pid}')
print(f'Log: {logfile}')
print(f'Dumps: {dump_dir}')
print()
print('实验流程:')
print('  Task 2: 同一会话翻页 10 次 (先在文件传输助手翻页)')
print('  Task 3: 切换联系人翻页 10 次 (切换到另一个联系人翻页)')
print('  Task 4: 群聊翻页 10 次 (切换到群聊翻页)')
print()
print('请按物理 PageUp 键翻页')
print('Ctrl+C 停止')
print('=' * 60)

try:
    time.sleep(99999)
except:
    pass
session.detach()
