"""
M32 — Immediate read within hook callback
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

outfile = r'C:\Users\OK\Desktop\wechat_v4_export\m32_immediate.jsonl'
os.makedirs(os.path.dirname(outfile), exist_ok=True)

js = '''
var mod = Process.findModuleByName("Weixin.dll");
var loopBody = mod.base.add(0x016c2a76);
var seen = {};
var exported = 0;

send("Hook @ " + loopBody.toString());

Interceptor.attach(loopBody, {
    onEnter: function(args) {
        var r14 = this.context.r14;
        if (!r14) return;

        try {
            var data = r14.readByteArray(0x2d8);
            if (!data) return;
            var bytes = new Uint8Array(data);

            // Read receiver at +0x120
            var receiver = "";
            for (var ri = 0x120; ri < 0x150 && bytes[ri] !== 0; ri++) {
                if (bytes[ri] >= 0x20 && bytes[ri] < 0x7f || bytes[ri] >= 0x80)
                    receiver += String.fromCharCode(bytes[ri]);
            }

            // Try content at known pointer offsets
            var content = "";
            var contentOff = 0;
            var tries = [0x268, 0x288, 0x260, 0x270, 0x258, 0x278, 0x250, 0x280, 0x248, 0x290];
            for (var ti = 0; ti < tries.length && !content; ti++) {
                var off = tries[ti];
                var ptr = 0;
                for (var bi = 0; bi < 8; bi++) ptr += bytes[off+bi] << (bi * 8);
                if (ptr > 0x100000 && ptr < 0x7fffffffffff) {
                    try {
                        var cp = ptr(ptr.toString());
                        var str = cp.readUtf8String();
                        if (str && str.length > 1 && str.length < 1000) {
                            content = str;
                            contentOff = off;
                        }
                    } catch(e) {}
                }
            }

            // Fallback: inline text at +0x20..+0x2c0
            if (!content) {
                for (var off = 0x20; off < 0x2c0; off++) {
                    if (bytes[off] >= 0x20 && bytes[off] < 0x7f) {
                        var s = "";
                        var j = off;
                        while (j < 0x2c0 && bytes[j] >= 0x20 && bytes[j] < 0x7f) {
                            s += String.fromCharCode(bytes[j]);
                            j++;
                        }
                        if (s.length >= 5) {
                            content = s.substring(0, 200);
                            contentOff = off;
                            break;
                        }
                        off = j;
                    }
                }
            }

            // Dedup by content
            var sig = receiver + "|" + (content ? content.substring(0, 30) : "");
            if (!content && !receiver) return;
            if (seen[sig]) return;
            seen[sig] = true;

            exported++;
            var msg = {
                idx: exported,
                receiver: receiver,
                content: content ? content.substring(0, 500) : "",
                contentOffset: contentOff,
                structAddr: r14.toString()
            };
            send("MSG " + JSON.stringify(msg));

            // Stop after enough data
            if (exported >= 200) {
                send("DONE");
                Interceptor.detachAll();
            }
        } catch(e) {}
    }
});
send("R");
'''

session = frida.attach(PID)
script = session.create_script(js)
exported = []

def on_msg(msg, data):
    if msg['type'] == 'send':
        line = msg['payload']
        if line.startswith('MSG '):
            exported.append(line[4:])
            try:
                o = json.loads(line[4:])
                c = o.get('content', '')[:60]
                r = o.get('receiver', '')
                print(f'[{o["idx"]}] {r}: {c}', flush=True)
            except:
                pass
        elif line != 'R':
            print(line, flush=True)

script.on('message', on_msg)
script.load()

print(f'M32 Immediate PID={PID} — PageUp (90s)', flush=True)
try:
    time.sleep(90)
except:
    pass

session.detach()

with open(outfile, 'w', encoding='utf-8') as f:
    for line in exported:
        f.write(line + '\n')

with_content = 0
for l in exported:
    try:
        o = json.loads(l)
        if o.get('content'):
            with_content += 1
    except:
        pass

print(f'\n=== 结果 ===', flush=True)
print(f'总条数: {len(exported)}', flush=True)
print(f'有内容: {with_content}', flush=True)
print(f'输出: {outfile}', flush=True)
