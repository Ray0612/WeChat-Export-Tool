"""
M31 — Exporter Feasibility Prototype
Hook FUN_1816c2a20 → extract content/receiver → export JSONL
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

outfile = r'C:\Users\OK\Desktop\wechat_v4_export\m31_export.jsonl'
os.makedirs(os.path.dirname(outfile), exist_ok=True)

js = '''
var mod = Process.findModuleByName("Weixin.dll");
var f = mod.base.add(0x016c2a20);
var count = 0;

Interceptor.attach(f, {
    onEnter: function(args) {
        var a1 = args[1];
        if (!a1) return;

        // Read as qword array to find structure
        try {
            var data = a1.readByteArray(0x100);
            if (!data) return;
            var bytes = new Uint8Array(data);

            // Look for receiver string at +0x120 area
            // Try offsets around 0x100-0x140 for ASCII strings
            var receiver = "";
            for (var tryOff = 0x80; tryOff < 0x140; tryOff += 1) {
                if (tryOff + 1 >= bytes.length) break;
                if (bytes[tryOff] >= 0x20 && bytes[tryOff] < 0x7f && bytes[tryOff+1] === 0) {
                    // Possible UTF16 string start
                    var s = "";
                    for (var ci = tryOff; ci < tryOff + 64 && ci+1 < bytes.length; ci += 2) {
                        if (bytes[ci] >= 0x20 && bytes[ci] < 0x7f && bytes[ci+1] === 0) {
                            s += String.fromCharCode(bytes[ci]);
                        } else break;
                    }
                    if (s.length >= 4 && (s.indexOf("wxid_") >= 0 || s.indexOf("@chatroom") >= 0 || s.indexOf("filehelper") >= 0)) {
                        receiver = s;
                        break;
                    }
                }
            }

            // Try content pointer at +0x268, +0x288
            var content = "";
            for (var ci = 0; ci < 4; ci++) {
                var coff = ci === 0 ? 0x268 : (ci === 1 ? 0x288 : (ci === 2 ? 0x260 : 0x270));
                if (coff + 8 > bytes.length) continue;
                var ptr = 0;
                for (var bi = 0; bi < 8; bi++) ptr += bytes[coff+bi] << (bi * 8);
                if (ptr > 0x100000 && ptr < 0x7fffffffffff) {
                    try {
                        var cp = ptr(ptr.toString());
                        var str = cp.readUtf8String();
                        if (str && str.length > 0 && str.length < 500) {
                            content = str;
                            break;
                        }
                    } catch(e) {}
                }
            }

            // Also try reading a1 as a pointer to string (for iterator objects)
            if (!receiver && !content) {
                try {
                    var p = a1.readPointer();
                    if (p) {
                        var str = p.readUtf8String();
                        if (str && str.length > 3 && str.length < 200) {
                            // This might be a receiver string
                            if (str.indexOf("wxid_") >= 0 || str.indexOf("@chatroom") >= 0 || str.indexOf("filehelper") >= 0) {
                                receiver = str;
                            } else if (str.length > 4) {
                                content = str;
                            }
                        }
                    }
                } catch(e) {}
            }

            // Export if we found something useful
            if (receiver || content) {
                count++;
                var msg = {
                    idx: count,
                    receiver: receiver,
                    content: content,
                    structAddr: a1.toString()
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
            json_str = line[4:]
            exported.append(json_str)
            try:
                obj = json.loads(json_str)
                print(f'[{obj["idx"]}] {obj["receiver"]}: {obj["content"][:60]}', flush=True)
            except:
                print(line, flush=True)
        elif line != 'R':
            print(line, flush=True)

script.on('message', on_msg)
script.load()

print(f'M31 Prototype PID={PID}', flush=True)
print('在联系人或群聊里按 PageUp 翻页', flush=True)
print('45秒后自动停止', flush=True)

try:
    time.sleep(45)
except:
    pass

session.detach()

# Save to file
with open(outfile, 'w', encoding='utf-8') as f:
    for line in exported:
        f.write(line + '\n')

print(f'\n导出完成: {len(exported)} 条消息 -> {outfile}', flush=True)
if exported:
    real = sum(1 for l in exported if '"content"' in l and '"content": ""' not in l)
    print(f'有内容的消息: {real}/{len(exported)}', flush=True)
