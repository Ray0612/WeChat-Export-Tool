# -*- coding: utf-8 -*-
"""
Frida 捕获 sqlite3_key_v2 的 key
流程: 关微信 → 启动本脚本 → 开微信 → Frida 自动捕获 key
"""
import frida, sys, time, psutil, json, os, threading
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

OUTDIR = r'C:\Users\OK\Desktop\wx_export'
KEY_SAVED = False

hook_code = '''
console.log("[*] Frida hook active");

function setupHook() {
    var flueMod = Process.findModuleByName("flue.dll");
    if (!flueMod) return false;

    var keyFunc = flueMod.base.add(0x2a9c805);
    console.log("[+] sqlite3_key_v2 at: " + keyFunc);

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
                try {
                    if (args[1] !== null) name = Memory.readUtf8String(args[1]);
                } catch(e) {}
                console.log("[KEY] " + JSON.stringify({key_hex: hex, key_len: keyLen, name: name}));
            }
        }
    });
    return true;
}

// Immediate attempt + retry loop
if (!setupHook()) {
    var attempts = 0;
    var timer = setInterval(function() {
        attempts++;
        if (setupHook()) {
            clearInterval(timer);
            console.log("[+] Hook established");
        } else if (attempts > 120) {
            clearInterval(timer);
            console.log("[-] Timeout");
        }
    }, 500);
} else {
    console.log("[+] Hook ready");
}
'''

def on_message(msg, data):
    global KEY_SAVED
    if msg['type'] == 'send':
        try:
            payload = json.loads(msg['payload'])
            key_hex = payload.get('key_hex', '')
            key_len = payload.get('key_len', 0)
            name = payload.get('name', '')

            print(f'\n{"="*50}')
            print(f'✅ KEY CAPTURED!')
            print(f'   Key ({key_len} bytes): {key_hex}')
            print(f'   DB: {name}')
            print(f'{"="*50}')

            path = os.path.join(OUTDIR, 'sqlcipher_key_captured.txt')
            with open(path, 'w') as f:
                f.write(key_hex)
            print(f'   Saved to: {path}')
            KEY_SAVED = True
        except: pass
    elif msg['type'] == 'error':
        desc = msg.get('description', '')
        if 'flue.dll' not in desc:
            print(f'[E] {desc[:100]}')

def find_appex():
    """Find main WeChatAppEx PID (xwechat, not WXWork)"""
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        if 'WeChatAppEx' not in (proc.info['name'] or ''): continue
        cmd = str(proc.info['cmdline'] or [])
        if 'xwechat' in cmd and '--type=renderer' not in cmd:
            return proc.info['pid'], proc.info['cmdline']
    return None, None

print('=' * 50)
print('Frida Key Capture')
print('=' * 50)
print()
print('步骤:')
print('1. 确保微信已关闭')
print('2. 本脚本启动后，打开微信')
print('3. 脚本会自动 hook key 并捕获')
print()

# Wait for WeChat to be closed
print('等待微信关闭...', end='', flush=True)
while True:
    pid, cmd = find_appex()
    if pid is None:
        print(' [已关闭]')
        break
    time.sleep(2)
    print('.', end='', flush=True)

# Now wait for WeChatAppEx to start and hook it
print()
print('等待微信启动...')

while not KEY_SAVED:
    pid, cmd = find_appex()
    if pid:
        print(f'\n检测到 WeChatAppEx! PID: {pid}')
        try:
            session = frida.attach(pid)
            print('Frida 已 attach')

            script = session.create_script(hook_code)
            script.on('message', on_message)
            script.load()

            # Wait for key capture (max 30 seconds)
            for i in range(60):
                if KEY_SAVED:
                    break
                time.sleep(0.5)

            session.detach()
            if KEY_SAVED:
                break

        except Exception as e:
            print(f'Frida attach失败: {e}')

    time.sleep(1)

if KEY_SAVED:
    print('\n✅ Key 已捕获！可以用 decrypt_db.py 解密数据库了')
else:
    print('\n❌ 未捕获到 key。可能 sqlite3_key_v2 不在新启动的进程中')
    print('可以尝试: 重新关开微信再试一次')
