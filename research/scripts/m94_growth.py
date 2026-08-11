"""
M94 实验1 — 消息增长实验
先拍快照→用户发消息→对比发现增长对象
"""
import pymem, psutil, struct, json, os, time, sys
import pymem.memory
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

PID = 17292
pm = pymem.Pymem(PID)
outdir = r'C:\Users\OK\Desktop\wechat_v4_export_research\experiments\m94'
os.makedirs(outdir, exist_ok=True)

def snapshot_vectors():
    """Quick scan for vectors (begin/end/cap) with count > 5"""
    vectors = {}
    base = 0x1a500000000
    end = 0x1a600000000

    while base < end:
        try:
            mbi = pymem.memory.virtual_query(pm.process_handle, base)
            if mbi.State == 0x1000 and mbi.RegionSize <= 65536:
                data = pm.read_bytes(base, mbi.RegionSize)
                for off in range(0, len(data)-24, 8):
                    b = struct.unpack('<Q', data[off:off+8])[0]
                    e = struct.unpack('<Q', data[off+8:off+16])[0]
                    c = struct.unpack('<Q', data[off+16:off+24])[0]
                    if not (0x1a500000000 <= b <= 0x1a600000000):
                        continue
                    if not (b <= e <= c):
                        continue
                    count = (e-b)//8
                    if 5 <= count <= 50000:
                        vectors[base+off] = count
            base += mbi.RegionSize if mbi.RegionSize > 0 else 0x10000
        except:
            base += 0x10000
    return vectors

print("=" * 60)
print("M94 增长实验")
print("=" * 60)
print(f"\nPID: {PID}")
print("Phase 1: Baseline snapshot...")
before = snapshot_vectors()
print(f"  Vectors before: {len(before)}")

# Save baseline
with open(os.path.join(outdir, 'vector_baseline.json'), 'w') as f:
    json.dump({hex(k):v for k,v in before.items()}, f, indent=2)

total_before = sum(before.values())
print(f"  Total element count: {total_before}")

print(f"\n现在发送消息: M93_A")
input("发送完后按 Enter 继续...")

print("Phase 2: After M93_A...")
after_a = snapshot_vectors()
new_a = {k:v for k,v in after_a.items() if k not in before}
grown_a = {k:v for k,v in after_a.items() if k in before and v != before[k]}
print(f"  New vectors: {len(new_a)}")
print(f"  Grown vectors: {len(grown_a)}")

for addr, count in sorted(new_a.items(), key=lambda x: -x[1])[:5]:
    print(f"  NEW 0x{addr:x}: count={count}")
for addr, count in sorted(grown_a.items(), key=lambda x: -(x[1]-before[x]))[:5]:
    delta = count - before[addr]
    print(f"  GROWN 0x{addr:x}: {before[addr]}→{count} (+{delta})")

# Check message cache area specifically
print(f"\nPhase 3: Checking message cache region...")
cache_addrs = [0x1a525f217f7, 0x1a5260cc6ec, 0x1a527225eec]
for ca in cache_addrs:
    ctx = pm.read_bytes(ca-16, 64)
    asc = ''.join(chr(b) if 32 <= b < 127 else '.' for b in ctx)
    print(f"  0x{ca:x}: {asc}")

print(f"\nDone.")
