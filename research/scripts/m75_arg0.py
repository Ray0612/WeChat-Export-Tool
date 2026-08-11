import frida, psutil, time, os, re

logfile = r'C:\Users\OK\Desktop\m75_arg0.txt'
dump_dir = r'C:\Users\OK\Desktop\m75_dumps'
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
            var arg0 = args[0];
            var arg1 = args[1];
            if (!arg0 || !arg1) return;

            this.hitNum = hitCount;
            this.arg0 = arg0;
            this.arg1 = arg1;

            send('=== HIT #' + hitCount + ' ===');
            send('arg0=' + arg0.toString());
            send('arg1=' + arg1.toString());

            // --- Task 1: Dump arg0 0x1000 bytes ---
            try {
                var data = arg0.readByteArray(4096);
                if (data) {
                    var hex = '';
                    var bytes = new Uint8Array(data);
                    for (var i = 0; i < 4096; i++) {
                        hex += ('0' + bytes[i].toString(16)).slice(-2);
                    }
                    send('[ARG0_HEX] ' + hex);
                }
            } catch(e) {
                send('[ARG0_ERR] ' + e.toString());
            }

            // --- Task 2: Walk first 64 pointers (8-byte steps) within arg0 ---
            // Read as qword array
            try {
                for (var i = 0; i < 64; i++) {
                    var off = i * 8;
                    try {
                        var val = arg0.add(off).readU64();
                        var valStr = val.toString();
                        var info = '';

                        // Check if val looks like a pointer
                        if (val > 0x100000000) {
                            var ptr = ptr(valStr);
                            // Try to read a string
                            try {
                                var str = ptr.readUtf8String();
                                if (str && str.length > 2 && str.length < 200) {
                                    info = ' STR="' + str.substring(0, 80) + '"';
                                }
                            } catch(e) {}

                            // If no string, maybe it's another pointer (vtable?)
                            if (!info) {
                                try {
                                    var innerPtr = ptr.readPointer();
                                    if (innerPtr) {
                                        info = ' [inner_ptr=' + innerPtr.toString() + ']';
                                    }
                                } catch(e) {}
                            }
                        }

                        if (val !== 0 || info) {
                            send('[QWORD+' + ('0x' + off.toString(16)) + '] ' + valStr + info);
                        }
                    } catch(e) {
                        // skip unreadable offsets
                    }
                }
            } catch(e) {
                send('[WALK_ERR] ' + e.toString());
            }
        },
        onLeave: function(retval) {
            send('[LEAVE #' + this.hitNum + ']');
        }
    });
    send('### M7.5 arg0 exploration ready ###');
}
'''

procs = [p for p in psutil.process_iter(['pid','name','create_time']) if p.info['name'] == 'Weixin.exe']
if not procs:
    print("Weixin.exe not running")
    exit(1)
procs.sort(key=lambda x: x.info['create_time'])
pid = procs[0].info['pid']
session = frida.attach(pid)
script = session.create_script(jscode)
dump_idx = [0]

def on_msg(msg, data):
    if msg['type'] == 'send':
        line = msg['payload']
        with open(logfile, 'a', encoding='utf-8') as f:
            f.write(line + '\n')

        if line.startswith('[ARG0_HEX]'):
            m = re.match(r'\[ARG0_HEX\]\s+([0-9a-fA-F]+)', line)
            if m:
                idx = dump_idx[0]
                bin_path = os.path.join(dump_dir, f'arg0_{idx:03d}.bin')
                with open(bin_path, 'wb') as f:
                    f.write(bytes.fromhex(m.group(1)))
                dump_idx[0] += 1

        print(line)
    elif msg['type'] == 'error':
        print('ERR:', str(msg))

script.on('message', on_msg)
script.load()

print('=' * 60)
print('M7.5: arg0 (MessageList Manager) Exploration')
print('=' * 60)
print(f'PID: {pid}')
print(f'Log: {logfile}')
print(f'Dumps: {dump_dir}')
print()
print('翻几次页，然后切换联系人再翻页')
print('Ctrl+C 停止')
print('=' * 60)

try:
    time.sleep(99999)
except:
    pass
session.detach()
