import frida, psutil, time

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

session = frida.attach(PID)

js = '''
var mod = Process.findModuleByName("Weixin.dll");
var f = mod.base.add(0x016c2a20);
var once = false;

Interceptor.attach(f, {
    onEnter: function(args) {
        if (once) return;
        once = true;
        var a1 = args[1];
        if (!a1) return;

        // Dump hex
        try {
            var data = a1.readByteArray(0x200);
            if (data) {
                var hex = "";
                var bytes = new Uint8Array(data);
                for (var i = 0; i < 0x200; i++) {
                    hex += ("0" + bytes[i].toString(16)).slice(-2);
                }
                send("HEX " + hex);
            }
        } catch(e) {}

        // Find begin/end pairs
        for (var off = 0; off < 0x1f8; off += 8) {
            try {
                var v1 = a1.add(off).readU64();
                var v2 = a1.add(off + 8).readU64();
                if (v1 > 0x100000 && v2 > v1) {
                    var diff = v2 - v1;
                    if (diff > 0 && diff % 0x2d8 === 0) {
                        var cnt = diff / 0x2d8;
                        send("PAIR +" + off.toString(16) + ": 0x" + v1.toString(16) + " - 0x" + v2.toString(16) + " (" + cnt + " nodes)");
                    }
                }
            } catch(e) {}
        }
    }
});
send("R");
'''

script = session.create_script(js)
lines = []
script.on('message', lambda msg,d: lines.append(msg['payload']) if msg['type']=='send' else None)
script.load()
print('PageUp once...', flush=True)
time.sleep(20)
session.detach()

# Analyze
hex_line = [l for l in lines if l.startswith('HEX ')][0] if any(l.startswith('HEX ') for l in lines) else None
pair_lines = [l for l in lines if l.startswith('PAIR')]

print('\nPairs found:')
for l in pair_lines:
    print(l, flush=True)

if hex_line:
    hex_data = hex_line.split(' ', 1)[1]
    data = bytes.fromhex(hex_data)
    print('\nKey qwords:')
    for off in range(0, min(len(data), 0x200), 8):
        val = int.from_bytes(data[off:off+8], 'little')
        if val > 0x100000 and val < 0x7fffffffffff:
            print(f'  +{off:03x}: 0x{val:016x}', flush=True)

print('\nDone.', flush=True)
