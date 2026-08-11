# -*- coding: utf-8 -*-
"""
Frida spawn+gating — 启动时 hook sqlite3_key_v2
"""
import frida, sys, time, psutil, json, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

OUTDIR = r'C:\Users\OK\Desktop\wx_export'

child_hook = '''
console.log("[CHILD] PID=" + Process.id);

function setupHook() {
    var m = Process.findModuleByName("flue.dll");
    if (!m) return false;
    var addr = m.base.add(0x2a9c805);
    console.log("[HOOK] sqlite3_key_v2 at " + addr);
    Interceptor.attach(addr, {
        onEnter: function(args) {
            var klen = args[3].toInt32();
            if (klen > 0 && klen <= 256) {
                var d = Memory.readByteArray(args[2], klen);
                var h = ""; var a = new Uint8Array(d);
                for (var i = 0; i < a.length; i++) h += ("0" + a[i].toString(16)).slice(-2);
                var n = "";
                try { if (args[1] !== null) n = Memory.readUtf8String(args[1]); } catch(e) {}
                console.log("[KEY] name=" + n + " key=" + h);
                send(JSON.stringify({key_hex: h, key_len: klen, name: n}));
            }
        }
    });
    return true;
}

if (!setupHook()) {
    var n = 0;
    var t = setInterval(function() {
        n++;
        if (setupHook()) { clearInterval(t); console.log("[HOOK] ready"); }
        else if (n > 30) { clearInterval(t); console.log("[HOOK] timeout"); send("TIMEOUT"); }
    }, 500);
} else {
    console.log("[HOOK] ready");
}
'''

KEY_SAVED = False

def on_child(child):
    global KEY_SAVED
    print(f'[CHILD] PID {child.pid}: {child.path[-50:]}')
    if 'WeChatAppEx' not in child.path:
        return
    print(f'[+] Attaching to WeChatAppEx PID {child.pid}...')
    try:
        s = device.attach(child.pid)
        def on_msg(msg, data):
            global KEY_SAVED
            if msg['type'] == 'send':
                p = msg.get('payload', '')
                if isinstance(p, str):
                    if p.startswith('{'):
                        try:
                            j = json.loads(p)
                            k = j.get('key_hex', '')
                            if k:
                                print(f'\n{"="*50}')
                                print(f'  KEY: {k}')
                                print(f'  DB: {j.get("name","")}')
                                path = os.path.join(OUTDIR, 'sqlcipher_key_captured.txt')
                                with open(path, 'w') as f: f.write(k)
                                print(f'  Saved to {path}')
                                KEY_SAVED = True
                        except: pass
                    elif p != "TIMEOUT":
                        print(f'  [PID {child.pid}] {p}')
        sc = s.create_script(child_hook)
        sc.on('message', on_msg)
        sc.load()
        print(f'[+] PID {child.pid} hook active')
    except Exception as e:
        print(f'[-] Error: {e}')

weixin_path = r'C:\Program Files\Tencent\Weixin\Weixin.exe'
print('[+] Spawning Weixin.exe with child-gating...')
device = frida.get_local_device()
pid = device.spawn([weixin_path])
session = device.attach(pid)
session.enable_child_gating()
device.on('child-added', on_child)
device.resume(pid)
print(f'[+] Weixin.exe PID {pid} running')
print('[+] 请登录微信，等待 key 捕获...')

for i in range(300):
    if KEY_SAVED: break
    time.sleep(1)

if KEY_SAVED:
    print('\n[+] Key captured!')
else:
    print('\n[-] No key captured')
    # Show any remaining output
