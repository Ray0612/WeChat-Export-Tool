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

js = '''
var mod = Process.findModuleByName('Weixin.dll');
var f = mod.base.add(0x016c2a20);
var hit = 0;

Interceptor.attach(f, {
    onEnter: function(args) {
        hit++;
        if (hit > 3) return;
        var a1 = args[1];
        if (!a1) return;
        send('=== HIT#' + hit + ' a1=' + a1.toString() + ' ===');

        // Scan a1 for pointer pairs (start/end) with diff divisible by 0x2d8
        try {
            for (var off = 0; off < 0x200; off += 8) {
                var p1 = a1.add(off).readPointer();
                if (!p1 || p1.isNull()) continue;
                var p1v = p1.toInt32();
                if (p1v < 0x100000 || p1v > 0x7fffffff) continue;

                for (var off2 = off + 8; off2 < 0x200; off2 += 8) {
                    var p2 = a1.add(off2).readPointer();
                    if (!p2 || p2.isNull()) continue;
                    var p2v = p2.toInt32();
                    if (p2v < 0x100000 || p2v > 0x7fffffff) continue;

                    var diff = p2v - p1v;
                    if (diff > 0 && diff % 0x2d8 === 0 && diff / 0x2d8 <= 60) {
                        var count = diff / 0x2d8;
                        send('  ARRAY? a1+' + off.toString(16) + '..+' + off2.toString(16) + ': 0x' + p1v.toString(16) + '..0x' + p2v.toString(16) + ' (' + count + ' nodes, ' + diff + ' bytes)');

                        // Dump first 3 nodes
                        for (var ni = 0; ni < Math.min(count, 3); ni++) {
                            var nodeAddr = p1.add(ni * 0x2d8);
                            try {
                                var nd = nodeAddr.readByteArray(0x2d8);
                                if (!nd) continue;
                                var bytes = new Uint8Array(nd);

                                // Read receiver at +0x120
                                var recv = '';
                                for (var ri = 0x120; ri < 0x150 && bytes[ri] !== 0; ri++) {
                                    if (bytes[ri] >= 0x20 && bytes[ri] < 0x7f) recv += String.fromCharCode(bytes[ri]);
                                }

                                // Read content ptr at +0x268, +0x288
                                var content = '';
                                for (var ci = 0; ci < 2; ci++) {
                                    var coff = ci === 0 ? 0x268 : 0x288;
                                    var ptr = 0;
                                    for (var bi = 0; bi < 8; bi++) ptr += bytes[coff+bi] << (bi * 8);
                                    if (ptr > 0x100000 && ptr < 0x7fffffff) {
                                        try {
                                            var cp = ptr(ptr.toString());
                                            var str = cp.readUtf8String();
                                            if (str && str.length > 1 && str.length < 500) {
                                                content = str;
                                                break;
                                            }
                                        } catch(e) {}
                                    }
                                }

                                send('    NODE[' + ni + '] @ 0x' + nodeAddr.toString() + ' recv="' + recv + '" content="' + content.substring(0, 60) + '"');
                            } catch(e) {}
                        }
                    }
                }
            }
        } catch(e) {
            send('  ERR: ' + e.toString().substring(0,60));
        }
    }
});
send('R');
'''

session = frida.attach(PID)
script = session.create_script(js)
script.on('message', lambda msg, d: print(msg['payload'], flush=True) if msg['type']=='send' else None)
script.load()

print(f'PID={PID} - PageUp a few times', flush=True)
time.sleep(45)
session.detach()
print('Done.', flush=True)
