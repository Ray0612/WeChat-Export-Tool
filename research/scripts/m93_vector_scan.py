"""
M93 — 逐区域扫描 heap 找 C++ vector<Message*> 模式
"""
import pymem, psutil, struct, json, os, time
import pymem.memory

PID = 17292
pm = pymem.Pymem(PID)
outdir = r'C:\Users\OK\Desktop\wechat_v4_export_research\experiments\m93'
os.makedirs(outdir, exist_ok=True)

print(f"PID: {PID}")
print("Scanning all heap regions for vectors...")

# Collect all private writable regions
regions = []
base = 0x100000
while base < 0x7fffffffffff:
    try:
        mbi = pymem.memory.virtual_query(pm.process_handle, base)
        if mbi.State == 0x1000 and mbi.Type == 0x20000 and mbi.RegionSize > 256:
            regions.append((base, mbi.RegionSize))
        base += mbi.RegionSize if mbi.RegionSize > 0 else 0x10000
    except:
        base += 0x10000

print(f"Total regions: {len(regions)}")

# Search each region for vector patterns
vectors_found = []
scanned = 0

for rbase, rsize in regions:
    try:
        data = pm.read_bytes(rbase, min(rsize, 65536))
    except:
        continue

    scanned += 1
    if scanned % 500 == 0:
        print(f"  scanned {scanned}/{len(regions)}...")

    for off in range(0, len(data) - 24, 8):
        begin = struct.unpack('<Q', data[off:off+8])[0]
        end = struct.unpack('<Q', data[off+8:off+16])[0]
        cap = struct.unpack('<Q', data[off+16:off+24])[0]

        # Quick sanity: heap pointers
        if not (0x150000000000 <= begin <= 0x200000000000):
            continue
        if not (0x150000000000 <= end <= 0x200000000000):
            continue

        # begin <= end <= cap
        if not (begin <= end <= cap):
            continue

        count = (end - begin) // 8
        if count < 2 or count > 50000:
            continue

        vectors_found.append({
            'addr': rbase + off,
            'begin': begin,
            'end': end,
            'cap': cap,
            'count': count,
        })

print(f"\nTotal vectors found: {len(vectors_found)}")

# Filter: vectors with count > 10 (likely message containers)
significant = [v for v in vectors_found if v['count'] > 10]
print(f"Significant (count>10): {len(significant)}")

if significant:
    print(f"\nTop candidates by count:")
    significant.sort(key=lambda v: -v['count'])
    for v in significant[:30]:
        # Sample each pointer to check for vtable patterns
        try:
            first_ptr = struct.unpack('<Q', pm.read_bytes(v['begin'], 8))[0]
            obj = pm.read_bytes(first_ptr, 16)
            vtable = struct.unpack('<Q', obj[:8])[0]
            has_vtable = 0x7ff000000000 <= vtable <= 0x7fffffffffff
            text = ''.join(chr(b) if 32 <= b < 127 else '.' for b in obj)
        except:
            has_vtable = False
            text = ''

        marker = ' [vtable]' if has_vtable else ''
        print(f"  0x{v['addr']:x}: count={v['count']} begin=0x{v['begin']:x}{marker} {text[:30]}")
else:
    print("No significant vectors found - trying different count thresholds...")

# Also look for any valid vector pattern with different thresholds
for min_count in [1, 3, 5, 8]:
    subset = [v for v in vectors_found if v['count'] >= min_count]
    if subset:
        print(f"\nVectors with count>={min_count}: {len(subset)}")
        break

# Save results
output = {
    'total_vectors': len(vectors_found),
    'significant': [dict(v) for v in vectors_found if v['count'] > 5][:100],
}
with open(os.path.join(outdir, 'vectors.json'), 'w') as f:
    json.dump(output, f, indent=2, default=str)
print(f"\nSaved to {outdir}/vectors.json")
print("Done")
