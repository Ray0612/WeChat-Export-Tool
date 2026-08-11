# -*- coding: utf-8 -*-
"""
M112 路线A v2 — 改进版文本提取器
目标: 从 WCDB 缓存中提取 时间戳 + 说话人 + 内容
"""
import pymem, psutil, struct, sys, re, time, json, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

OUTDIR = r'C:\Users\OK\Desktop\wx_export'
os.makedirs(OUTDIR, exist_ok=True)

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

chinese_pat = re.compile(b'([\xe4-\xe9][\xb8-\xbf][\x80-\xbf]){3,}')
wxid_pat = re.compile(b'wxid_[a-zA-Z0-9_]{10,30}')

all_msgs = {}
total_scan = 0

SCAN_START = 0x01a400000000
SCAN_END   = 0x01a600000000

addr = SCAN_START
while addr < SCAN_END:
    try:
        mbi = pymem.memory.virtual_query(pm.process_handle, addr)
        if mbi.State != 0x1000:
            addr += max(mbi.RegionSize, 0x1000)
            continue
        rsize = min(mbi.RegionSize, 0x200000)
        try:
            data = pm.read_bytes(addr, rsize)
        except:
            addr += max(mbi.RegionSize, 0x1000)
            continue

        for m in chinese_pat.finditer(data):
            abs_addr = addr + m.start()
            raw = data[m.start():m.start()+80].split(b'\x00')[0]
            try:
                text = raw.decode('utf-8', errors='replace').strip()
            except: continue
            if len(text) < 4 or len(text) > 500: continue
            if text in all_msgs: continue

            total_scan += 1

            # 取大范围上下文: 前面 512 字节 + 后面 128 字节
            ctx_start = max(0, m.start() - 512)
            ctx = data[ctx_start:m.start() + 128]

            # 1. 找 wxid
            wxids = list(set(w.decode() for w in wxid_pat.findall(ctx)))

            # 2. 找时间戳: 4字节/8字节整数在 1.5B-1.8B 范围
            timestamps = []
            for off in range(0, len(ctx) - 4):
                val = struct.unpack('<I', ctx[off:off+4])[0]
                if 1500000000 < val < 1900000000:
                    timestamps.append(val)
                val_be = struct.unpack('>I', ctx[off:off+4])[0]
                if 1500000000 < val_be < 1900000000:
                    timestamps.append(val_be)

            # 去重+排序
            timestamps = sorted(set(timestamps))[:5]

            # 3. 计算文本在上下文中的偏移
            txt_off = m.start() - ctx_start

            all_msgs[text] = {
                'addr': abs_addr,
                'text': text[:200],
                'len': len(text),
                'wxid': wxids[0] if wxids else '',
                'wxids': wxids,
                'timestamps': timestamps,
                'ctx_offset': txt_off,
                'ctx_sample': ctx[:64].hex()[:120],
            }

        addr += mbi.RegionSize if mbi.RegionSize > 0 else 0x1000
    except:
        addr += 0x10000

print(f"扫描 {total_scan} 条文本, 去重后 {len(all_msgs)} 条")
print()

# 分析时间戳
has_ts = [m for m in all_msgs.values() if m['timestamps']]
no_ts = [m for m in all_msgs.values() if not m['timestamps']]
print(f"有时间戳: {len(has_ts)}  |  无时间戳: {len(no_ts)}")

has_wxid = [m for m in all_msgs.values() if m['wxid']]
no_wxid = [m for m in all_msgs.values() if not m['wxid']]
print(f"有 wxid: {len(has_wxid)}  |  无 wxid: {len(no_wxid)}")
print()

# 显示样例: 有时间戳+wxid 的
print("=== 样例: 有时间戳+wxid 的消息 ===")
count = 0
for m in all_msgs.values():
    if m['timestamps'] and m['wxid']:
        ts_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(m['timestamps'][0]))
        print(f"  [{ts_str}] [{m['wxid'][:25]}] {m['text'][:60]}")
        count += 1
        if count >= 15: break

print()
print("=== 样例: 有时间戳但无 wxid ===")
count = 0
for m in all_msgs.values():
    if m['timestamps'] and not m['wxid']:
        ts_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(m['timestamps'][0]))
        print(f"  [{ts_str}] {m['text'][:60]}")
        count += 1
        if count >= 10: break

# 按说话人分组统计
by_wxid = {}
for m in all_msgs.values():
    wid = m['wxid'] or '__unknown'
    if wid not in by_wxid: by_wxid[wid] = []
    by_wxid[wid].append(m)

# 按时间排序的消息列表
sorted_msgs = sorted(all_msgs.values(), key=lambda m: m['timestamps'][0] if m['timestamps'] else 0)

# 保存
ts = int(time.time())
path = f'{OUTDIR}/extract_v2_{ts}.json'
with open(path, 'w', encoding='utf-8') as f:
    json.dump({
        'total_unique': len(all_msgs),
        'has_timestamp': len(has_ts),
        'has_wxid': len(has_wxid),
        'by_wxid': {k: len(v) for k, v in by_wxid.items()},
        'messages': sorted_msgs,
    }, f, ensure_ascii=False, indent=2)
print(f"\n已保存: {path}")
