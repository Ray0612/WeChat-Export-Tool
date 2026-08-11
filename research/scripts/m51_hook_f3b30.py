"""
M51 — Hook FUN_1816f3b30 (GetMessageListBySvrIds)
Capture return array (begin/end) to find history layer
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

if not PID:
    print("No Weixin.exe found", flush=True)
    exit(1)

session = frida.attach(PID)

# Find PID for pymem too
import pymem
pm = pymem.Pymem()
pm.open_process_from_id(PID)

js = '''
var mod = Process.findModuleByName("Weixin.dll");
var f3b30 = mod.base.add(0x016f3b30);
var hit = 0;

// Track returned array via ECX/RAX
Interceptor.attach(f3b30, {
    onEnter: function(args) {
        hit++;
        if (hit > 50) return;
        this.h = hit;

        var txt = "";
        for (var i = 0; i < 4; i++) {
            try { txt += " a" + i + "=" + (args[i] ? args[i].toString() : "n"); } catch(e) {}
        }
        send("C" + hit + txt);
    },
    onLeave: function(retval) {
        if (this.h > 50) return;
        send("R" + this.h + " ret=" + (retval ? retval.toString() : "n"));
    }
});
send("R");
'''

script = session.create_script(js)
all_hits = []

def handler(msg, data):
    if msg['type'] == 'send':
        line = msg['payload']
        all_hits.append(line)
        if line.startswith("C") or line.startswith("R"):
            print(line, flush=True)

script.on('message', handler)
script.load()

print(f"PID={PID} - 执行各种操作触发历史加载", flush=True)
print("1. 打开一个历史消息多的聊天", flush=True)
print("2. 翻页", flush=True)
print("3. 搜索消息", flush=True)
time.sleep(60)
session.detach()

# Count
calls = [l for l in all_hits if l.startswith("C")]
rets = [l for l in all_hits if l.startswith("R")]
print(f"\n调用了 {len(calls)} 次", flush=True)
print(f"返回了 {len(rets)} 次", flush=True)

# Analyze retvals
for r in rets:
    parts = r.split(" ret=")
    if len(parts) > 1:
        retval = parts[1]
        if retval != "n":
            try:
                addr = int(retval, 16)
                if addr > 0x100000:
                    # Try to read as pointer
                    data = pm.read_bytes(addr, 16)
                    print(f"  retval {retval}: data={data.hex()}", flush=True)
            except:
                pass
PYEOF