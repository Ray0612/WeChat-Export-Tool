# -*- coding: utf-8 -*-
"""
Frida SPAWN 模式 — 在 WeChatAppEx 启动前 hook sqlite3_key_v2
流程: 杀掉已有 WeChatAppEx → Frida spawn 新进程 → hook → 捕获 key
"""
import frida, sys, time, psutil, json, os, signal
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

OUTDIR = r'C:\Users\OK\Desktop\wx_export'

hook_code = '''
console.log("[*] Hook active - spawned process");

function setupHook() {
    var flueMod = Process.findModuleByName("flue.dll");
    if (!flueMod) return false;

    var keyFunc = flueMod.base.add(0x2a9c805);
    console.log("[+] flue.dll at " + flueMod.base);

    Interceptor.attach(keyFunc, {
        onEnter: function(args) {
            var keyLen = args[3].toInt32();
            if (keyLen > 0 && keyLen <= 256) {
                var data = Memory.readByteArray(args[2], keyLen);
                var hex = "";
                var arr = new Uint8Array(data);
                for (var i = 0; i < arr.length; i++) {
                    hex += ("0" + arr[i].toString(16)).slice(-2);
                }
                var name = "";
                try { if (args[1] !== null) name = Memory.readUtf8String(args[1]); } catch(e) {}
                console.log("[KEY] " + JSON.stringify({key_hex: hex, key_len: keyLen, name: name}));
            }
        }
    });
    return true;
}

if (!setupHook()) {
    var attempts = 0;
    var timer = setInterval(function() {
        attempts++;
        if (setupHook()) {
            clearInterval(timer);
            console.log("[+] Hook ready");
        } else if (attempts > 50) {
            clearInterval(timer);
            console.log("[-] flue.dll not found");
        }
    }, 200);
} else {
    console.log("[+] Hook ready");
}
'''

def find_main_appex():
    """Find the main xwechat WeChatAppEx (browser process, no --type=)"""
    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'exe']):
        if 'WeChatAppEx' not in (proc.info['name'] or ''): continue
        cmd = proc.info['cmdline'] or []
        cmd_str = str(cmd)
        # Browser process has no --type= flag
        if 'xwechat' in cmd_str and '--type=' not in cmd_str:
            return proc.info['pid'], cmd, proc.info['exe']
    return None, None, None

print('=' * 50)
print('Frida Spawn Key Capture')
print('=' * 50)

pid, cmd, exe = find_main_appex()
if not pid:
    print('[-] 找不到主 WeChatAppEx 进程')
    sys.exit(1)

print(f'[+] 找到目标进程 PID: {pid}')
print(f'[+] 执行路径: {exe}')

if cmd:
    # Extract args (skip the first - it's the exe path)
    spawn_args = cmd[1:]  # All args except program path
    print(f'[+] 参数: {" ".join(spawn_args[:3])}...')

# Kill the existing process
print(f'\n[*] 杀掉 PID {pid}...')
try:
    proc = psutil.Process(pid)
    proc.kill()
    time.sleep(2)
    print('[+] 已杀掉')
except:
    print('[-] 杀掉失败')

# Quick check if process is gone
if psutil.pid_exists(pid):
    print('[-] 进程仍然存在')
    sys.exit(1)

# Now spawn with Frida
print('\n[*] 用 Frida spawn WeChatAppEx...')
try:
    # Spawn with the same arguments
    device = frida.get_local_device()
    pid_new = device.spawn(exe, argv=cmd)
    print(f'[+] Spawned as PID: {pid_new}')

    session = device.attach(pid_new)
    print('[+] Attached')

    script = session.create_script(hook_code)
    KEY_CAPTURED = []

    def on_message(msg, data):
        if msg['type'] == 'send':
            payload = msg.get('payload', '')
            if isinstance(payload, str) and '{' in payload:
                try:
                    p = json.loads(payload)
                    key = p.get('key_hex', '')
                    print(f'\n✅ KEY CAPTURED!')
                    print(f'   64-char key: {key}')
                    print(f'   DB: {p.get("name", "")}')
                    KEY_CAPTURED.append(key)
                    path = os.path.join(OUTDIR, 'sqlcipher_key_captured.txt')
                    with open(path, 'w') as f:
                        f.write(key)
                    print(f'   Saved to: {path}')
                except: pass

    script.on('message', on_message)
    script.load()

    # Resume the process
    print('[*] Resuming process...')
    device.resume(pid_new)

    # Wait for key capture
    for i in range(100):
        if KEY_CAPTURED:
            break
        time.sleep(0.5)

    session.detach()

except Exception as e:
    print(f'[-] Error: {e}')
    import traceback
    traceback.print_exc()

if KEY_CAPTURED:
    print(f'\n✅ Key 已捕获!')
else:
    print(f'\n[-] 未捕获到 key')
    print('微信可能自动重启了 WeChatAppEx，尝试再次运行本脚本')
