import frida, psutil, time, os, sys

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

dump_dir = r'C:\Users\OK\Desktop\m14_dumps3'
os.makedirs(dump_dir, exist_ok=True)

# Store dumps in files directly via Frida's file API
# Actually, let's just use send() and write binary files in Python

js = '''
var mod = Process.findModuleByName('Weixin.dll');
Interceptor.attach(mod.base.add(0x01683b08), {
    onEnter: function(args) {
        this.a2 = args[2];
        this.hit = (this.hit || 0) + 1;
        if (!this.a2) return;
        try {
            var data = this.a2.readByteArray(512);
            if (data) {
                var hex = '';
                var bytes = new Uint8Array(data);
                for (var i = 0; i < 512; i++) hex += ('0' + bytes[i].toString(16)).slice(-2);
                send('B ' + this.hit + ' ' + hex);
            }
        } catch(e) {}

        try {
            var p = this.a2.readPointer();
            if (p) send('W ' + this.hit + ' ' + p.readUtf8String().substring(0,50));
        } catch(e) {}
        try { send('CUR ' + this.hit + ' ' + this.a2.add(0x28).readU64()); } catch(e) {}
        try { send('CNT ' + this.hit + ' ' + this.a2.add(0x30).readU32()); } catch(e) {}
    },
    onLeave: function(retval) {
        if (!this.a2) return;
        try {
            var data = this.a2.readByteArray(512);
            if (data) {
                var hex = '';
                var bytes = new Uint8Array(data);
                for (var i = 0; i < 512; i++) hex += ('0' + bytes[i].toString(16)).slice(-2);
                send('A ' + this.hit + ' ' + hex);
            }
        } catch(e) {}
        try { send('CURA ' + this.hit + ' ' + this.a2.add(0x28).readU64()); } catch(e) {}
        try { send('CNTA ' + this.hit + ' ' + this.a2.add(0x30).readU32()); } catch(e) {}
        if (this.hit >= 5) {
            send('STOP');
        }
    }
});
send('R');
'''

session = frida.attach(PID)
script = session.create_script(js)

buf = {}
results = {}

def on_msg(msg, data):
    if msg['type'] == 'send':
        line = msg['payload']
        parts = line.split(' ', 2)
        cmd = parts[0] if len(parts) > 0 else ''
        hit = parts[1] if len(parts) > 1 else '0'

        if cmd == 'B':
            buf[hit] = bytes.fromhex(parts[2])
            with open(os.path.join(dump_dir, f'before_{hit}.bin'), 'wb') as f:
                f.write(buf[hit])
        elif cmd == 'A':
            after = bytes.fromhex(parts[2])
            if hit in buf:
                before = buf[hit]
                # Compute diff
                changes = []
                for i in range(0, 512, 8):
                    b = before[i:i+8]
                    a = after[i:i+8]
                    if b != a:
                        bv = int.from_bytes(b, 'little')
                        av = int.from_bytes(a, 'little')
                        tag = ''
                        if bv == 0 and av > 0x100000000: tag = ' NEW_PTR'
                        elif bv > 0x100000000 and av == 0: tag = ' CLEARED'
                        elif bv > 0x100000000 and av > 0x100000000: tag = ' PTR_CHG'
                        changes.append(f'+0x{i:03x} {b.hex()}->{a.hex()}{tag}')
                results[hit] = changes
                with open(os.path.join(dump_dir, f'after_{hit}.bin'), 'wb') as f:
                    f.write(after)
                # Print immediately
                sys.stdout.write(f'\n=== HIT #{hit} ({len(changes)} changes) ===\n')
                for c in changes:
                    sys.stdout.write(f'  {c}\n')
                sys.stdout.flush()
        elif cmd == 'W':
            sys.stdout.write(f'  wxid={parts[2]}\n')
        elif cmd == 'CUR':
            sys.stdout.write(f'  cursor_before={parts[2]}\n')
        elif cmd == 'CNT':
            sys.stdout.write(f'  counter_before={parts[2]}\n')
        elif cmd == 'CURA':
            sys.stdout.write(f'  cursor_after={parts[2]}\n')
        elif cmd == 'CNTA':
            sys.stdout.write(f'  counter_after={parts[2]}\n')
        elif cmd == 'STOP':
            sys.stdout.write('=== GOT 5 HITS, stopping ===\n')
        elif cmd == 'R':
            sys.stdout.write('READY\n')

        sys.stdout.flush()

script.on('message', on_msg)
script.load()

sys.stdout.write(f'PID={PID} - PageUp 10 times. I will stop after 10s of no activity\n')
sys.stdout.flush()

# Use a loop instead of sleep to keep event loop alive
import select
last_count = len(results)
idle_cycles = 0
while idle_cycles < 20:  # ~10 seconds of inactivity
    time.sleep(0.5)
    if len(results) > last_count:
        last_count = len(results)
        idle_cycles = 0
    else:
        idle_cycles += 1

# Print final summary
sys.stdout.write('\n=== FINAL SUMMARY ===\n')
for hit in sorted(results.keys(), key=int):
    changes = results[hit]
    sys.stdout.write(f'HIT #{hit}: {len(changes)} changes\n')
    for c in changes:
        sys.stdout.write(f'  {c}\n')

session.detach()
