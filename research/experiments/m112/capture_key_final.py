# -*- coding: utf-8 -*-
"""
Frida spawn+gating — 最终版
流程: 启动微信 → hook 子进程的 key 函数 → 捕获 key
"""
import frida, sys, time, psutil, json, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

OUTDIR = r'C:\Users\OK\Desktop\wx_export'
KEY_SAVED = [False]  # mutable for closure

child_hook = '''
Process.on("module-loaded", function(m) {
    if (m.name.indexOf("Weixin.dll") !== -1) {
        console.log("[+] Weixin.dll loaded, hooking key function...");
        Interceptor.attach(m.base.add(0x55d0f0), {
            onEnter: function(args) {
                for (var i = 0; i < 4; i++) {
                    try {
                        var d = Memory.readByteArray(args[i], 32);
                        var a = new Uint8Array(d);
                        var s = {};
                        for (var j = 0; j < a.length; j++) s[a[j]] = true;
                        if (Object.keys(s).length >= 20) {
                            var h = "";
                            for (var j = 0; j < a.length; j++) h += ("0" + a[j].toString(16)).slice(-2);
                            console.log("[KEY] " + h);
                            send(JSON.stringify({key: h}));
                        }
                    } catch(e) {}
                }
            }
        });
    }
});
'''

def on_child(child):
    print(f'[+] Child: PID {child.pid} ({child.path[-40:]})')
    if 'Weixin.exe' not in child.path and 'WeChatAppEx' not in child.path:
        return
    try:
        s = device.attach(child.pid)
        sc = s.create_script(child_hook)
        sc.on('message', lambda m, d: on_key_msg(m, d, s))
        sc.load()
        print(f'  -> Hook set on PID {child.pid}')
    except Exception as e:
        print(f'  -> Error: {e}')

def on_key_msg(msg, data, session):
    if msg['type'] == 'send':
        p = msg.get('payload', '')
        if isinstance(p, str) and p.startswith('{'):
            try:
                j = json.loads(p)
                k = j.get('key', '')
                if k:
                    print(f'\n{"="*50}')
                    print(f'✅ KEY: {k}')
                    path = os.path.join(OUTDIR, 'sqlcipher_key_captured.txt')
                    with open(path, 'w') as f: f.write(k)
                    print(f'Saved to {path}')
                    KEY_SAVED[0] = True
                    session.detach()
            except: pass
        elif 'KEY:' in p:
            print(f'[KEY] {p.split("KEY:")[1].strip()}')
        elif p:
            print(f'  [C] {p}')

exe_path = r'C:\Program Files\Tencent\Weixin\Weixin.exe'
print(f'[+] Spawning {exe_path}...')
device = frida.get_local_device()
pid = device.spawn([exe_path])
print(f'[+] PID {pid}')

# Attach to launcher
session = device.attach(pid)
session.enable_child_gating()
device.on('child-added', on_child)
# Also hook the main (parent) process
parent_session = device.attach(pid)
parent_script = parent_session.create_script(child_hook)
parent_script.on('message', lambda m, d: on_key_msg(m, d, parent_session))
parent_script.load()
print(f'[+] Parent hook set on PID {pid}')

device.resume(pid)
print(f'[+] 微信已启动，请登录')
print(f'[+] 等待 key...\n')

# Wait
for i in range(180):
    if KEY_SAVED[0]: break
    time.sleep(1)

session.detach()
if KEY_SAVED[0]:
    print('\n✅ Key captured!')
else:
    print('\n[-] No key captured')
