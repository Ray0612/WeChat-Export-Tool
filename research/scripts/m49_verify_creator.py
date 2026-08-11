"""
M49 — Verify FUN_181bc3b00 is the 0x2d8 MessageNode Creator
"""
import frida, psutil, time, json, os

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
var creator = mod.base.add(0x01bc3b00);
var count = 0;

send("Creator @ " + creator.toString());

Interceptor.attach(creator, {
    onLeave: function(retval) {
        count++;
        if (count > 10) return;
        var addr = retval;
        if (!addr || addr.isNull()) return;

        send("RET #" + count + " @ " + addr.toString());

        // Read 0x2d8 bytes from returned object
        try {
            var data = addr.readByteArray(0x2d8);
            if (!data) return;
            var bytes = new Uint8Array(data);

            // Check receiver at +0x120
            var receiver = "";
            for (var ri = 0x120; ri < 0x150 && bytes[ri] !== 0; ri++) {
                if (bytes[ri] >= 0x20 && bytes[ri] < 0x7f)
                    receiver += String.fromCharCode(bytes[ri]);
            }

            // Check content at +0x268, +0x288
            var content = "";
            for (var ci = 0; ci < 2; ci++) {
                var coff = ci === 0 ? 0x268 : 0x288;
                var ptr = 0;
                for (var bi = 0; bi < 8; bi++) ptr += bytes[coff+bi] << (bi * 8);
                if (ptr > 0x100000 && ptr < 0x7fffffffffff) {
                    try {
                        var s = ptr(ptr.toString()).readUtf8String();
                        if (s && s.length > 0 && s.length < 500) {
                            content = s;
                            break;
                        }
                    } catch(e) {}
                }
            }

            // Check for wxid, filehelper, @chatroom anywhere in struct
            var wxid = "";
            for (var off = 0; off < 0x2d8 - 5; off++) {
                if (bytes[off] === 0x77 && bytes[off+1] === 0x78 &&
                    bytes[off+2] === 0x69 && bytes[off+3] === 0x64) {  // "wxid"
                    var end = off;
                    while (end < 0x2d8 && bytes[end] >= 0x20 && bytes[end] < 0x7f) end++;
                    wxid = "";
                    for (var w = off; w < end; w++) wxid += String.fromCharCode(bytes[w]);
                    break;
                }
            }

            var info = {idx: count, addr: addr.toString(), receiver: receiver, content: content.substring(0, 80), wxid: wxid};
            send("NODE " + JSON.stringify(info));
        } catch(e) {
            send("ERR: " + e.toString().substring(0, 40));
        }
    }
});
send("R");
'''

script = session.create_script(js)
script.on('message', lambda msg,d: print(msg['payload'], flush=True) if msg['type']=='send' else None)
script.load()

print('PID=' + str(PID) + ' - 翻页或切换会话触发 Creator', flush=True)
time.sleep(45)
session.detach()
print('Done.', flush=True)
