"""
M31 v2 — Hook FUN_1816c2a20 循环体内 R14 (MessageNode 指针)
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

# The loop body in FUN_1816c2a20 processes each 0x2d8 node.
# Ghidra shows loop starts at 0x1816c2a76 (LAB).
# R14 already points to the current 0x2d8 element.
# DLL offset of 0x1816c2a76 = 0x016c2a76

LOOP_ADDR = 0x016c2a76  # Where R14 = current 0x2d8 element

js = '''
var mod = Process.findModuleByName("Weixin.dll");
var loopAddr = mod.base.add(0x016c2a76);
var count = 0;
var pageMsgCount = 0;

send("Loop hook @ " + loopAddr.toString());

Interceptor.attach(loopAddr, {
    onEnter: function(args) {
        // R14 should point to current 0x2d8 element
        var r14 = this.context.r14;
        if (!r14) return;

        count++;
        if (count > 200) return;  // limit

        // Read 0x2d8 from R14
        try {
            var data = r14.readByteArray(0x2d8);
            if (!data) return;
            var bytes = new Uint8Array(data);

            // Receiver at +0x120 (inline ASCII)
            var receiver = "";
            for (var ri = 0x120; ri < 0x150 && bytes[ri] !== 0; ri++) {
                if (bytes[ri] >= 0x20 && bytes[ri] < 0x7f)
                    receiver += String.fromCharCode(bytes[ri]);
            }

            // Content ptr at +0x268
            var content = "";
            for (var ci = 0; ci < 2; ci++) {
                var coff = ci === 0 ? 0x268 : 0x288;
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

            if (receiver || content) {
                var msg = { idx: count, receiver: receiver, content: content };
                send("MSG " + JSON.stringify(msg));
                pageMsgCount++;
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
                c = obj.get('content', '')
                r = obj.get('receiver', '')
                print(f'[{obj["idx"]}] {r}: {c[:60]}', flush=True)
            except:
                pass
        elif line != 'R':
            print(line, flush=True)

script.on('message', on_msg)
script.load()

print(f'在联系人聊天里按 PageUp 翻页 (30s)', flush=True)
try:
    time.sleep(30)
except:
    pass

session.detach()

with open(outfile, 'w', encoding='utf-8') as f:
    for line in exported:
        f.write(line + '\n')

print(f'\n导出: {len(exported)} 条 -> {outfile}', flush=True)
if exported:
    with_content = sum(1 for l in exported if '"content"' in l and ': "' in l and l.split('"content": "')[1].startswith('"') == False and len(l.split('"content": "')[1].split('"')[0]) > 0)
    print(f'有内容: {with_content}/{len(exported)}', flush=True)
