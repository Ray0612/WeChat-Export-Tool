# Frida hook — 在微信运行时拦截数据库密钥
# 自动查找 Weixin.exe PID 并 hook

import frida
import sys
import os
import time
import psutil

script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hook_key.js")
with open(script_path, "r", encoding="utf-8") as f:
    hook_code = f.read()

def on_message(message, data):
    if message["type"] == "send":
        print(message["payload"])
    elif message["type"] == "error":
        print(f"[ERROR] {message}")

# 自动找 Weixin.exe PID
target_pid = None
for p in psutil.process_iter(['pid', 'name']):
    if p.info['name'] == 'Weixin.exe':
        target_pid = p.info['pid']
        break

if not target_pid:
    print("[-] Weixin.exe not running. Start WeChat first.")
    sys.exit(1)

print(f"[+] Found Weixin.exe PID: {target_pid}")

try:
    session = frida.attach(target_pid)
    print("[+] Frida attached successfully")

    script = session.create_script(hook_code)
    script.on("message", on_message)
    script.load()

    print("[*] Hook active, waiting for database key calls...")
    print("[*] (5秒超时，无输出则说明 hook 的函数未命中)")
    print()

    # 等5秒
    time.sleep(6)

    # 尝试 detach
    try:
        session.detach()
    except:
        pass

    print("\n[*] Done. 如果没有任何密钥输出，说明需要找其他函数来 hook。")

except Exception as e:
    print(f"[-] Error: {e}")
    sys.exit(1)
