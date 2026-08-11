import frida, psutil, time, os, re, struct, sys

PID = None
for p in sorted(psutil.process_iter(['pid','name']), key=lambda x: x.info['pid']):
    if p.info['name'] != 'Weixin.exe': continue
    try:
        sess = frida.attach(p.info['pid'])
        sc = sess.create_script("send(Process.findModuleByName('Weixin.dll')?'yes':'no');")
        r = []
        def m(msg,d):
            if msg['type']=='send': r.append(msg['payload'])
        sc.on('message', m)
        sc.load()
        time.sleep(0.2)
        sess.detach()
        if r and r[0]=='yes':
            PID = p.info['pid']
            break
    except: pass

dump_dir = r'C:\Users\OK\Desktop\m14_dumps2'
os.makedirs(dump_dir, exist_ok=True)

# Hook script: save BEFORE and AFTER as separate binary files via hex-encoded send()
js = '''
var mod = Process.findModuleByName('Weixin.dll');
var caller1Addr = mod.base.add(0x01683b08);
var hit = 0;

Interceptor.attach(caller1Addr, {
    onEnter: function(args) {
        hit++;
        this.h = hit;
        var a2 = args[2];
        if (!a2) return;

        send('HIT ' + hit);
        this.a2 = a2;

        try {
            var data = a2.readByteArray(512);
            if (data) {
                var hex = '';
                var bytes = new Uint8Array(data);
                for (var i = 0; i < 512; i++) hex += ('0' + bytes[i].toString(16)).slice(-2);
                send('BEFORE ' + hex);
            }
        } catch(e) {
            send('ERR ' + e.toString().substring(0,40));
        }
    },
    onLeave: function(retval) {
        var h = this.h;
        if (!this.a2) return;
        try {
            var data = this.a2.readByteArray(512);
            if (data) {
                var hex = '';
                var bytes = new Uint8Array(data);
                for (var i = 0; i < 512; i++) hex += ('0' + bytes[i].toString(16)).slice(-2);
                send('AFTER ' + hex);
            }
        } catch(e) {
            send('ERR_AFTER ' + e.toString().substring(0,40));
        }
        send('DONE ' + h);
    }
});
send('READY');
'''

session = frida.attach(PID)
script = session.create_script(js)

before_data = {}
after_data = {}

def on_msg(msg, data):
    if msg['type'] == 'send':
        line = msg['payload']
        print(line, flush=True)

        parts = line.split(' ', 1)
        if len(parts) < 1:
            return

        cmd = parts[0]

        if cmd == 'HIT':
            hit_num = int(parts[1]) if len(parts) > 1 else 0
            before_data[hit_num] = None
            after_data[hit_num] = None

        elif cmd == 'BEFORE' and len(parts) == 2:
            hex_data = parts[1]
            # Find the last HIT without BEFORE
            for h in sorted(before_data.keys(), reverse=True):
                if before_data[h] is None:
                    before_data[h] = bytes.fromhex(hex_data)
                    bin_path = os.path.join(dump_dir, f'before_{h:03d}.bin')
                    with open(bin_path, 'wb') as f:
                        f.write(before_data[h])
                    break

        elif cmd == 'AFTER' and len(parts) == 2:
            hex_data = parts[1]
            for h in sorted(after_data.keys(), reverse=True):
                if after_data[h] is None:
                    after_data[h] = bytes.fromhex(hex_data)
                    bin_path = os.path.join(dump_dir, f'after_{h:03d}.bin')
                    with open(bin_path, 'wb') as f:
                        f.write(after_data[h])
                    break

        elif cmd == 'DONE':
            pass  # hit completed

script.on('message', on_msg)
script.load()

print(f'M14 Delta PID={PID} - Press PageUp 10 times (30s)', flush=True)
time.sleep(30)
session.detach()

# Now compute diffs in Python
print('\n=== DIFF RESULTS ===')
for hit_num in sorted(before_data.keys()):
    if hit_num not in after_data:
        continue
    before = before_data[hit_num]
    after = after_data[hit_num]
    if before is None or after is None:
        continue

    changes = []
    for i in range(0, min(len(before), len(after)), 8):
        b_seg = before[i:i+8]
        a_seg = after[i:i+8]
        if b_seg != a_seg:
            b_val = int.from_bytes(b_seg, 'little')
            a_val = int.from_bytes(a_seg, 'little')
            tag = ''
            if b_val == 0 and a_val > 0x100000000:
                tag = '  [NEW_PTR]'
            elif b_val > 0x100000000 and a_val == 0:
                tag = '  [CLEARED]'
            elif b_val > 0x100000000 and a_val > 0x100000000:
                tag = '  [PTR_CHANGED]'
            elif 0 < b_val < 0x1000 and a_val > 0x100000000:
                tag = '  [LEN_TO_PTR]'
            changes.append(f'  +0x{i:03x}: {b_seg.hex()} -> {a_seg.hex()}{tag}')

    if changes:
        print(f'\n--- HIT #{hit_num} ({len(changes)} changes) ---')
        for c in changes:
            print(c)
    else:
        print(f'\n--- HIT #{hit_num} (NO CHANGES) ---')
