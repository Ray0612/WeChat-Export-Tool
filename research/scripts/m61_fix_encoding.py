"""
M61 — 修复中文乱码：在字节层面用 GBK 解码
"""
import os, re, json, datetime
from collections import Counter

dump_dir = r'C:\Users\OK\Desktop\wechat_v4_export\experiments\m57_v3'
files = sorted(os.listdir(dump_dir))

def extract_bytes(data, start_tag, end_tag=b'</'):
    """Extract content between tags from raw bytes, try GBK then UTF-8"""
    start = data.find(start_tag)
    if start < 0: return '', data
    start += len(start_tag)
    # Skip any whitespace/CDATA prefix
    if data[start:start+9] == b'<![CDATA[':
        start += 9
        end = data.find(b']]>', start)
    else:
        end_tag_full = end_tag + start_tag[1:].split(b'>')[0] + b'>' if b'>' in start_tag else end_tag
        # Find matching closing tag
        tag_name = start_tag[1:].split(b'>')[0].split(b' ')[0] if b' ' in start_tag[1:] else start_tag[1:-1]
        end_tag_bytes = b'</' + tag_name + b'>'
        end = data.find(end_tag_bytes, start)

    if end < 0: return '', data

    raw = data[start:end]

    # Try GBK first, then UTF-8
    for enc in ['gbk', 'utf-8']:
        try:
            text = raw.decode(enc)
            return text, data[end:]
        except:
            continue

    # Fallback: latin-1 (never fails)
    text = raw.decode('latin-1', errors='replace')
    return text, data[end:]

all_msgs = []
for fname in files:
    raw_data = open(os.path.join(dump_dir, fname), 'rb').read()

    # Split into segments at <msg boundaries
    i = 0
    while True:
        start = raw_data.find(b'<msg', i)
        if start < 0: break
        end = raw_data.find(b'</msg>', start)
        if end < 0: break

        seg = raw_data[start:end+6]

        msg = {}

        # fromusername / tousername (always ASCII safe)
        for p in [b'fromusername="', b"fromusername='"]:
            pos = seg.find(p)
            if pos >= 0:
                val_start = pos + len(p)
                val_end = seg.find(b'"', val_start)
                if val_end > val_start:
                    msg['from'] = seg[val_start:val_end].decode('ascii', errors='ignore')

        for p in [b'tousername="', b"tousername='"]:
            pos = seg.find(p)
            if pos >= 0:
                val_start = pos + len(p)
                val_end = seg.find(b'"', val_start)
                if val_end > val_start:
                    msg['to'] = seg[val_start:val_end].decode('ascii', errors='ignore')

        # title (use GBK decode)
        title, _ = extract_bytes(seg, b'<title>')
        des, _ = extract_bytes(seg, b'<des>')

        # type
        mt = re.search(rb'<type>(.*?)</type>', seg)
        if mt:
            tval = mt.group(1)
            # Handle CDATA
            cdata = re.search(rb'<!\[CDATA\[(.*?)\]\]>', tval)
            if cdata: tval = cdata.group(1)
            try:
                msg['type'] = int(tval)
            except:
                pass

        # content
        if des:
            msg['content'] = des
        elif title:
            msg['content'] = title

        # msgsource
        ms = re.search(rb'<msgsource>(.*?)</msgsource>', seg)
        if ms:
            msg['msgsource'] = ms.group(1).decode('ascii', errors='ignore')

        # Timestamp
        for match in re.finditer(rb'(1[5-7]\d{8})', seg):
            ts_int = int(match.group(1))
            if 1500000000 < ts_int < 2000000000:
                msg['timestamp'] = ts_int
                msg['timestamp_str'] = datetime.datetime.fromtimestamp(ts_int).strftime('%Y-%m-%d %H:%M:%S')
                break

        if msg.get('content'):
            all_msgs.append(msg)

        i = end + 6

# Dedup
seen = set()
unique = []
for m in all_msgs:
    k = m.get('content','')[:80]
    if k and k not in seen:
        seen.add(k)
        unique.append(m)

print(f"Raw: {len(all_msgs)}, Unique: {len(unique)}", flush=True)
print(f"With timestamp: {sum(1 for m in unique if 'timestamp' in m)}", flush=True)
print(f"With from: {sum(1 for m in unique if 'from' in m)}", flush=True)
print(f"With to: {sum(1 for m in unique if 'to' in m)}", flush=True)

# Show samples
print(f"\n=== Samples ===", flush=True)
for m in unique[:30]:
    ts = m.get('timestamp_str','')
    fr = m.get('from','?')
    to = m.get('to','?')
    c = m.get('content','')[:80]
    t = m.get('type','?')
    # Safe print
    safe = ''.join(ch if ord(ch) < 128 or 0x4e00 <= ord(ch) <= 0x9fff else '?' for ch in c)
    print(f"  [{t}] {fr}->{to} @{ts}: {safe}", flush=True)

# Save
with open(r'C:\Users\OK\Desktop\wechat_v4_export\m61_gbk_fixed.json', 'w', encoding='utf-8') as f:
    json.dump(unique, f, ensure_ascii=False, indent=2)
print(f"\nSaved to m61_gbk_fixed.json", flush=True)
