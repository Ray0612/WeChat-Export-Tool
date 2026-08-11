"""
M36 — Export using new compact structure format
Prefix: XX 02 05 09 01 01 04 (XX varies, was 1b in old version)
Entry: prefix + content + 04 + seq(2B) + s_tag(8B) + header(8B+) + padding
"""
import pymem, psutil, struct, json, os, datetime

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

pm = pymem.Pymem()
pm.open_process_from_id(target_pid)
print(f'PID={target_pid}', flush=True)

outfile = r'C:\Users\OK\Desktop\wechat_v4_export\m36_export.json'
os.makedirs(os.path.dirname(outfile), exist_ok=True)

# Scan for prefix pattern
prefix_core = bytes([0x02, 0x05, 0x09, 0x01, 0x01, 0x04])
messages = []
seen = set()

print('Scanning for compact structure entries...', flush=True)

# Scan heap
base = 0x21d00000000
while base < 0x21d80000000:
    try:
        mbi = pymem.memory.virtual_query(pm.process_handle, base)
        if mbi.State == 0x1000 and mbi.Protect & 0x10 == 0:
            size = min(mbi.RegionSize, 2*1024*1024)
            data = pm.read_bytes(base, size)
            if data:
                pos = -1
                while True:
                    pos = data.find(prefix_core, pos + 1)
                    if pos < 0: break
                    prefix_start = base + pos - 1  # Including the variable byte

                    # Entry starts after prefix (7 bytes total)
                    entry_start = prefix_start + 7

                    # Read the entry
                    try:
                        entry_data = pm.read_bytes(entry_start, 60)
                    except:
                        continue

                    # Content starts at entry_start, ends at 0x04
                    sep_pos = entry_data.find(b'\x04', 1)
                    if sep_pos < 2 or sep_pos > 40:
                        continue

                    content = entry_data[0:sep_pos]

                    # Decode content (UTF-8)
                    try:
                        text = content.decode('utf-8', errors='replace')
                    except:
                        text = content.decode('ascii', errors='replace')

                    # Filter out garbage (must have sufficient printable chars)
                    printable = sum(1 for c in text if ' ' <= c <= '~' or ord(c) >= 0x80)
                    if len(text) < 3 or printable < len(text) * 0.5:
                        continue

                    # Sequence
                    seq = struct.unpack_from('<H', entry_data, sep_pos + 1)[0]

                    # Session tag
                    s_tag = entry_data[sep_pos + 3:sep_pos + 11].hex()

                    # Skip duplicates
                    sig = f'{seq}_{text[:20]}'
                    if sig in seen:
                        continue
                    seen.add(sig)

                    messages.append({
                        'seq': seq,
                        'text': text,
                        'tag': s_tag,
                        'addr': hex(entry_start),
                    })
        base += mbi.RegionSize if mbi.RegionSize > 0 else 0x10000
    except:
        base += 0x10000

# Deduplicate by sequence
by_seq = {}
for m in messages:
    seq = m['seq']
    if seq not in by_seq or len(m['text']) > len(by_seq[seq]['text']):
        by_seq[seq] = m

sorted_msgs = sorted(by_seq.values(), key=lambda m: m['seq'])

# Filter: only keep messages with reasonable content
real_msgs = [m for m in sorted_msgs if len(m['text']) >= 3 and not all(c in '0123456789' for c in m['text'])]

print(f'Total entries: {len(messages)}', flush=True)
print(f'Unique by seq: {len(sorted_msgs)}', flush=True)
print(f'Real messages: {len(real_msgs)}', flush=True)
print()

for m in real_msgs[:30]:
    safe = m["text"][:50].encode('ascii', errors='replace').decode('ascii')
    print(f'  #{m["seq"]}: tag={m["tag"]} "{safe}"', flush=True)

# Save
with open(outfile, 'w', encoding='utf-8') as f:
    json.dump(real_msgs, f, ensure_ascii=False, indent=2)

print(f'\n输出: {outfile}', flush=True)
