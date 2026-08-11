"""
M93 — 查找消息容器 (vector<Message*>)
特征：3 个连续 QWORD (begin, end, capacity_end)
"""
import pymem, psutil, struct, json, os, time
import pymem.memory
from datetime import datetime

PID = 17292
outdir = r'C:\Users\OK\Desktop\wechat_v4_export_research\experiments\m93'
os.makedirs(outdir, exist_ok=True)

pm = pymem.Pymem(PID)
print(f"PID: {PID}")

def find_vectors(data, base_addr):
    """Find C++ vector patterns in memory buffer.
    Vector: [ptr begin] [ptr end] [ptr capacity_end]
    difference end-begin = element_count
    difference capacity_end-end = available capacity
    """
    vectors = []
    for off in range(0, len(data) - 24, 8):
        begin = struct.unpack('<Q', data[off:off+8])[0]
        end = struct.unpack('<Q', data[off+8:off+16])[0]
        cap = struct.unpack('<Q', data[off+16:off+24])[0]

        # All three must be in heap range
        heap_min = 0x150000000000
        heap_max = 0x200000000000

        if not (heap_min <= begin <= heap_max):
            continue
        if not (heap_min <= end <= heap_max):
            continue
        if not (heap_min <= cap <= heap_max):
            continue

        # begin <= end <= capacity_end (typical vector invariant)
        if not (begin <= end <= cap):
            continue

        element_size = end - begin
        if element_size == 0:
            continue

        # Element count
        count = element_size // 8  # pointer-sized elements

        if 0 < count < 10000:
            vectors.append({
                'addr': base_addr + off,
                'begin': begin,
                'end': end,
                'capacity': cap,
                'count': count,
                'element_size': element_size,
            })

    return vectors

# Phase 1: Find all vectors in heap
print("Phase 1: Finding C++ vectors in heap...")

all_vectors = []
for heap_start in [0x1a500000000, 0x1a520000000, 0x1a540000000, 0x1a560000000,
                    0x1a580000000, 0x1a5a0000000, 0x1a5c0000000]:
    try:
        data = pm.read_bytes(heap_start, 32*1024*1024)
        vectors = find_vectors(data, heap_start)
        all_vectors.extend(vectors)
        print(f"  Region 0x{heap_start:x}: {len(vectors)} vectors")
    except:
        continue

print(f"\nTotal vectors: {len(all_vectors)}")

# Phase 2: Filter for potential message containers
# Message containers would have:
# - Count > 5 (reasonable message count)
# - Element size = count * 8 (pointer array)
# - Each pointer points to a Message-like object
print(f"\nPhase 2: Filtering for message containers...")

message_containers = []
for v in all_vectors:
    if v['count'] < 3 or v['count'] > 5000:
        continue

    # Sample first pointer and check if it looks like an object
    try:
        first_ptr = struct.unpack('<Q', pm.read_bytes(v['begin'], 8))[0]
        # Check if it points to valid memory
        if first_ptr > 0x100000 and first_ptr < 0x7fffffffffff:
            # Read the potential object
            obj = pm.read_bytes(first_ptr, 32)
            # Check for vtable pointer (0x7fff... range)
            vtable = struct.unpack('<Q', obj[:8])[0]
            if 0x7ffc00000000 <= vtable <= 0x7fffffffffff:
                message_containers.append(v)
    except:
        continue

print(f"Potential message containers: {len(message_containers)}")
for v in message_containers[:20]:
    print(f"  0x{v['addr']:x}: count={v['count']}, first_ptr=0x{v['begin']:x}")

# Save for comparison later
snapshot = {
    'time': datetime.now().isoformat(),
    'vector_count': len(all_vectors),
    'candidates': len(message_containers),
    'sample_vectors': [{'addr': v['addr'], 'count': v['count']} for v in all_vectors[:100]],
}

with open(os.path.join(outdir, 'vector_snapshot.json'), 'w') as f:
    json.dump(snapshot, f, indent=2)
print(f"\nSnapshot saved")

# Phase 3: For the most promising containers, dump their pointers
if message_containers:
    print(f"\nPhase 3: Dumping top candidate pointers...")
    v = message_containers[0]
    ptrs = pm.read_bytes(v['begin'], v['count'] * 8)
    for i in range(min(v['count'], 50)):
        ptr = struct.unpack('<Q', ptrs[i*8:i*8+8])[0]
        # Try to identify this object
        try:
            obj = pm.read_bytes(ptr, 64)
            vtable = struct.unpack('<Q', obj[:8])[0]
            # Look for wxid patterns in the object
            obj_text = ''.join(chr(b) if 32 <= b < 127 else '.' for b in obj)
            has_wxid = 'wxid_' in obj_text
            print(f"  [{i}] 0x{ptr:x} vtable=0x{vtable:x} {'wxid!' if has_wxid else ''}")
            if has_wxid:
                print(f"        {obj_text[:60]}")
        except:
            print(f"  [{i}] 0x{ptr:x} (unreadable)")
