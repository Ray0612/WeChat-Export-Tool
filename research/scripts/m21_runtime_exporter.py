"""
M21 — Runtime Export Pipeline
Frida Hook FUN_1816c2a20 → 实时捕获消息并导出
"""
import frida, psutil, time, os, json
from datetime import datetime

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

outfile = r'C:\Users\OK\Desktop\wechat_v4_export\runtime_export.json'
os.makedirs(os.path.dirname(outfile), exist_ok=True)

jscode = '''
'use strict';

var mod = Process.findModuleByName('Weixin.dll');
var base = mod.base;
var funcAddr = base.add(0x016c2a20);
var hitCount = 0;
var messages = [];

send('[m21] FUN_1816c2a20 @ ' + funcAddr.toString());

Interceptor.attach(funcAddr, {
    onEnter: function(args) {
        hitCount++;
        var a1 = args[1];
        if (!a1) return;

        // Read 0x2d8 message struct
        try {
            var data = a1.readByteArray(0x2d8);
            if (!data) return;
            var bytes = new Uint8Array(data);

            // Read receiver at +0x120 (inline string)
            var receiver = '';
            for (var ri = 0x120; ri < 0x150 && bytes[ri] !== 0; ri++) {
                receiver += String.fromCharCode(bytes[ri]);
            }

            // Try content at +0x268 and +0x288
            var content = '';
            var contentOff = -1;
            for (var ci = 0; ci < 2; ci++) {
                var offset = ci === 0 ? 0x268 : 0x288;
                var ptr = 0;
                for (var bi = 0; bi < 8; bi++) {
                    ptr += bytes[offset + bi] << (bi * 8);
                }
                if (ptr > 0x100000 && ptr < 0x7fffffffffff) {
                    try {
                        var cptr = ptr(ptr.toString());
                        var str = cptr.readUtf8String();
                        if (str && str.length > 0 && str.length < 500) {
                            content = str;
                            contentOff = offset;
                            break;
                        }
                    } catch(e) {}
                }
            }

            // Only report if we have receiver and content
            if (receiver.length > 0 && content.length > 0) {
                hitCount++;
                var msg = {
                    idx: hitCount,
                    receiver: receiver,
                    content: content,
                    contentOffset: contentOff,
                    structAddr: a1.toString(),
                };
                messages.push(msg);
                send('[MSG #' + hitCount + '] ' + receiver + ': ' + content.substring(0, 80));
            }
        } catch(e) {
            send('[ERR] ' + e.toString().substring(0, 60));
        }
    }
});

// Dump all captured messages on demand
recv('dump', function() {
    send('[DUMP] ' + JSON.stringify(messages));
    send('[DONE]');
});
'''

session = frida.attach(PID)
script = session.create_script(jscode)
captured = []
dump_requested = [False]

def on_msg(msg, data):
    global captured
    if msg['type'] == 'send':
        line = msg['payload']
        print(line, flush=True)

        if line.startswith('[MSG #'):
            # Extract JSON-ish info
            try:
                parts = line.split('] ', 2)
                if len(parts) >= 3:
                    info = parts[2]
                    captured.append(info)
            except:
                pass
        elif line.startswith('[DUMP] '):
            # Save to file
            json_str = line[7:]
            try:
                msgs = json.loads(json_str)
                with open(outfile.replace('.json', f'_{len(msgs)}.json'), 'w', encoding='utf-8') as f:
                    json.dump(msgs, f, ensure_ascii=False, indent=2)
                print(f'[m21] Saved {len(msgs)} messages to {outfile}', flush=True)
            except Exception as e:
                print(f'[m21] Save error: {e}', flush=True)

script.on('message', on_msg)
script.load()

print(f'[m21] Runtime Exporter PID={PID}', flush=True)
print('[m21] Press PageUp to capture messages', flush=True)
print('[m21] Ctrl+C to stop', flush=True)

try:
    time.sleep(99999)
except:
    pass

# Final save
script.post({'type': 'dump'})
time.sleep(2)
session.detach()

print(f'[m21] Done. Captured {len(captured)} messages.', flush=True)
