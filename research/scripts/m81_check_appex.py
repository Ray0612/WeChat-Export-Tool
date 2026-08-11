"""
M81 — 检查所有 WeChatAppEx 进程，找有 flue.dll 的
"""
import frida, psutil, time

# Get all WeChatAppEx PIDs
target_pids = []
for proc in psutil.process_iter(['pid', 'name', 'exe']):
    name = proc.info['name'] or ''
    exe = proc.info.get('exe', '') or ''
    if 'wechatappex' in name.lower() and 'xwechat' in exe:
        target_pids.append(proc.info['pid'])

print(f"Target PIDs: {target_pids}")

jscode = """
'use strict';
var modules = Process.enumerateModules();
var hasFlue = false;
modules.forEach(function(mod) {
    if (mod.name.toLowerCase().indexOf('flue') !== -1) {
        console.log('>>> FOUND flue.dll: ' + mod.name + ' @ ' + mod.base + ' size=' + mod.size);
        hasFlue = true;
    }
    if (mod.name.toLowerCase().indexOf('sqlite') !== -1) {
        console.log('>>> FOUND sqlite: ' + mod.name + ' @ ' + mod.base);
    }
});
if (!hasFlue) {
    // List all interesting modules
    modules.forEach(function(mod) {
        var n = mod.name.toLowerCase();
        if (n.indexOf('wmpf') !== -1 || n.indexOf('radium') !== -1) {
            console.log('  WMPF module: ' + mod.name);
        }
    });
}
"""

for pid in target_pids:
    try:
        print(f"\nPID {pid}: connecting...")
        session = frida.attach(pid)
        script = session.create_script(jscode)
        script.load()
        time.sleep(1)
        session.detach()
    except Exception as e:
        print(f"  Error: {e}")
