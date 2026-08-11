"""
M61 Phase 1 — 完善解析器
修复乱码 + 完整 from/to + 优化输出
"""
import os, re, json, datetime
from collections import Counter

dump_dir = r'C:\Users\OK\Desktop\wechat_v4_export\experiments\m57_v3'
files = sorted(os.listdir(dump_dir))

def clean_text(text):
    """修复编码问题：LevelDB 存储的文本可能是 GBK 编码"""
    if not text:
        return ''
    # The text has already been decoded as UTF-8 with errors='replace'
    # We need to re-encode the replacement chars and try GBK
    # Check if there are replacement characters
    if '�' in text:
        # Re-encode the raw bytes that produced this and try GBK
        try:
            # Get the raw bytes from the original data
            return text.encode('latin-1').decode('gbk', errors='replace')
        except:
            pass
    return text.strip()

def extract_field(seg, pattern, use_cdata=True):
    """Extract field with optional CDATA handling"""
    if use_cdata:
        m = re.search(r'<' + pattern + r'><\!\[CDATA\[(.*?)\]\]></' + pattern + r'>', seg)
        if m:
            return m.group(1)
    m = re.search(r'<' + pattern + r'>(.*?)</' + pattern + r'>', seg)
    if m:
        return m.group(1)
    return ''

all_msgs = []
for fname in files:
    data = open(os.path.join(dump_dir, fname), 'rb').read()
    txt = data.decode('utf-8', errors='replace')

    i = 0
    while True:
        start = txt.find('<msg', i)
        if start < 0: break

        # Find the actual end — check for both </msg> and self-closing
        end = txt.find('</msg>', start)
        if end < 0:
            i = start + 4
            continue

        seg = txt[start:end+6]

        msg = {}

        # 1. fromusername / tousername — check in ALL parts of the msg
        for p in [r'fromusername\s*=\s*"([^"]+)"', r'fromusername=' + "'([^']+)'"]:
            m = re.search(p, seg)
            if m: msg['from'] = m.group(1)

        for p in [r'tousername\s*=\s*"([^"]+)"', r'tousername=' + "'([^']+)'"]:
            m = re.search(p, seg)
            if m: msg['to'] = m.group(1)

        # 2. msg type
        mt = re.search(r'<type>(\d+)</type>', seg)
        if mt: msg['type'] = int(mt.group(1))

        # 3. title + des with CDATA support
        title = extract_field(seg, 'title')
        des = extract_field(seg, 'des')

        # 4. content
        if des:
            msg['content'] = des
        elif title:
            msg['content'] = title

        # 5. Clean content
        if msg.get('content'):
            msg['content_clean'] = clean_text(msg['content'])

        # 6. msgsource
        ms = re.search(r'<msgsource>(.*?)</msgsource>', seg)
        if ms: msg['msgsource'] = ms.group(1)

        # 7. Timestamp
        for ts_str in re.findall(r'(1[5-7]\d{8})', seg):
            ts_int = int(ts_str)
            if 1500000000 < ts_int < 2000000000:
                msg['timestamp'] = ts_int
                msg['timestamp_str'] = datetime.datetime.fromtimestamp(ts_int).strftime('%Y-%m-%d %H:%M:%S')
                break

        # 8. type
        if 'type' not in msg:
            mt2 = re.search(r'<type[^>]*>(.*?)</type>', seg)
            if mt2:
                tval = mt2.group(1)
                tval = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', tval)
                try:
                    msg['type'] = int(tval)
                except:
                    pass

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

# Stats
print(f"Raw: {len(all_msgs)}, Unique: {len(unique)}", flush=True)
print(f"With timestamp: {sum(1 for m in unique if 'timestamp' in m)}", flush=True)
print(f"With from: {sum(1 for m in unique if 'from' in m)}", flush=True)
print(f"With to: {sum(1 for m in unique if 'to' in m)}", flush=True)

# Show clean samples
print(f"\n=== Clean content samples ===", flush=True)
with_clean = [m for m in unique if m.get('content_clean') and len(m['content_clean']) > 5]
for m in with_clean[:20]:
    ts = m.get('timestamp_str','')
    fr = m.get('from','?')
    to = m.get('to','?')
    c = m['content_clean'][:80]
    t = m.get('type','?')
    print(f"  [{t}] {fr}->{to} @{ts}: {c}", flush=True)

# Messages with from/to
print(f"\n=== Messages with sender/receiver ===", flush=True)
for m in unique:
    if m.get('from'):
        ts = m.get('timestamp_str','')
        c = m.get('content_clean', m.get('content',''))[:80]
        t = m.get('type','?')
        print(f"  [{t}] {m['from']} -> {m.get('to','?')} @{ts}: {c}", flush=True)

# Save
with open(r'C:\Users\OK\Desktop\wechat_v4_export\m61_clean.json', 'w', encoding='utf-8') as f:
    json.dump(unique, f, ensure_ascii=False, indent=2)
print(f"\nSaved to m61_clean.json", flush=True)
