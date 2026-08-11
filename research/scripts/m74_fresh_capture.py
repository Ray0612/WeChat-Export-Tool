"""
M74 — 全新捕获+全量解析管线
从捕获到GUI一条龙
"""
import pymem, psutil, time, os, datetime, json, re
from collections import defaultdict

PID = 6312
pm = pymem.Pymem()
pm.open_process_from_id(PID)

outdir = r'C:\Users\OK\Desktop\wechat_v4_export_research\experiments\m74_fresh'
os.makedirs(outdir, exist_ok=True)

# === Phase 1: Baseline ===
baseline = {}
base = 0x100000
while base < 0x7fffffffffff:
    try:
        mbi = pymem.memory.virtual_query(pm.process_handle, base)
        if mbi.State == 0x1000: baseline[base] = mbi.RegionSize
        base += mbi.RegionSize if mbi.RegionSize > 0 else 0x10000
    except: base += 0x10000

print(f"基线: {len(baseline)} 区域, {sum(baseline.values())/1024/1024:.0f}MB", flush=True)
print("触发手机备份，自动监控 90 秒", flush=True)

# === Phase 2: Capture (500ms + GROWN detection) ===
dumped = set()
start = time.time()

while time.time() - start < 90:
    time.sleep(0.5)

    current = {}
    base = 0x100000
    while base < 0x7fffffffffff:
        try:
            mbi = pymem.memory.virtual_query(pm.process_handle, base)
            if mbi.State == 0x1000: current[base] = mbi.RegionSize
            base += mbi.RegionSize if mbi.RegionSize > 0 else 0x10000
        except: base += 0x10000

    for addr, size in current.items():
        is_new = addr not in baseline
        old_size = baseline.get(addr, 0)
        has_grown = not is_new and size > old_size * 1.05 and (size - old_size) > 256*1024

        if (is_new or has_grown) and size > 256*1024 and addr not in dumped:
            try:
                data = pm.read_bytes(addr, min(size, 2*1024*1024))
                if data and (b'msgsource' in data or b'wxid_' in data or b'<msg' in data):
                    ts = datetime.datetime.now().strftime('%H%M%S')
                    tag = "N" if is_new else "G"
                    fname = f"{tag}_{ts}_{addr:x}.bin"
                    with open(os.path.join(outdir, fname), 'wb') as f:
                        f.write(data[:min(len(data), 10*1024*1024)])
                    print(f"  {tag} 0x{addr:x} ({size>>20}MB)", flush=True)
                    dumped.add(addr)
            except: pass

print(f"\n捕获完成: {len(dumped)} 个文件", flush=True)

# === Phase 3: Quick parse ===
print("\n解析中...", flush=True)
files = sorted(os.listdir(outdir))
all_msgs = []
type_map = {1:"文本", 6:"文件", 19:"转发", 33:"链接", 36:"语音", 47:"表情", 49:"转发", 51:"视频", 53:"接龙", 57:"表情", 62:"拍一拍", 2000:"转账", 2001:"红包"}

for fname in files:
    if not fname.endswith('.bin'): continue
    txt = open(os.path.join(outdir, fname), 'rb').read().decode('utf-8', errors='replace')
    for seg in re.findall(r'<msg>.*?</msg>', txt):
        msg = {}
        # from/to
        fu = re.search(r'fromusername\s*=\s*"([^"]+)"', seg)
        if fu: msg['from'] = fu.group(1)
        tu = re.search(r'tousername\s*=\s*"([^"]+)"', seg)
        if tu: msg['to'] = tu.group(1)
        # type
        mt = re.search(r'<type>(.*?)</type>', seg)
        if mt:
            try: msg['type'] = int(re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', mt.group(1)))
            except: pass
        # content
        for tag in ['title', 'des']:
            m = re.search(f'<{tag}>(.*?)</{tag}>', seg)
            if m:
                raw = m.group(1)
                cd = re.search(r'<!\[CDATA\[(.*?)\]\]>', raw)
                if cd: raw = cd.group(1)
                msg[tag] = raw
        msg['content'] = msg.get('des') or msg.get('title', '')
        # timestamp
        for f in ['srcMsgCreateTime', 'createtime', 'sourcetime']:
            ts = re.search(f'<{f}>(\\d+)</{f}>', seg)
            if ts:
                v = int(ts.group(1))
                if 1500000000 < v < 1800000000:
                    msg['timestamp'] = v
                    break
        # msgsource
        ms = re.search(r'<msgsource>(.*?)</msgsource>', seg)
        if ms: msg['msgsource'] = ms.group(1)[:200]
        if msg.get('content'): all_msgs.append(msg)

# Dedup
seen = set()
unique = []
for m in all_msgs:
    k = m.get('content','')[:80]
    if k and k not in seen: seen.add(k); unique.append(m)

# Save parsed
with open(r'C:\Users\OK\Desktop\wechat_v4_export_research\experiments\logs\m74_parsed.json', 'w', encoding='utf-8') as f:
    json.dump({'total': len(unique), 'msgs': unique}, f, ensure_ascii=False, indent=2)

# Stats
senders = set()
for m in unique:
    if 'from' in m: senders.add(m['from'])
    if 'to' in m: senders.add(m['to'])

print(f"消息: {len(unique)}, 发送者: {len(senders)}", flush=True)
print(f"保存到 experiments/logs/m74_parsed.json", flush=True)
print("现在可以启动 GUI 了", flush=True)
