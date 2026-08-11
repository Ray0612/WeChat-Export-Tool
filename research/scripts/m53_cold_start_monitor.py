"""
M53 — Cold start memory analysis
Compare memory maps before and after opening chat to find history data source
"""
import pymem, psutil, time, struct, os

target_pid = None
for p in sorted(psutil.process_iter(['pid','name']), key=lambda x: x.info['pid']):
    if p.info['name'] != 'Weixin.exe': continue
    try:
        pm = pymem.Pymem()
        pm.open_process_from_id(p.info['pid'])
        for mod in pm.list_modules():
            if 'weixin.dll' in mod.name.lower():
                target_pid = p.info['pid']
                break
        pm.close_process()
    except:
        pass
    if target_pid: break

if not target_pid:
    print("Weixin.exe with Weixin.dll not found", flush=True)
    exit(1)

pm = pymem.Pymem()
pm.open_process_from_id(target_pid)
proc = psutil.Process(target_pid)

outdir = r'C:\Users\OK\Desktop\wechat_v4_export\experiments\m53_cold'
os.makedirs(outdir, exist_ok=True)

# Phase 1: Record baseline memory (don't open any chat yet)
print(f"Phase 1: Baseline (current state, {target_pid})", flush=True)
baseline_regions = []
base = 0x100000
while base < 0x7fffffffffff:
    try:
        mbi = pymem.memory.virtual_query(pm.process_handle, base)
        if mbi.State == 0x1000:
            baseline_regions.append((base, mbi.RegionSize, mbi.Protect))
        base += mbi.RegionSize if mbi.RegionSize > 0 else 0x10000
    except:
        base += 0x10000

baseline_mb = sum(r[1] for r in baseline_regions) / 1024 / 1024
baseline_count = len(baseline_regions)
print(f"  Regions: {baseline_count}, Total: {baseline_mb:.0f}MB", flush=True)

# Phase 2: Wait for user to open chat
print(f"\nPhase 2: 请打开一个历史消息多的聊天窗口", flush=True)
print(f"等待 60 秒...", flush=True)
time.sleep(60)

# Phase 3: Take new snapshot
print(f"Phase 3: Post-chat snapshot", flush=True)
after_regions = []
base = 0x100000
while base < 0x7fffffffffff:
    try:
        mbi = pymem.memory.virtual_query(pm.process_handle, base)
        if mbi.State == 0x1000:
            after_regions.append((base, mbi.RegionSize, mbi.Protect))
        base += mbi.RegionSize if mbi.RegionSize > 0 else 0x10000
    except:
        base += 0x10000

after_mb = sum(r[1] for r in after_regions) / 1024 / 1024
after_count = len(after_regions)
print(f"  Regions: {after_count}, Total: {after_mb:.0f}MB", flush=True)

# Find new regions
baseline_set = {(r[0], r[1]) for r in baseline_regions}
new_regions = [r for r in after_regions if (r[0], r[1]) not in baseline_set]

print(f"\nNew memory regions: {len(new_regions)}", flush=True)

# Search for wxid/chatroom/msgsource in new regions
total_new_mb = 0
for addr, size, prot in new_regions:
    sz = min(size, 2*1024*1024)
    total_new_mb += size / 1024 / 1024
    try:
        data = pm.read_bytes(addr, sz)
    except:
        continue

    # Check for message-related strings
    markers = 0
    for m in [b'wxid_', b'@chatroom', b'filehelper', b'msgsource', b'create_time']:
        if data and m in data:
            markers += 1
            pos = data.find(m)
            end = pos
            while end < len(data) and data[end] >= 0x20 and data[end] < 0x7f:
                end += 1
            s = data[pos:end].decode('ascii', errors='replace')[:50]
            print(f"  [MARKER] {s} in new region 0x{addr:x}", flush=True)
            break

print(f"\nTotal new: {total_new_mb:.0f}MB across {len(new_regions)} regions", flush=True)

# Phase 4: Search for large data structures
print(f"\nPhase 4: 搜索大容量容器", flush=True)
prefix_core = bytes([0x02, 0x05, 0x09, 0x01, 0x01, 0x04])
compact_count = 0
for addr, size, prot in new_regions[:50]:  # Limit to first 50 new regions
    try:
        data = pm.read_bytes(addr, min(size, 1024*1024))
        if data:
            pos = -1
            while True:
                pos = data.find(prefix_core, pos + 1)
                if pos < 0: break
                compact_count += 1
        if compact_count > 100:
            print(f"  紧凑结构在新区域 0x{addr:x} (已找到 {compact_count} 条)", flush=True)
    except:
        pass

print(f"  新区域中紧凑结构条目: {compact_count}", flush=True)

print(f"\nDone.", flush=True)
