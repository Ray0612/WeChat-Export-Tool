"""
M59 Full — 全量解析 162 个 dump 文件
输出结构化聊天数据 JSON
"""
import os, re, json, time

dump_dir = r'C:\Users\OK\Desktop\wechat_v4_export\experiments\m57_v3'
outdir = r'C:\Users\OK\Desktop\wechat_v4_export'
files = sorted(os.listdir(dump_dir))

print(f"Total files: {len(files)}", flush=True)

all_messages = []
total_bytes = 0

for idx, fname in enumerate(files):
    path = os.path.join(dump_dir, fname)
    data = open(path, 'rb').read()
    total_bytes += len(data)

    # Extract all XML messages with <msg>...</msg>
    i = 0
    while True:
        start = data.find(b'<msg', i)
        if start < 0: break
        end = data.find(b'</msg>', start)
        if end > 0:
            seg = data[start:end+6]
            try:
                txt = seg.decode('utf-8', errors='replace')

                msg = {
                    'file': fname,
                    'offset': start,
                    'raw': txt[:2000],  # truncate for storage
                }

                # Extract wxid
                wxids = re.findall(r'wxid_[a-zA-Z0-9_]+', txt)
                if wxids:
                    msg['wxids'] = list(set(wxids))

                # Extract msgsource
                ms = re.search(r'<msgsource>.*?</msgsource>', txt)
                if ms:
                    msg['msgsource'] = ms.group()

                # Extract title/des (content)
                title = re.search(r'<title>(.*?)</title>', txt)
                if title:
                    msg['title'] = title.group(1)

                des = re.search(r'<des>(.*?)</des>', txt)
                if des:
                    msg['des'] = des.group(1)

                # Extract type
                mtype = re.search(r'<type>(\d+)</type>', txt)
                if mtype:
                    msg['type'] = int(mtype.group(1))

                # Extract aeskey (image key)
                aes = re.search(r'aeskey="([^"]+)"', txt)
                if aes:
                    msg['aeskey'] = aes.group(1)

                # Extract url
                url = re.search(r'<url>(.*?)</url>', txt)
                if url:
                    msg['url'] = url.group(1)

                # Determine content (best guess)
                if 'des' in msg and msg['des'].strip():
                    msg['content'] = msg['des']
                elif 'title' in msg and msg['title'].strip():
                    msg['content'] = msg['title']

                all_messages.append(msg)
            except:
                pass
            i = end + 6
        else:
            i = start + 4

    if (idx + 1) % 20 == 0:
        print(f"  [{idx+1}/{len(files)}] {len(all_messages)} msgs found", flush=True)

# Deduplicate by content
seen = set()
unique_msgs = []
for m in all_messages:
    key = m.get('content', '')[:50]
    if key and key not in seen:
        seen.add(key)
        unique_msgs.append(m)

print(f"\n=== Results ===", flush=True)
print(f"Files: {len(files)}", flush=True)
print(f"Total size: {total_bytes/1024/1024:.0f}MB", flush=True)
print(f"Raw XML msgs: {len(all_messages)}", flush=True)
print(f"Unique msgs: {len(unique_msgs)}", flush=True)

# Count types
from collections import Counter
types = Counter(m.get('type', 0) for m in unique_msgs)
print(f"\nBy type:", flush=True)
for t, c in types.most_common():
    print(f"  type {t}: {c}", flush=True)

# Count wxid references
wxid_count = Counter()
for m in unique_msgs:
    for w in m.get('wxids', []):
        wxid_count[w] += 1
print(f"\nTop wxid:", flush=True)
for w, c in wxid_count.most_common(5):
    print(f"  {w}: {c}", flush=True)

# Sample messages with content
with_content = [m for m in unique_msgs if m.get('content')]

# Save BEFORE printing (in case of encoding errors)
output = {
    'total_files': len(files),
    'total_size_mb': total_bytes/1024/1024,
    'total_raw_msgs': len(all_messages),
    'total_unique_msgs': len(unique_msgs),
    'msgs': unique_msgs,
}

json_path = os.path.join(outdir, 'm59_all_messages.json')
with open(json_path, 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

# Also save a compact version (content only)
txt_path = os.path.join(outdir, 'm59_all_content.txt')
with open(txt_path, 'w', encoding='utf-8') as f:
    for m in with_content:
        c = m.get('content', '')
        w = ','.join(m.get('wxids', []))
        t = m.get('type', 0)
        f.write(f"[{t}] {w}: {c}\n")

print(f"\nSaved:", flush=True)
print(f"  {json_path}", flush=True)
print(f"  {txt_path}", flush=True)
