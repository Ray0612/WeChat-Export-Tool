"""
M73 — 内存捕获策略验证
监控新 Region + 已有 Region 大小增长
"""
import pymem, psutil, time, os, datetime

PID = 6312
pm = pymem.Pymem()
pm.open_process_from_id(PID)

outdir = r'C:\Users\OK\Desktop\wechat_v4_export\experiments\m73_test'
os.makedirs(outdir, exist_ok=True)
logfile = os.path.join(outdir, 'capture_log.txt')

def log(msg):
    with open(logfile, 'a', encoding='utf-8') as f:
        f.write(f"[{datetime.datetime.now().strftime('%H:%M:%S.%f')[:12]}] {msg}\n")
    print(msg, flush=True)

# Phase 1: Baseline
log("=== M73 Capture Verification ===")
log("Phase 1: Baseline snapshot")

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

total_mb = sum(baseline.values()) / 1024 / 1024
log(f"Baseline: {len(baseline)} regions, {total_mb:.0f}MB")

# Phase 2: Monitor loop (0.5s intervals, 30 seconds)
log("\nPhase 2: Monitoring (30s, 500ms intervals)")
log("Trigger the phone backup now!")

dumped = set()
prev_regions = dict(baseline)
start_time = time.time()

while time.time() - start_time < 30:
    time.sleep(0.5)

    # Current snapshot
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

    # Check for: 1) NEW regions, 2) GROWING regions
    for addr, size in current.items():
        if addr in baseline:
            old_size = baseline[addr]
        else:
            old_size = 0

        is_new = addr not in baseline
        has_grown = not is_new and size > old_size * 1.1  # >10% growth
        is_large_enough = size > 512 * 1024

        if (is_new or has_grown) and is_large_enough and addr not in dumped:
            # Check for message content
            try:
                data = pm.read_bytes(addr, min(size, 2*1024*1024))
                if data:
                    score = 0
                    for kw in [b'msgsource', b'wxid_', b'<msg', b'<des>']:
                        if kw in data: score += 1

                    if score >= 1:
                        ts = datetime.datetime.now().strftime('%H%M%S%f')[:8]
                        change_type = "NEW" if is_new else "GROWN"
                        growth = f"(was {old_size/1024/1024:.0f}MB, now {size/1024/1024:.0f}MB)" if has_grown else ""
                        fname = f"{change_type}_{ts}_{addr:x}_{size//1024//1024}MB.bin"
                        path = os.path.join(outdir, fname)
                        with open(path, 'wb') as f:
                            f.write(data[:min(len(data), 10*1024*1024)])

                        log(f"  [{change_type}] 0x{addr:x} {size/1024/1024:.0f}MB {growth} score={score} -> {fname}")
                        dumped.add(addr)
            except:
                pass

log(f"\nPhase 3: Complete")
log(f"Total captured: {len(dumped)} regions")
log(f"Files in {outdir}")

# Summary
import glob
files = sorted(glob.glob(os.path.join(outdir, '*.bin')))
log(f"\nSummary:")
log(f"  Total files: {len(files)}")
total_size = sum(os.path.getsize(f) for f in files) / 1024 / 1024
log(f"  Total size: {total_size:.0f}MB")

# Count test messages
import re
test_hits = {'RAY_TEST_BBB': 0, 'RAY_NODE': 0, 'PHONE_ONLY': 0, 'RAY_PAGE': 0}
for f in files:
    data = open(f, 'rb').read()
    for kw in test_hits:
        if kw.encode() in data:
            test_hits[kw] += 1

for kw, count in test_hits.items():
    log(f"  {kw}: {count} files")

log("Done.")
