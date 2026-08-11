# -*- coding: utf-8 -*-
"""
M112 路线A — 单会话实时监控器 v3
流程:
1. 关闭微信 → 启动监控器 → 打开微信 → 点开一个聊天 → 翻页
2. 监控器只捕获「新出现」的消息 (delta from baseline)
3. 此时缓存是空的，所以新数据只来自当前会话
4. 说话人: 根据 wxid 区分
5. 时间戳: 尝试从附近二进制提取，同时用首次发现时间作为 fallback
"""
import pymem, psutil, struct, sys, re, time, json, os, datetime
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

OUTDIR = r'C:\Users\OK\Desktop\wx_export'
os.makedirs(OUTDIR, exist_ok=True)

chinese_pat = re.compile(b'([\xe4-\xe9][\xb8-\xbf][\x80-\xbf]){3,}')
wxid_pat = re.compile(b'wxid_[a-zA-Z0-9_]{10,30}')

def find_wechat():
    while True:
        for proc in psutil.process_iter(['pid', 'name']):
            if proc.info['name'] == 'Weixin.exe':
                try:
                    for f in proc.open_files():
                        if 'message_0.db' in f.path:
                            return proc.info['pid']
                except: pass
        time.sleep(1)

def find_text_regions(pm):
    """找到所有包含中文文本的区域 (只检查每个区域的起始部分)"""
    regions = []
    addr = 0
    while addr < 0x7fffffffffff:
        try:
            mbi = pymem.memory.virtual_query(pm.process_handle, addr)
            if mbi.State == 0x1000 and mbi.RegionSize > 0:
                try:
                    check = pm.read_bytes(addr, min(mbi.RegionSize, 0x10000))
                    if chinese_pat.search(check):
                        regions.append((addr, mbi.RegionSize))
                except: pass
            addr += mbi.RegionSize if mbi.RegionSize > 0 else 0x10000
        except:
            addr += 0x10000
    return regions

def extract_texts(pm, regions, max_read=0x100000):
    """从指定区域提取所有中文文本"""
    result = {}
    for rbase, rsize in regions:
        try:
            data = pm.read_bytes(rbase, min(rsize, max_read))
        except:
            continue
        for m in chinese_pat.finditer(data):
            raw = data[m.start():m.start()+60].split(b'\x00')[0]
            try:
                text = raw.decode('utf-8', errors='replace').strip()
            except: continue
            if len(text) < 4: continue
            if text in result: continue

            # 上下文找 wxid
            ctx_start = max(0, m.start() - 256)
            ctx = data[ctx_start:m.start() + 60]
            wxids = list(set(w.decode() for w in wxid_pat.findall(ctx)))

            result[text] = {
                'text': text[:200],
                'addr': rbase + m.start(),
                'wxid': wxids[0] if wxids else '',
                'first_seen': time.time(),
            }
    return result

# ── 主流程 ──
print("=" * 50)
print("M112 路线A — 单会话监控器 v3")
print("=" * 50)
print()
print("请先关闭微信，然后按 Enter 开始监控 (后台模式: 等待微信关闭...)")
# 等待微信关闭
while True:
    found = False
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.info['name'] == 'Weixin.exe':
            found = True
            break
    if not found:
        break
    time.sleep(1)
print("微信已关闭，开始监控...")

print("等待微信启动...")
pid = find_wechat()
print(f"微信已启动! PID: {pid}")
pm = pymem.Pymem(pid)

wx_base = None
for mod in pm.list_modules():
    if 'weixin.dll' in mod.name.lower():
        wx_base = mod.lpBaseOfDll
        break

print(f"正在扫描初始缓存 (基线)...")
baseline_regions = find_text_regions(pm)
print(f"找到 {len(baseline_regions)} 个中文区域")

baseline = extract_texts(pm, baseline_regions)
print(f"基线: {len(baseline)} 条预存文本")
print()

print("请点开一个聊天窗口并翻页")
print("监控中...")
print()

captured = []  # 有序列表, 按发现顺序
seen_texts = set(baseline.keys())
no_new_rounds = 0
round_n = 0

try:
    while True:
        round_n += 1
        new_this_round = 0

        current = extract_texts(pm, baseline_regions)

        for text, info in current.items():
            if text not in seen_texts:
                seen_texts.add(text)
                captured.append(info)
                new_this_round += 1

        if new_this_round > 0:
            no_new_rounds = 0
            print(f"[+{new_this_round}] 累计 {len(captured)} 条")
            for m in captured[-new_this_round:]:
                wid = m['wxid'][:25] if m['wxid'] else '(?)'
                print(f"  [{wid}] {m['text'][:55]}")
            print()
        else:
            no_new_rounds += 1

        # 60 轮无新消息 → 结束
        if no_new_rounds >= 60:
            print("60 秒无新消息，自动停止")
            break

        time.sleep(1)

except KeyboardInterrupt:
    print("\n手动停止")

# ── 结果 ──
print()
print(f"共捕获 {len(captured)} 条消息")

# 说话人分组
my_wxid = 'wxid_caccoealsdbj12'
me_count = sum(1 for m in captured if m['wxid'] == my_wxid)
them_count = sum(1 for m in captured if m['wxid'] and m['wxid'] != my_wxid)
unknown_count = sum(1 for m in captured if not m['wxid'])
print(f"  我: {me_count}  |  对方: {them_count}  |  未知: {unknown_count}")

# 导出
ts = int(time.time())
path = f'{OUTDIR}/session_export_{ts}.json'
with open(path, 'w', encoding='utf-8') as f:
    json.dump({
        'total': len(captured),
        'me_count': me_count,
        'them_count': them_count,
        'my_wxid': my_wxid,
        'messages': captured,
    }, f, ensure_ascii=False, indent=2)
print(f"保存: {path}")
print()

# 尝试按说话人交替打印预览
if me_count > 0 and them_count > 0:
    print("=== 导出预览 (交替显示 我/对方) ===")
    for m in captured[:30]:
        speaker = '我' if m['wxid'] == my_wxid else ('对方' if m['wxid'] else '?')
        print(f"  [{speaker}] {m['text'][:60]}")
