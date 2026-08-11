"""
M57 v3 — 实时监控 + 自动 dump 含消息的新内存区域
在手机备份/恢复过程中自动捕获数据
"""
import frida, psutil, time, os, json, threading
from datetime import datetime

import pymem
pm = pymem.Pymem()
pm.open_process_from_id(6312)

outdir = r'C:\Users\OK\Desktop\wechat_v4_export\experiments\m57_v3'
os.makedirs(outdir, exist_ok=True)

# Baseline
baseline = {}
base = 0x100000
while base < 0x7fffffffffff:
    try:
        mbi = pymem.memory.virtual_query(pm.process_handle, base)
        if mbi.State == 0x1000:
            baseline[base] = mbi.RegionSize
        base += mbi.RegionSize if mbi.RegionSize > 0 else 0x10000
    except:
        base += 0x10000

print("基线就绪，开始实时监控...", flush=True)
print("=" * 50, flush=True)
print("请在手机上触发备份/恢复", flush=True)
print("脚本每 3 秒检查一次新区域", flush=True)
print("发现含消息数据的大区域自动 dump", flush=True)
print("=" * 50, flush=True)

# Monitor loop
dumped = set()
try:
    while True:
        time.sleep(3)

        current = {}
        base = 0x100000
        while base < 0x7fffffffffff:
            try:
                mbi = pymem.memory.virtual_query(pm.process_handle, base)
                if mbi.State == 0x1000:
                    current[base] = mbi.RegionSize
                base += mbi.RegionSize if mbi.RegionSize > 0 else 0x10000
            except:
                base += 0x10000

        new = [(a, s) for a, s in current.items() if a not in baseline]

        for addr, size in new:
            if size > 512*1024 and addr not in dumped:  # >512KB and not dumped yet
                try:
                    data = pm.read_bytes(addr, min(size, 2*1024*1024))
                    if data:
                        # Check for message markers
                        for kw in [b'msgsource', b'wxid_', b'filehelper']:
                            if kw in data:
                                ts = datetime.now().strftime('%H%M%S')
                                fname = f"dump_{ts}_{addr:x}_{size//1024//1024}MB.bin"
                                path = os.path.join(outdir, fname)
                                with open(path, 'wb') as f:
                                    f.write(data[:min(len(data), 10*1024*1024)])
                                print(f"\n[!!] 捕获 {kw.decode()} 区域 0x{addr:x} ({size/1024/1024:.0f}MB) -> {fname}", flush=True)
                                dumped.add(addr)
                                break
                except:
                    pass

        # Show progress
        now = datetime.now()
        if now.second % 10 == 0:  # every 10s
            print(f"  [{now.strftime('%H:%M:%S')}] 已捕获 {len(dumped)} 个区域", flush=True)

except KeyboardInterrupt:
    pass

print(f"\n完成. 共捕获 {len(dumped)} 个含消息数据的区域", flush=True)
