"""
M59 — 解析 Chromium LevelDB dump 文件中的 XML 消息
"""
import os, re, json
from xml.etree import ElementTree

dump_dir = r'C:\Users\OK\Desktop\wechat_v4_export\experiments\m57_v3'
outfile = r'C:\Users\OK\Desktop\wechat_v4_export\m59_messages.json'

files = sorted(os.listdir(dump_dir))
print(f"共 {len(files)} 个 dump 文件", flush=True)

all_chinese = []
all_xml = []
total_size = 0

for fname in files:
    path = os.path.join(dump_dir, fname)
    data = open(path, 'rb').read()
    total_size += len(data)

    # Method 1: Extract <msg>...</msg> XML (binary safe)
    i = 0
    while True:
        start = data.find(b'<msg', i)
        if start < 0: break
        # Find the closing </msg> or > (self-closing)
        end_tag = data.find(b'</msg>', start)
        end_self = data.find(b'/>', start)

        if end_tag > 0 and (end_self < 0 or end_tag < end_self):
            end = end_tag + 6  # include </msg>
        elif end_self > 0:
            end = end_self + 2
        else:
            i = start + 4
            continue

        xml_seg = data[start:end]
        try:
            text = xml_seg.decode('utf-8', errors='replace')
            if len(text) > 20 and any(k in text for k in ['wxid_', 'msgsource', 'content']):
                all_xml.append(text[:500])
        except:
            pass
        i = end

    # Method 2: Scan for Chinese text content
    for off in range(len(data) - 6):
        c = data[off]
        if 0xE4 <= c <= 0xE9:  # Chinese UTF-8 start bytes
            try:
                for end in range(off + 6, min(off + 200, len(data)), 3):
                    text = data[off:end].decode('utf-8')
                    if len(text) >= 8 and sum(1 for ch in text if 0x4e00 <= ord(ch) <= 0x9fff) >= 4:
                        # Clean up: remove HTML tags
                        clean = re.sub(r'<[^>]+>', '', text)
                        if len(clean) >= 8 and clean not in [c[1] for c in all_chinese[-5:]]:
                            all_chinese.append((fname, off, clean.strip()))
                        break
            except:
                pass

print(f"扫描完成: {total_size/1024/1024:.0f}MB", flush=True)
print(f"XML 片段: {len(all_xml)}", flush=True)
print(f"中文文本: {len(all_chinese)}", flush=True)

# Show XML samples (safe chars only)
print(f"\n=== XML 消息样例 ===", flush=True)
for x in all_xml[:5]:
    safe = ''.join(c if ord(c) < 128 or 0x4e00 <= ord(c) <= 0x9fff else '.' for c in x[:150])
    print(f"  {safe}", flush=True)

# Show Chinese text samples (safe chars only)
print(f"\n=== 中文文本样例 ===", flush=True)
for fname, off, text in all_chinese[:20]:
    safe = ''.join(c if ord(c) < 128 or 0x4e00 <= ord(c) <= 0x9fff else '.' for c in text[:60])
    print(f"  [{fname[:20]}] +{off:x}: {safe}", flush=True)

# Save all Chinese text to file
with open(r'C:\Users\OK\Desktop\wechat_v4_export\m59_chinese_texts.txt', 'w', encoding='utf-8') as f:
    for fname, off, text in all_chinese:
        f.write(f"[{fname}] +{off:x}: {text}\n")

# Save XML to JSON
with open(outfile, 'w', encoding='utf-8') as f:
    json.dump(all_xml, f, ensure_ascii=False, indent=2)

print(f"\n输出:", flush=True)
print(f"  XML: {outfile} ({len(all_xml)} 条)", flush=True)
print(f"  中文: m59_chinese_texts.txt ({len(all_chinese)} 条)", flush=True)
