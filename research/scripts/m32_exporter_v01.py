"""
M32 — Exporter PoC v0.1
Hooks Caller1 + FUN_1816c2a20 loop to capture messages
"""
import frida, psutil, time, json, os, datetime

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

outfile = r'C:\Users\OK\Desktop\wechat_v4_export\m32_export.jsonl'
os.makedirs(os.path.dirname(outfile), exist_ok=True)

js = '''
var mod = Process.findModuleByName("Weixin.dll");
var caller1 = mod.base.add(0x01683b08);
var loopBody = mod.base.add(0x016c2a76);
var pageCount = 0;
var msgCount = 0;
var currentReceiver = "";

// Track known message signatures to avoid duplicates
var seenContents = {};

// Hook 1: Caller1 for PagingContext
Interceptor.attach(caller1, {
    onEnter: function(args) {
        pageCount++;
        currentReceiver = "";
        try {
            var a2 = args[2];
            if (a2) {
                var wxidPtr = a2.readPointer();
                if (wxidPtr) {
                    var str = wxidPtr.readUtf8String();
                    if (str) currentReceiver = str.substring(0, 64);
                }
                var cursor = a2.add(0x28).readU64();
                var counter = a2.add(0x30).readU32();
                send("[PAGE #" + pageCount + "] recv=" + currentReceiver + " cursor=" + cursor + " cnt=" + counter);
            }
        } catch(e) {}
    }
});

// Hook 2: Loop body for 0x2d8 MessageNode
Interceptor.attach(loopBody, {
    onEnter: function(args) {
        var r14 = this.context.r14;
        if (!r14) return;

        try {
            var data = r14.readByteArray(0x2d8);
            if (!data) return;
            var bytes = new Uint8Array(data);

            // Try receiver at +0x120
            var receiver = "";
            for (var ri = 0x120; ri < 0x150 && bytes[ri] !== 0; ri++) {
                if (bytes[ri] >= 0x20 && bytes[ri] < 0x7f)
                    receiver += String.fromCharCode(bytes[ri]);
            }
            if (!receiver) receiver = currentReceiver;

            // Content: try ptr at +0x268, +0x288, +0x260, +0x270
            var content = "";
            var foundAt = 0;
            for (var ci = 0; ci < 4 && !content; ci++) {
                var tries = [[0x268, 0x288], [0x260, 0x270], [0x258, 0x278], [0x250, 0x280]];
                for (var ti = 0; ti < tries.length && !content; ti++) {
                    var coff = tries[ti][ci < 2 ? 0 : 1];
                    if (coff === undefined) continue;
                    var ptr = 0;
                    for (var bi = 0; bi < 8; bi++) ptr += bytes[coff+bi] << (bi * 8);
                    if (ptr > 0x100000 && ptr < 0x7fffffffffff) {
                        try {
                            var str = ptr(ptr.toString()).readUtf8String();
                            if (str && str.length > 0 && str.length < 500) {
                                content = str;
                                foundAt = coff;
                            }
                        } catch(e) {}
                    }
                }
            }

            // Also try reading inline text at various offsets
            if (!content) {
                for (var off = 0x20; off < 0x2c0; off++) {
                    if (bytes[off] >= 0x20 && bytes[off] < 0x7f) {
                        var s = "";
                        var j = off;
                        while (j < 0x2d8 && bytes[j] >= 0x20 && bytes[j] < 0x7f) {
                            s += String.fromCharCode(bytes[j]);
                            j++;
                        }
                        if (s.length >= 6 && (s.indexOf(" ") >= 0 || s.indexOf("?") >= 0 || s.indexOf(".") >= 0 || s.indexOf("!") >= 0)) {
                            content = s.substring(0, 200);
                            foundAt = off;
                            break;
                        }
                        off = j;
                    }
                }
            }

            // Deduplicate
            var sig = receiver + "|" + (content ? content.substring(0, 40) : "");
            if (content && !seenContents[sig]) {
                seenContents[sig] = true;
                msgCount++;
                var msg = {
                    idx: msgCount,
                    receiver: receiver,
                    content: content.substring(0, 500),
                    contentOffset: foundAt,
                    structAddr: r14.toString()
                };
                send("MSG " + JSON.stringify(msg));
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
        else:
            print(line, flush=True)

script.on('message', on_msg)
script.load()

print(f'M32 PoC PID={PID}', flush=True)
print('在联系人聊天里翻页 (60s)', flush=True)

try:
    time.sleep(60)
except:
    pass

session.detach()

with open(outfile, 'w', encoding='utf-8') as f:
    for line in exported:
        f.write(line + '\n')

print(f'\n=== 结果 ===', flush=True)
print(f'翻页次数: {exported.count("PAGE") if False else "?"}', flush=True)
print(f'消息条数: {len(exported)}', flush=True)

# Stats
if exported:
    with_content = 0
    for l in exported:
        try:
            o = json.loads(l)
            if o.get('content'):
                with_content += 1
        except:
            pass
    print(f'有内容: {with_content}/{len(exported)}', flush=True)

print(f'输出: {outfile}', flush=True)
