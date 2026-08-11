"""
M57B — Weixin.exe 历史消息动态监控
准备所有 Hook + 内存基线，等待用户触发备份/恢复
"""
import frida, psutil, time, os, struct, json
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

if not PID:
    print("Weixin.exe not found", flush=True)
    exit(1)

import pymem
pm = pymem.Pymem()
pm.open_process_from_id(PID)

outdir = r'C:\Users\OK\Desktop\wechat_v4_export\experiments\m57'
os.makedirs(outdir, exist_ok=True)

ts = datetime.now().strftime('%H%M%S')

# === Phase 1: 内存基线快照 ===
print(f"[{ts}] Phase 1: 内存基线快照", flush=True)
baseline = {}
base = 0x100000
region_count = 0
while base < 0x7fffffffffff:
    try:
        mbi = pymem.memory.virtual_query(pm.process_handle, base)
        if mbi.State == 0x1000:
            baseline[base] = mbi.RegionSize
            region_count += 1
        base += mbi.RegionSize if mbi.RegionSize > 0 else 0x10000
    except:
        base += 0x10000

total_baseline = sum(baseline.values()) / 1024 / 1024
print(f"  基线: {region_count} 区域, {total_baseline:.0f}MB", flush=True)

# Save baseline for later comparison
with open(os.path.join(outdir, 'baseline.json'), 'w') as f:
    json.dump({hex(k): v for k, v in baseline.items()}, f)

# === Phase 2: 安装所有 Frida Hook ===
print(f"[{ts}] Phase 2: 安装 Hook", flush=True)

session = frida.attach(PID)

js = '''
var mod = Process.findModuleByName("Weixin.dll");

// Hook 1: Caller1 (翻页入口)
var c1 = mod.base.add(0x01683b08);
var pages = 0;
Interceptor.attach(c1, {
    onEnter: function(a) { pages++; },
    onLeave: function(r) { send("CALLER1 page=" + pages); }
});

// Hook 2: GetPagedMessages
var gpm = mod.base.add(0x016ff6b0);
var loads = 0;
Interceptor.attach(gpm, {
    onEnter: function() { loads++; send("GPM enter #" + loads); },
    onLeave: function() { send("GPM leave #" + loads); }
});

// Hook 3: FUN_1816c2a20 (0x2d8 遍历)
var filter = mod.base.add(0x016c2a20);
var filtCalls = 0;
Interceptor.attach(filter, {
    onEnter: function() { filtCalls++; }
});

// Hook 4: FUN_1816f3510 (缓存)
var cache = mod.base.add(0x016f3510);
var cacheCalls = 0;
Interceptor.attach(cache, {
    onEnter: function() { cacheCalls++; }
});

// Report every 10s
setInterval(function() {
    send("STATS pages=" + pages + " gpm=" + loads + " filter=" + filtCalls + " cache=" + cacheCalls);
}, 10000);

send("HOOKS_READY");
'''

script = session.create_script(js)
script.on('message', lambda msg,d: print(msg['payload'], flush=True) if msg['type']=='send' else None)
script.load()
time.sleep(2)

print(f"[{ts}] Hook 就绪，等待操作...", flush=True)
print("=" * 50, flush=True)
print("请在手机上触发备份/恢复，或打开大聊天翻页", flush=True)
print("脚本将自动记录所有函数调用和内存变化", flush=True)
print("=" * 50, flush=True)

# === Phase 3: 监控循环（120秒）===
try:
    for i in range(12):
        time.sleep(10)

        # Take periodic memory diff
        current_regions = {}
        base = 0x100000
        while base < 0x7fffffffffff:
            try:
                mbi = pymem.memory.virtual_query(pm.process_handle, base)
                if mbi.State == 0x1000:
                    current_regions[base] = mbi.RegionSize
                base += mbi.RegionSize if mbi.RegionSize > 0 else 0x10000
            except:
                base += 0x10000

        # Find new regions
        new_regions = []
        for addr, size in current_regions.items():
            if addr not in baseline:
                new_regions.append((addr, size))

        if new_regions:
            new_mb = sum(s for _, s in new_regions) / 1024 / 1024
            print(f"  +{new_mb:.0f}MB 新区域 ({len(new_regions)} 个)", flush=True)
            # Check for message content in large new regions
            for addr, size in new_regions[:5]:
                if size > 1024*1024:  # >1MB
                    try:
                        data = pm.read_bytes(addr, min(size, 65536))
                        if data:
                            for m in [b'msgsource', b'wxid_', b'filehelper', b'TEST_RAY']:
                                if m in data:
                                    print(f"    [!!] {m.decode()} found in new region 0x{addr:x}", flush=True)
                    except:
                        pass

except KeyboardInterrupt:
    pass

session.detach()
print("\nDone.", flush=True)
