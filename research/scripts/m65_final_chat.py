"""
M65 — 最终聊天记录导出
- 从收藏文本中提取说话人
- 按会话分组 + 排序
- 输出一来一回格式
"""
import os, re, json, datetime
from collections import defaultdict

dump_dir = r'C:\Users\OK\Desktop\wechat_v4_export\experiments\m57_v3'
files = sorted(os.listdir(dump_dir))

all_msgs = []

for fname in files:
    data = open(os.path.join(dump_dir, fname), 'rb').read()
    txt = data.decode('utf-8', errors='replace')

    for m in re.finditer(r'<msg>.*?</msg>', txt, re.DOTALL):
        seg = m.group()
        msg = {}

        # Structured from/to
        fu = re.search(r'fromusername\s*=\s*"([^"]+)"', seg)
        if fu: msg['wxid'] = fu.group(1)
        tu = re.search(r'tousername\s*=\s*"([^"]+)"', seg)
        if tu: msg['to'] = tu.group(1)

        # type
        mt = re.search(r'<type>(.*?)</type>', seg)
        if mt:
            tval = mt.group(1)
            cd = re.search(r'<!\[CDATA\[(.*?)\]\]>', tval)
            if cd: tval = cd.group(1)
            try: msg['type'] = int(tval)
            except: pass

        # title/des
        for tag in ['title', 'des']:
            ts = re.search(f'<{tag}>(.*?)</{tag}>', seg, re.DOTALL)
            if ts:
                raw = ts.group(1)
                cd = re.search(r'<!\[CDATA\[(.*?)\]\]>', raw)
                if cd: raw = cd.group(1)
                msg[tag] = raw.strip()

        if msg.get('des'): msg['content'] = msg['des']
        elif msg.get('title'): msg['content'] = msg['title']
        else: continue

        # Timestamp
        for field in ['srcMsgCreateTime', 'createtime', 'sourcetime']:
            ts = re.search(f'<{field}>(\\d+)</{field}>', seg)
            if ts:
                val = int(ts.group(1))
                if 1500000000 < val < 1800000000:
                    msg['timestamp'] = val
                    msg['date'] = datetime.datetime.fromtimestamp(val).strftime('%Y-%m-%d %H:%M:%S')
                    break

        # Extract sender from content if no wxid
        if 'wxid' not in msg and msg.get('content'):
            first_line = msg['content'].split('\n')[0]
            colon = first_line.find(': ')
            if colon > 0 and colon < 30:
                potential_name = first_line[:colon].strip()
                # Must be a plausible name (not URL, not too long)
                if len(potential_name) >= 2 and '/' not in potential_name and potential_name != 'http':
                    msg['inferred_sender'] = potential_name

        all_msgs.append(msg)

# Dedup
seen = set()
unique = []
for m in all_msgs:
    k = m.get('content','')[:80]
    if k and k not in seen:
        seen.add(k)
        unique.append(m)

# Group by conversation TAG
# Use wxid/to/chatroom as conversation key
convos = defaultdict(list)
for m in unique:
    key = m.get('to') or m.get('wxid') or m.get('inferred_sender', 'unknown')
    convos[key].append(m)

# Sort each conversation by timestamp
for key in convos:
    convos[key].sort(key=lambda x: x.get('timestamp', 0))

print(f"Total: {len(unique)} msgs, {len(convos)} conversations", flush=True)

# Save per-conversation JSON
output = {}
for key, msgs in sorted(convos.items()):
    session_name = key[:40]
    output[session_name] = {
        'total': len(msgs),
        'messages': msgs
    }

with open(r'C:\Users\OK\Desktop\wechat_v4_export\m65_by_conversation.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

# Save readable chat format
with open(r'C:\Users\OK\Desktop\wechat_v4_export\m65_chat.txt', 'w', encoding='utf-8') as f:
    for session_name, session_data in sorted(output.items(), key=lambda x: len(x[1]['messages']), reverse=True):
        f.write(f"\n{'='*60}\n")
        f.write(f"【{session_name}】（{session_data['total']} 条）\n")
        f.write(f"{'='*60}\n")

        for m in session_data['messages'][:50]:  # limit per session for readability
            ts = m.get('date', '')
            sender = m.get('wxid') or m.get('inferred_sender', '')
            c = m.get('content', '')
            if sender:
                f.write(f"\n【{sender}】（{ts}）\n  {c}\n")
            else:
                f.write(f"\n（{ts}）\n  {c}\n")

print(f"Saved m65_by_conversation.json + m65_chat.txt", flush=True)
PYEOF