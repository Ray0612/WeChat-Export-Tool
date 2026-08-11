"""
M34 — Hook FUN_1816f3510 to find where text materializes
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

outfile = r'C:\Users\OK\Desktop\wechat_v4_export\m34_cache.jsonl'
os.makedirs(os.path.dirname(outfile), exist_ok=True)

js = '''
var mod = Process.findModuleByName("Weixin.dll");
var f = mod.base.add(0x016f3510);
var callCount = 0;

send("Hook @ " + f.toString());

Interceptor.attach(f, {
    onEnter: function(args) {
        callCount++;
        if (callCount > 100) return;

        // Try reading all params as string pointers
        var txt = "";
        for (var ai = 0; ai < 4; ai++) {
            if (!args[ai]) continue;
            try {
                var s = args[ai].readUtf8String();
                if (s && s.length > 2 && s.length < 200) {
                    var printable = 0;
                    for (var ci = 0; ci < s.length; ci++) {
                        var cc = s.charCodeAt(ci);
                        if (cc >= 0x20 && cc < 0x7f || cc >= 0x80) printable++;
                    }
                    if (printable > s.length * 0.5) {
                        txt = s;
                        break;
                    }
                }
            } catch(e) {}
        }

        // Read return value (after the call completes)
        this.needRet = true;
        this.callIdx = callCount;

        // Log params
        if (txt) {
            send("PARAM #" + callCount + " a" + ai + ": " + txt.substring(0, 80));
        } else {
            var info = "";
            for (var ai = 0; ai < 4; ai++) {
                try { info += " a" + ai + "=" + (args[ai] ? args[ai].toString() : "null"); } catch(e) {}
            }
            if (callCount <= 10) send("CALL #" + callCount + info);
        }
    },
    onLeave: function(retval) {
        if (!this.needRet) return;
        var idx = this.callIdx;

        if (!retval || retval.isNull()) return;
        var addr = retval;

        // Read the returned object (0x2f0 bytes)
        try {
            var data = addr.readByteArray(0x2f0);
            if (!data) return;
            var bytes = new Uint8Array(data);

            // Search for text in the returned object
            var found = [];
            for (var off = 0; off < 0x2f0 - 8; off++) {
                // Check for pointer to string
                var ptr = 0;
                for (var bi = 0; bi < 8; bi++) ptr += bytes[off+bi] << (bi * 8);
                if (ptr > 0x100000 && ptr < 0x7fffffffffff) {
                    try {
                        var s = ptr(ptr.toString()).readUtf8String();
                        if (s && s.length > 3 && s.length < 500) {
                            var printable = 0;
                            for (var ci = 0; ci < s.length && ci < 30; ci++) {
                                var cc = s.charCodeAt(ci);
                                if (cc >= 0x20 && cc < 0x7f || cc >= 0x80) printable++;
                            }
                            if (printable > 10) {
                                found.push({off: off, text: s.substring(0, 100)});
                            }
                        }
                    } catch(e) {}
                }
            }

            // Check inline UTF8 at key offsets
            for (var off of [0x20, 0x40, 0x80, 0x100, 0x120, 0x140, 0x1c0, 0x200, 0x240, 0x280]) {
                if (off + 4 > 0x2f0) continue;
                try {
                    var s = "";
                    var j = off;
                    while (j < 0x2f0 && bytes[j] >= 0x20 && bytes[j] < 0x7f) {
                        s += String.fromCharCode(bytes[j]);
                        j++;
                    }
                    if (s.length > 3) {
                        found.push({off: off, text: "(inline) " + s.substring(0, 80)});
                    }
                } catch(e) {}
            }

            if (found.length > 0) {
                send("RET #" + idx + " @ " + addr.toString());
                for (var fi = 0; fi < found.length && fi < 5; fi++) {
                    send("  +0x" + found[fi].off.toString(16) + ": " + found[fi].text.substring(0, 80));
                }
            }
        } catch(e) {}
    }
});
send("R");
'''

session = frida.attach(PID)
script = session.create_script(js)
results = []

def on_msg(msg, data):
    if msg['type'] == 'send':
        line = msg['payload']
        print(line, flush=True)
        results.append(line)

script.on('message', on_msg)
script.load()

print(f'M34 PID={PID} — PageUp (60s)', flush=True)
time.sleep(60)
session.detach()

# Count
call_count = sum(1 for l in results if l.startswith('CALL #'))
text_hits = sum(1 for l in results if 'RET #' in l)
print(f'\n=== 结果 ===', flush=True)
print(f'总调用: ~{call_count}', flush=True)
print(f'有文本返回: {text_hits}', flush=True)
print(f'输出: {outfile}', flush=True)
