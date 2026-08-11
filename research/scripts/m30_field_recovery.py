import frida, psutil, time, os, struct

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

dump_dir = r'C:\Users\OK\Desktop\m30_dumps'
os.makedirs(dump_dir, exist_ok=True)

js = '''
var mod = Process.findModuleByName('Weixin.dll');
var f = mod.base.add(0x016c2a20);
var hit = 0;

Interceptor.attach(f, {
    onEnter: function(args) {
        hit++;
        if (hit > 5) return;
        var a1 = args[1];
        if (!a1) return;

        send('=== HIT#' + hit + ' ===');
        send('a1=' + a1.toString());

        // Try known offsets from Ghidra: +0x30 = start, +0x38 = end
        try {
            var start = a1.add(0x30).readPointer();
            var end = a1.add(0x38).readPointer();
            send('a1+0x30=' + start.toString() + ' a1+0x38=' + end.toString());

            if (start && end && start.toInt32() > 0x100000 && end.toInt32() > 0x100000) {
                var diff = end.sub(start).toInt32();
                if (diff > 0 && diff % 0x2d8 === 0) {
                    var count = diff / 0x2d8;
                    send('VALID ARRAY: ' + count + ' nodes, ' + diff + ' bytes');

                    // Dump first 3 nodes
                    for (var ni = 0; ni < Math.min(count, 3); ni++) {
                        var nodeAddr = start.add(ni * 0x2d8);
                        try {
                            var data = nodeAddr.readByteArray(0x2d8);
                            if (!data) continue;
                            var bytes = new Uint8Array(data);
                            var hex = '';
                            for (var i = 0; i < 0x2d8; i++) hex += ('0' + bytes[i].toString(16)).slice(-2);
                            send('NODE[' + ni + '] @ ' + nodeAddr.toString() + ' ' + hex);
                        } catch(e) {}
                    }
                } else {
                    send('Not a valid array: diff=' + diff);
                }
            }
        } catch(e) {
            send('ERR a1+0x30: ' + e.toString().substring(0,40));
        }

        // Also try a1+0x50 and a1+0x58 (alternative offsets)
        try {
            var s2 = a1.add(0x50).readPointer();
            var e2 = a1.add(0x58).readPointer();
            if (s2 && e2 && s2.toInt32() > 0x100000 && e2.toInt32() > 0x100000) {
                var diff2 = e2.sub(s2).toInt32();
                if (diff2 > 0 && diff2 % 0x2d8 === 0) {
                    send('ALT ARRAY at a1+0x50: ' + (diff2 / 0x2d8) + ' nodes');
                }
            }
        } catch(e) {}

        // Also check a1 itself - read as pointer
        try {
            var p = a1.readPointer();
            if (p) send('a1[0]=' + p.toString());
        } catch(e) {}
    }
});
send('R');
'''

session = frida.attach(PID)
script = session.create_script(js)
dump_idx = [0]

def on_msg(msg, data):
    if msg['type'] == 'send':
        line = msg['payload']
        print(line, flush=True)

        import re
        m = re.match(r'NODE\[(\d+)\] @ (0x[0-9a-f]+) ([0-9a-fA-F]+)', line)
        if m:
            idx = dump_idx[0]
            bin_path = os.path.join(dump_dir, f'node_{idx:03d}.bin')
            with open(bin_path, 'wb') as f:
                f.write(bytes.fromhex(m.group(3)))
            dump_idx[0] += 1

script.on('message', on_msg)
script.load()

print(f'PID={PID} - PageUp a few times', flush=True)
time.sleep(45)
session.detach()
print(f'Dumped {dump_idx[0]} nodes', flush=True)
