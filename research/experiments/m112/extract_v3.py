# -*- coding: utf-8 -*-
"""
M112 v3 — 自适应扫描: 先找到中文文本区域，再提取带时间戳/wxid 的消息
"""
import pymem, psutil, struct, sys, re, time, json, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

OUTDIR = r'C:\Users\OK\Desktop\wx_export'
os.makedirs(OUTDIR, exist_ok=True)

# ── 1. 找微信 ──
pid = None
for proc in psutil.process_iter(['pid', 'name']):
    if proc.info['name'] == 'Weixin.exe':
        try:
            for f in proc.open_files():
                if 'message_0.db' in f.path:
                    pid = proc.info['pid']
                    break
        except: pass
        if pid: break

pm = pymem.Pymem(pid)
wx_base = None
for mod in pm.list_modules():
    if 'weixin.dll' in mod.name.lower():
        wx_base = mod.lpBaseOfDll
        break

print(f"PID: {pid}  weixin.dll: 0x{wx_base:x}")
print()

# ── 2. 扫描全部内存找中文文本区域 ──
chinese_pat = re.compile(b'([\xe4-\xe9][\xb8-\xbf][\x80-\xbf]){3,}')
wxid_pat = re.compile(b'wxid_[a-zA-Z0-9_]{10,30}')

text_regions = []
addr = 0
total_seen = 0
while addr < 0x7fffffffffff:
    try:
        mbi = pymem.memory.virtual_query(pm.process_handle, addr)
        if mbi.State == 0x1000 and mbi.RegionSize > 0:
            check_size = min(mbi.RegionSize, 0x10000)
            try:
                data = pm.read_bytes(addr, check_size)
                if chinese_pat.search(data):
                    text_regions.append((addr, mbi.RegionSize))
            except: pass
        addr += mbi.RegionSize if mbi.RegionSize > 0 else 0x10000
    except:
        addr += 0x10000

print(f"找到 {len(text_regions)} 个含中文文本的区域")
print()

# ── 3. 提取文本 ──
all_msgs = {}
scan_limit = min(20, len(text_regions))  # 最多扫 20 个最大区域

# 按大小排序
text_regions.sort(key=lambda x: -x[1])

for idx in range(scan_limit):
    rbase, rsize = text_regions[idx]
    read_size = min(rsize, 0x200000)
    try:
        data = pm.read_bytes(rbase, read_size)
    except:
        continue

    for m in chinese_pat.finditer(data):
        raw = data[m.start():m.start()+80].split(b'\x00')[0]
        try:
            text = raw.decode('utf-8', errors='replace').strip()
        except: continue
        if len(text) < 4 or len(text) > 500: continue
        if text in all_msgs: continue

        total_seen += 1
        abs_addr = rbase + m.start()
        ctx_start = max(0, m.start() - 512)
        ctx = data[ctx_start:m.start() + 128]

        # wxid
        wxids = list(set(w.decode() for w in wxid_pat.findall(ctx)))

        # 时间戳
        timestamps = []
        for off in range(0, len(ctx) - 4):
            val = struct.unpack('<I', ctx[off:off+4])[0]
            if 1500000000 < val < 1900000000:
                timestamps.append(val)

        all_msgs[text] = {
            'addr': abs_addr,
            'region': f'0x{rbase:x}',
            'text': text[:200],
            'wxid': wxids[0] if wxids else '',
            'timestamps': sorted(set(timestamps))[:3],
        }

# ── 4. 分析 ──
print(f"提取完成: {len(all_msgs)} 条不重复文本")

has_ts = [m for m in all_msgs.values() if m['timestamps']]
has_wx = [m for m in all_msgs.values() if m['wxid']]
print(f"带时间戳: {len(has_ts)}  |  带 wxid: {len(has_wx)}")
print()

# 显示样例
print("=== 样例 (有时间戳+wxid) ===")
count = 0
for m in all_msgs.values():
    if m['timestamps'] and m['wxid']:
        ts = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(m['timestamps'][0]))
        print(f"  [{ts}] [{m['wxid'][:25]}] {m['text'][:60]}")
        count += 1
        if count >= 20: break

print()
print("=== 样例 (有时间戳但无 wxid) ===")
count = 0
for m in all_msgs.values():
    if m['timestamps'] and not m['wxid']:
        ts = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(m['timestamps'][0]))
        print(f"  [{ts}] {m['text'][:60]}")
        count += 1
        if count >= 15: break

# 保存
ts = int(time.time())
path = f'{OUTDIR}/extract_v3_{ts}.json'
with open(path, 'w', encoding='utf-8') as f:
    json.dump({
        'total': len(all_msgs),
        'has_timestamp': len(has_ts),
        'has_wxid': len(has_wx),
        'messages': sorted(all_msgs.values(), key=lambda m: m['timestamps'][0] if m['timestamps'] else 0),
    }, f, ensure_ascii=False, indent=2)
print(f"\n保存: {path}")
