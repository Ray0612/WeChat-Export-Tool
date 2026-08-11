# -*- coding: utf-8 -*-
"""
Frida 捕获 sqlite3_key_v2 — 使用 child-gating 模式
在 Weixin.exe 上启用 child-gating，当 WeChatAppEx 被 spawn 时 hook
"""
import frida, sys, time, psutil, json, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

OUTDIR = r'C:\Users\OK\Desktop\wx_export'

hook_code = '''
console.log("[*] Hook active on child process");

function setupHook() {
    var flueMod = Process.findModuleByName("flue.dll");
    if (!flueMod) return false;

    var keyFunc = flueMod.base.add(0x2a9c805);
    console.log("[+] flue.dll at " + flueMod.base + ", key func at " + keyFunc);

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
                send(JSON.stringify({key_hex: hex, key_len: keyLen, name: name}));
            }
        }
    });
    return true;
}

// Retry hook
if (!setupHook()) {
    var attempts = 0;
    var timer = setInterval(function() {
        attempts++;
        if (setupHook()) {
            clearInterval(timer);
            console.log("[+] Hook ready");
        } else if (attempts > 30) {
            clearInterval(timer);
            console.log("[-] Timeout");
            send("TIMEOUT");
        }
    }, 500);
} else {
    console.log("[+] Hook ready");
}
'''

KEY_SAVED = False

def on_message(msg, data):
    global KEY_SAVED
    if msg['type'] == 'send':
        payload = msg.get('payload', '')
        if isinstance(payload, str) and payload.startswith('{'):
            try:
                p = json.loads(payload)
                key = p.get('key_hex', '')
                print(f'\n✅ KEY CAPTURED!')
                print(f'   Key: {key}')
                print(f'   DB: {p.get("name", "")}')
                path = os.path.join(OUTDIR, 'sqlcipher_key_captured.txt')
                with open(path, 'w') as f:
                    f.write(key)
                print(f'   Saved to: {path}')
                KEY_SAVED = True
            except: pass

def find_targets():
    """Find Weixin.exe and WeChatAppEx PIDs"""
    weixin_pid = None
    for proc in psutil.process_iter(['pid', 'name']):
        name = proc.info['name'] or ''
        if name.lower() == 'weixin.exe':
            weixin_pid = proc.info['pid']
            break
    return weixin_pid

print('=' * 50)
print('Frida Key Capture v2 - Child Gating')
print('=' * 50)
print()
print('步骤:')
print('1. 微信必须在运行')
print('2. 本脚本 attach 到 Weixin.exe 并启用 child-gating')
print('3. 当 WeChatAppEx 被创建时，自动 hook sqlite3_key_v2')
print()

# Find Weixin.exe
weixin_pid = find_targets()
if not weixin_pid:
    print('[-] 微信未运行')
    sys.exit(1)
print(f'[+] Weixin.exe PID: {weixin_pid}')

try:
    session = frida.attach(weixin_pid)
    print('[+] Frida attached to Weixin.exe')

    # Enable child gating
    session.enable_child_gating()
    print('[+] Child gating enabled')

    script = session.create_script(hook_code)
    script.on('message', on_message)
    script.load()

    print('\n[*] 监控中... 当 WeChatAppEx 启动时会自动 hook')
    print('[*] 尝试重新打开微信或触发备份操作')
    print('[*] 等待 key (最多 120 秒)...\n')

    for i in range(240):
        if KEY_SAVED:
            break
        time.sleep(0.5)

    session.detach()

except Exception as e:
    print(f'[-] Error: {e}')
    import traceback
    traceback.print_exc()

if KEY_SAVED:
    print('\n✅ Key 已捕获! 可以用 decrypt_db.py 解密数据库')
else:
    print('\n[-] 未捕获到 key。试试手动关开微信')
