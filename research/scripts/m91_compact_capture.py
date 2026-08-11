"""
M91 — 紧凑结构捕获器
搜索 Weixin.exe 内存中的 02 05 09 01 01 04 前缀结构
提取内联文本、session tag、seq
"""
import pymem, psutil, struct, datetime, re, os, time
import pymem.memory

PID = 6312
pm = pymem.Pymem(PID)
outdir = r'C:\Users\OK\Desktop\wechat_v4_export_research\experiments\m91'
os.makedirs(outdir, exist_ok=True)

print(f"M91 — Compact Structure Capture")
print(f"PID: {PID}")

# Phase 1: Find all compact structures
print("\nPhase 1: Scanning for 02 05 09 01 01 04 prefix...")

compact_structs = []
base = 0x100000
scanned = 0

while base < 0x7fffffffffff:
    try:
        mbi = pymem.memory.virtual_query(pm.process_handle, base)
        if mbi.State == 0x1000 and mbi.Protect in [0x04, 0x20] and mbi.RegionSize <= 65536:
            try:
                data = pm.read_bytes(base, min(mbi.RegionSize, 32768))
                off = 0
                while True:
                    pos = data.find(b'\x02\x05\x09\x01\x01\x04', off)
                    if pos == -1:
                        break

                    abs_addr = base + pos

                    # Read the compact structure (up to 256 bytes)
                    struct_data = pm.read_bytes(abs_addr, 256)

                    # Parse: after the 7B prefix, content is UTF-8 until 0x04
                    content_start = 7  # prefix bytes
                    content_end = struct_data.find(b'\x04', content_start)

                    if content_end > content_start:
                        content = struct_data[content_start:content_end].decode('utf-8', errors='replace')

                        # After content: 0x04 + 2B seq + session tag
                        seq_pos = content_end + 1
                        seq = struct.unpack('<H', struct_data[seq_pos:seq_pos+2])[0] if seq_pos + 2 <= len(struct_data) else 0

                        # Session tag (~8 bytes after seq)
                        tag_start = seq_pos + 2
                        tag = struct_data[tag_start:tag_start+8].hex() if tag_start + 8 <= len(struct_data) else ''

                        compact_structs.append({
                            'addr': abs_addr,
                            'content': content,
                            'seq': seq,
                            'tag': tag,
                        })
                    off = pos + 1
            except:
                pass
        base += mbi.RegionSize if mbi.RegionSize > 0 else 0x10000
    except:
        base += 0x10000

print(f"  Found {len(compact_structs)} compact structures")

# Phase 2: Dedup and group by session
seen = set()
unique = []
for cs in compact_structs:
    key = f"{cs['content'][:60]}|{cs['seq']}"
    if key not in seen:
        seen.add(key)
        unique.append(cs)

print(f"  Unique: {len(unique)}")

# Phase 3: Sort by seq and show
unique.sort(key=lambda x: x['seq'])

print(f"\nPhase 2: Messages by seq")
print(f"{'seq':>6} {'content':60s} {'tag':20s} {'addr':16s}")
print("-" * 110)
for cs in unique[:50]:
    content_preview = cs['content'][:60]
    print(f"{cs['seq']:>6} {content_preview:60s} {cs['tag'][:20]:20s} 0x{cs['addr']:x}")

# Phase 4: Save output
import json
output = {
    'total': len(unique),
    'compact_structs': [{
        'addr': hex(cs['addr']),
        'content': cs['content'],
        'seq': cs['seq'],
        'tag': cs['tag'],
    } for cs in unique],
}

with open(os.path.join(outdir, 'm91_compact_output.json'), 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"\nSaved to m91_compact_output.json")
print(f"Done!")
