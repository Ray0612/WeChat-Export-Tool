"""
M64 — 快速捕获（500ms 轮询），用户将触发手机备份
"""
import pymem, psutil, time, os, datetime

PID = 6312
pm = pymem.Pymem()
pm.open_process_from_id(PID)

outdir = r'C:\Users\OK\Desktop\wechat_v4_export\experiments\m64_fast'
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

print(f"基线就绪: {len(baseline)} 区域, {sum(baseline.values())/1024/1024:.0f}MB", flush=True)
print("现在触发手机备份", flush=True)

dumped = set()
try:
    while True:
        time.sleep(0.5)  # 每秒两次

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

        new = [(a, s) for a, s in current.items() if a not in baseline and s > 512*1024]

        for addr, size in new:
            if addr in dumped:
                continue
            try:
                data = pm.read_bytes(addr, min(size, 2*1024*1024))
                if data:
                    # Check for ANY interesting content
                    score = 0
                    for kw in [b'msgsource', b'wxid_', b'filehelper', b'<msg', b'<des>']:
                        if kw in data:
                            score += 1
                    if score >= 1:
                        ts = datetime.datetime.now().strftime('%H%M%S%f')[:8]
                        fname = f"dump_{ts}_{addr:x}.bin"
                        path = os.path.join(outdir, fname)
                        with open(path, 'wb') as f:
                            f.write(data[:min(len(data), 10*1024*1024)])
                        print(f"[!] 捕获 0x{addr:x} ({size/1024/1024:.0f}MB, score={score}) -> {fname}", flush=True)
                        dumped.add(addr)
            except:
                pass

except KeyboardInterrupt:
    pass

print(f"\n完成. 共捕获 {len(dumped)} 个区域", flush=True)
