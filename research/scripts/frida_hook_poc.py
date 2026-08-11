# Frida PoC: Hook GetPagedMessages (offset 0x016ade70 in Weixin.dll)
import frida
import psutil
import time
import sys

TARGET_OFFSET = 0x016ade70

jscode = """
'use strict';
var base = Module.findBaseAddress('Weixin.dll');
if (!base) {
    console.log('[-] Weixin.dll not found!');
} else {
    var funcAddr = base.add(""" + hex(TARGET_OFFSET) + """);
    console.log('[*] Weixin.dll base: ' + base);
    console.log('[*] Target function: ' + funcAddr);

    var hitCount = 0;
    Interceptor.attach(funcAddr, {
        onEnter: function(args) {
            hitCount++;
            console.log('[GetPagedMessages] HIT #' + hitCount);
        }
    });
    console.log('[*] Hook installed. 翻页试试...');
}
"""

# 找 Weixin.exe — 选运行时间最长的那个（主进程）
weixin_procs = []
for p in psutil.process_iter(['pid', 'name', 'create_time']):
    if p.info['name'] == 'Weixin.exe':
        weixin_procs.append((p.info['pid'], p.info['create_time']))

if not weixin_procs:
    print("[-] Weixin.exe not running.")
    sys.exit(1)

# 选最早创建的那个（主进程）
weixin_procs.sort(key=lambda x: x[1])
target_pid = weixin_procs[0][0]
print(f"[+] Weixin.exe PID: {target_pid}（共 {len(weixin_procs)} 个进程）")

try:
    session = frida.attach(target_pid)
    print("[+] Frida attached.")
except Exception as e:
    print(f"[-] Frida attach failed: {e}")
    sys.exit(1)

script = session.create_script(jscode)

def on_message(msg, data):
    if msg['type'] == 'send':
        print(msg['payload'])
    elif msg['type'] == 'error':
        print("[ERROR]", msg)

script.on('message', on_message)
script.load()

print("[*] PoC running. 打开聊天窗口 → 向上翻页 → 观察 HIT")
print("[*] Ctrl+C 停止")
try:
    time.sleep(9999)
except KeyboardInterrupt:
    print("\n[*] Stopped.")
    session.detach()
