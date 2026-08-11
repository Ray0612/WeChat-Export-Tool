# -*- coding: utf-8 -*-
"""
提取中文消息文本 — 仅扫 0x1a400000000-0x1a600000000 范围
"""
import pymem, psutil, struct, sys, re, time, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

OUTDIR = r'C:\Users\OK\Desktop\wx_export'

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
time_pat = re.compile(b'(\d{9,10})')

all_msgs = {}

SCAN_START = 0x01a400000000
SCAN_END   = 0x01a600000000

addr = SCAN_START
while addr < SCAN_END:
    try:
        mbi = pymem.memory.virtual_query(pm.process_handle, addr)
        if mbi.State != 0x1000:
            addr += max(mbi.RegionSize, 0x1000)
            continue
        rsize = min(mbi.RegionSize, 0x100000)  # max 1MB per read
        try:
            data = pm.read_bytes(addr, rsize)
        except:
            addr += max(mbi.RegionSize, 0x1000)
            continue

        for m in chinese_pat.finditer(data):
            abs_addr = addr + m.start()
            raw = data[m.start():m.start()+60].split(b'\x00')[0]
            try:
                text = raw.decode('utf-8', errors='replace').strip()
            except:
                continue
            if len(text) < 4 or len(text) > 300:
                continue
            if text in all_msgs:
                continue

            # 周围 200 字节上下文
            ctx_start = max(0, m.start() - 200)
            ctx = data[ctx_start:m.start() + 60]

            wxids = [w.decode() for w in wxid_pat.findall(ctx)]
            timestamps = [int(t.group(1)) for t in time_pat.finditer(ctx) if 1000000000 < int(t.group(1)) < 2000000000]

            all_msgs[text] = {
                'addr': abs_addr,
                'text': text,
                'len': len(text),
                'wxid': wxids[0] if wxids else '',
                'ts': timestamps[0] if timestamps else 0,
            }

        addr += mbi.RegionSize if mbi.RegionSize > 0 else 0x1000
    except:
        addr += 0x10000

print(f"共 {len(all_msgs)} 条不重复文本")

# 按 wxid 分组
by_wxid = {}
for msg in all_msgs.values():
    wid = msg['wxid'] or '__unknown'
    if wid not in by_wxid:
        by_wxid[wid] = []
    by_wxid[wid].append(msg)

print(f"\n发送者分布:")
for wid, msgs in sorted(by_wxid.items(), key=lambda x: -len(x[1]))[:15]:
    print(f"  {wid}: {len(msgs)} 条")
    for m in msgs[:3]:
        print(f"    {m['text'][:40]}")

# 保存
ts = int(time.time())
path = f'{OUTDIR}/raw_texts_{ts}.json'
with open(path, 'w', encoding='utf-8') as f:
    json.dump({
        'total': len(all_msgs),
        'by_wxid': {k: len(v) for k, v in by_wxid.items()},
        'messages': list(all_msgs.values()),
    }, f, ensure_ascii=False, indent=2)
print(f"\n保存: {path}")
