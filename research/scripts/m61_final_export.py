"""
M61 Final — 修复时间戳 + 按联系人分组导出
"""
import os, re, json, datetime
from collections import defaultdict

dump_dir = r'C:\Users\OK\Desktop\wechat_v4_export\experiments\m57_v3'
files = sorted(os.listdir(dump_dir))

all_msgs = []

for fname in files:
    data = open(os.path.join(dump_dir, fname), 'rb').read()

    i = 0
    while True:
        start = data.find(b'<msg', i)
        if start < 0: break
        end = data.find(b'</msg>', start)
        if end < 0: break

        seg = data[start:end+6]
        msg = {}

        # === fromusername / tousername ===
        for p in [b'fromusername="', b"fromusername='"]:
            pos = seg.find(p)
            if pos >= 0:
                vs = pos + len(p); ve = seg.find(b'"', vs)
                if ve > vs: msg['from'] = seg[vs:ve].decode('ascii', errors='ignore')
        for p in [b'tousername="', b"tousername='"]:
            pos = seg.find(p)
            if pos >= 0:
                vs = pos + len(p); ve = seg.find(b'"', vs)
                if ve > vs: msg['to'] = seg[vs:ve].decode('ascii', errors='ignore')

        # === type ===
        mt = re.search(rb'<type>(.*?)</type>', seg)
        if mt:
            tval = mt.group(1)
            cd = re.search(rb'<!\[CDATA\[(.*?)\]\]>', tval)
            if cd: tval = cd.group(1)
            try: msg['type'] = int(tval)
            except: pass

        # === title + des ===
        for tag in [b'<title>', b'<des>']:
            ts = seg.find(tag)
            if ts >= 0:
                te = seg.find(b'</' + tag[1:], ts)
                if te > ts:
                    raw = seg[ts+len(tag):te]
                    if raw[:9] == b'<![CDATA[':
                        cde = raw.find(b']]>')
                        if cde > 0: raw = raw[9:cde]
                    try: text = raw.decode('utf-8')
                    except: text = raw.decode('utf-8', errors='replace')
                    if tag == b'<title>': msg['title'] = text
                    else: msg['des'] = text

        # === content ===
        if msg.get('des'): msg['content'] = msg['des']
        elif msg.get('title'): msg['content'] = msg['title']

        # === Timestamp: find the LONGEST 10-digit number (most likely actual timestamp) ===
        candidates = []
        for m in re.finditer(rb'(1[5-7]\d{8})', seg):
            val = int(m.group(1))
            if 1500000000 < val < 1800000000:  # 2017~2027
                candidates.append(val)

        # Also try 13-digit ms timestamps
        for m in re.finditer(rb'(1[5-7]\d{11})', seg):
            val = int(m.group(1))
            if 1500000000000 < val < 1800000000000:
                candidates.append(val // 1000)

        if candidates:
            # Use the most reasonable one (closest to 2025)
            msg['timestamp'] = min(candidates, key=lambda x: abs(x - 1700000000))
            try:
                msg['date'] = datetime.datetime.fromtimestamp(msg['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
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

# === Group by conversation ===
convos = defaultdict(list)
for m in unique:
    # Determine conversation key
    fr = m.get('from', '')
    to = m.get('to', '')

    # Try to extract sender from content for type 19 (chat records)
    if not fr and m.get('type') == 19 and m.get('content'):
        first_line = m['content'].split('\n')[0].split(':')[0]
        if first_line and len(first_line) < 20:
            m['detected_sender'] = first_line.strip()

    convo_key = fr or to or 'unknown'
    convos[convo_key].append(m)

# Save full JSON
with open(r'C:\Users\OK\Desktop\wechat_v4_export\m61_final.json', 'w', encoding='utf-8') as f:
    json.dump({
        'total': len(unique),
        'conversations': len(convos),
        'msgs': unique
    }, f, ensure_ascii=False, indent=2)

# Save conversation-grouped chat
with open(r'C:\Users\OK\Desktop\wechat_v4_export\m61_chat.txt', 'w', encoding='utf-8') as f:
    f.write(f"共 {len(unique)} 条消息，{len(convos)} 个会话\n\n")

    for convo_key in sorted(convos.keys()):
        msgs = sorted(convos[convo_key], key=lambda m: m.get('timestamp', 0))

        # Skip very small conversations
        if len(msgs) < 1:
            continue

        f.write(f"\n{'='*60}\n")
        f.write(f"【{convo_key}】（{len(msgs)} 条）\n")
        f.write(f"{'='*60}\n")

        for m in msgs:
            ts = m.get('date', '')
            c = m.get('content', '')
            t = m.get('type', '?')
            fr = m.get('from', '')
            to = m.get('to', '')

            if fr:
                f.write(f"\n【{fr}】（{ts}）\n  {c}\n")
            elif to:
                f.write(f"\n【{to}】（{ts}）\n  {c}\n")
            else:
                f.write(f"\n[{t}]（{ts}）\n  {c}\n")

print(f"Total: {len(unique)} msgs, {len(convos)} conversations", flush=True)
print(f"Saved to m61_final.json + m61_chat.txt", flush=True)
