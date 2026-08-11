import frida, psutil, time, os, re, hashlib

logfile = r'C:\Users\OK\Desktop\m7_diff.txt'
dump_dir = r'C:\Users\OK\Desktop\m7_dumps'
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
            var arg1 = args[1];
            if (!arg1) return;

            this.hitNum = hitCount;
            this.arg1 = arg1;
            this.arg2 = args[2];

            send('[ENTER #' + hitCount + '] arg1=' + arg1.toString());

            // Dump arg1 0x400 bytes as before
            try {
                var data = arg1.readByteArray(1024);
                if (data) {
                    var hex = '';
                    var bytes = new Uint8Array(data);
                    for (var i = 0; i < 1024; i++) {
                        hex += ('0' + bytes[i].toString(16)).slice(-2);
                    }
                    send('[BEFORE #' + hitCount + '] ' + hex);
                }
            } catch(e) {
                send('[BEFORE_ERR #' + hitCount + '] ' + e.toString());
            }

            // Dump arg2 PagingContext header too for reference
            if (args[2]) {
                try {
                    var data2 = args[2].readByteArray(64);
                    if (data2) {
                        var hex2 = '';
                        var bytes2 = new Uint8Array(data2);
                        for (var i = 0; i < 64; i++) {
                            hex2 += ('0' + bytes2[i].toString(16)).slice(-2);
                        }
                        send('[ARG2 #' + hitCount + '] ' + hex2);
                    }
                } catch(e) {}
            }
        },
        onLeave: function(retval) {
            var arg1 = this.arg1;
            if (!arg1) return;

            send('[LEAVE #' + this.hitNum + '] retval=' + (retval ? retval.toString() : 'null'));

            // Dump arg1 0x400 bytes as after
            try {
                var data = arg1.readByteArray(1024);
                if (data) {
                    var hex = '';
                    var bytes = new Uint8Array(data);
                    for (var i = 0; i < 1024; i++) {
                        hex += ('0' + bytes[i].toString(16)).slice(-2);
                    }
                    send('[AFTER #' + this.hitNum + '] ' + hex);
                }
            } catch(e) {
                send('[AFTER_ERR #' + this.hitNum + '] ' + e.toString());
            }

            // Also dump cursor from arg2
            if (this.arg2) {
                try {
                    var cursor = this.arg2.add(0x28).readU64();
                    var wxidPtr = this.arg2.readPointer();
                    var wxidStr = '?';
                    try { wxidStr = wxidPtr.readUtf8String(); } catch(e) {}
                    send('[CURSOR #' + this.hitNum + '] wxid=' + wxidStr + ' cursor=' + cursor.toString());
                } catch(e) {}
            }

            // Check if retval is same as arg1 (verification from M6)
            if (retval && retval.toString() === arg1.toString()) {
                send('[VERIFY #' + this.hitNum + '] retval==arg1 confirmed');
            }
        }
    });
    send('### M7 GC Diff Hook ready ###');
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

# Store before/after data for diff
before_data = {}
after_data = {}

def on_msg(msg, data):
    global before_data, after_data
    if msg['type'] == 'send':
        line = msg['payload']
        with open(logfile, 'a', encoding='utf-8') as f:
            f.write(line + '\n')

        # Parse BEFORE/AFTER hex data
        m_before = re.match(r'\[BEFORE #(\d+)\]\s+([0-9a-fA-F]+)', line)
        m_after = re.match(r'\[AFTER #(\d+)\]\s+([0-9a-fA-F]+)', line)

        if m_before:
            hit = int(m_before.group(1))
            before_data[hit] = m_before.group(2)
            # Also save binary
            bin_path = os.path.join(dump_dir, f'before_{hit:03d}.bin')
            with open(bin_path, 'wb') as f:
                f.write(bytes.fromhex(m_before.group(2)))

        if m_after:
            hit = int(m_after.group(1))
            after_data[hit] = m_after.group(2)
            # Also save binary
            bin_path = os.path.join(dump_dir, f'after_{hit:03d}.bin')
            with open(bin_path, 'wb') as f:
                f.write(bytes.fromhex(m_after.group(2)))

            # If we have both before and after for this hit, compute diff
            if hit in before_data:
                compute_diff(hit, before_data[hit], after_data[hit])

        print(line)
    elif msg['type'] == 'error':
        err_line = 'ERR: ' + str(msg)
        with open(logfile, 'a', encoding='utf-8') as f:
            f.write(err_line + '\n')
        print(err_line)

def compute_diff(hit, before_hex, after_hex):
    """Compare before and after byte-by-byte, report differences."""
    before_bytes = bytes.fromhex(before_hex[:2048])  # 1024 bytes
    after_bytes = bytes.fromhex(after_hex[:2048])

    changes = []
    for i in range(0, len(before_bytes), 8):
        b_seg = before_bytes[i:i+8]
        a_seg = after_bytes[i:i+8]
        if b_seg != a_seg:
            # Check if it's a pointer change (8 bytes that look like addresses)
            b_val = int.from_bytes(b_seg, 'little')
            a_val = int.from_bytes(a_seg, 'little')
            changes.append((i, b_seg.hex(), a_seg.hex(), b_val, a_val))

    if changes:
        diff_path = os.path.join(dump_dir, f'diff_{hit:03d}.txt')
        with open(diff_path, 'w') as f:
            f.write(f'=== HIT #{hit} diff ===\n')
            f.write(f'Changes: {len(changes)} segments\n\n')
            for offset, b_hex, a_hex, b_val, a_val in changes:
                tag = ''
                if b_val == 0 and a_val > 0x100000000:
                    tag = ' [NEW_PTR]'
                elif a_val == 0 and b_val > 0x100000000:
                    tag = ' [CLEARED]'
                elif b_val > 0x100000000 and a_val > 0x100000000 and b_val != a_val:
                    tag = f' [PTR_CHANGED: {hex(b_val)} → {hex(a_val)}]'
                elif b_val == 0 and a_val == 1:
                    tag = ' [SET_TRUE]'
                elif b_val == 1 and a_val == 0:
                    tag = ' [SET_FALSE]'
                f.write(f'  +0x{offset:03x}: {b_hex} → {a_hex}{tag}\n')

        # Log to main log too
        with open(logfile, 'a', encoding='utf-8') as f:
            f.write(f'[DIFF #{hit}] {len(changes)} changed segments (see {diff_path})\n')

        # Print summary
        print(f'  >>> DIFF #{hit}: {len(changes)} changed segments')

        # If a new pointer appeared, try to dump it
        for offset, b_hex, a_hex, b_val, a_val in changes:
            if b_val == 0 and a_val > 0x100000000:
                print(f'  >>> NEW_PTR at +0x{offset:03x}: {hex(a_val)}')

script.on('message', on_msg)
script.load()

print('=' * 60)
print('M7: Global Context Differential Analysis')
print('=' * 60)
print(f'PID: {pid}')
print(f'Log: {logfile}')
print(f'Dumps: {dump_dir}')
print()
print('实验流程:')
print('  Task 2-3: 同一会话翻页 10 次')
print('  Task 4:   切换联系人翻页 10 次')
print('  Task 5:   群聊翻页 10 次')
print()
print('请按物理 PageUp 键翻页')
print('Ctrl+C 停止')
print('=' * 60)

try:
    time.sleep(99999)
except:
    pass
session.detach()
