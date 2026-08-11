# -*- coding: utf-8 -*-
"""
M112 路线A — 实时监控器 v2
流程:
1. 等待 Weixin.exe 启动 (检测 message_0.db 句柄)
2. 持续监控 0x1a400000000-0x1a600000000 范围出现的中文文本
3. 解析上下文提取 时间戳 + wxid
4. 实时显示已收集条数
5. 用户翻页时自动捕获新消息

用法: python live_monitor_v2.py
      然后打开微信 → 点聊天窗口 → 滚轮翻页
"""
import pymem, psutil, struct, sys, re, time, json, os, datetime
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

OUTDIR = r'C:\Users\OK\Desktop\wx_export'
os.makedirs(OUTDIR, exist_ok=True)

chinese_pat = re.compile(b'([\xe4-\xe9][\xb8-\xbf][\x80-\xbf]){3,}')
wxid_pat = re.compile(b'wxid_[a-zA-Z0-9_]{10,30}')

def find_wechat():
    """找 Weixin.exe PID，等待直到出现"""
    while True:
        for proc in psutil.process_iter(['pid', 'name']):
            if proc.info['name'] == 'Weixin.exe':
                try:
                    for f in proc.open_files():
                        if 'message_0.db' in f.path:
                            return proc.info['pid']
                except: pass
        print("等待微信启动...", end='\r')
        time.sleep(2)

def get_wx_base(pm):
    for mod in pm.list_modules():
        if 'weixin.dll' in mod.name.lower():
            return mod.lpBaseOfDll
    return None

def get_heap_regions(pm):
    """枚举 Weixin.exe 的私有堆区域"""
    regions = []
    addr = 0
    while addr < 0x7fffffffffff:
        try:
            mbi = pymem.memory.virtual_query(pm.process_handle, addr)
            if mbi.State == 0x1000 and mbi.RegionSize > 0:
                regions.append((addr, mbi.RegionSize))
            addr += mbi.RegionSize if mbi.RegionSize > 0 else 0x10000
        except:
            addr += 0x10000
    return regions

print("=" * 50)
print("M112 路线A — 实时消息监控器 v2")
print("=" * 50)
print()
print("步骤:")
print("1. 关闭微信")
print("2. 运行本脚本")
print("3. 打开微信 → 点开一个聊天窗口 → 翻页")
print()

# 全局缓存
all_msgs = {}      # text → info
seen_addr_ranges = set()  # 已扫描过的区域标识

pid = None
pm = None

while True:
    try:
        # 检测微信
        new_pid = find_wechat()
        if new_pid != pid:
            print(f"\n检测到微信启动! PID: {new_pid}")
            pid = new_pid
            pm = pymem.Pymem(pid)
            wx_base = get_wx_base(pm)
            print(f"weixin.dll: 0x{wx_base:x}")
            all_msgs = {}  # 新进程，清空旧缓存
            round_n = 0
            print("请点开一个聊天窗口并翻页...\n")

        # 扫描
        round_n += 1
        round_new = 0
        now = datetime.datetime.now().strftime('%H:%M:%S')

        # 只扫 0x1a400000000-0x1a600000000 范围
        addr = 0x01a400000000
        while addr < 0x01a600000000:
            try:
                mbi = pymem.memory.virtual_query(pm.process_handle, addr)
                if mbi.State != 0x1000:
                    addr += max(mbi.RegionSize, 0x1000)
                    continue
                rsize = min(mbi.RegionSize, 0x100000)
                try:
                    data = pm.read_bytes(addr, rsize)
                except:
                    addr += max(mbi.RegionSize, 0x1000)
                    continue

                for m in chinese_pat.finditer(data):
                    raw = data[m.start():m.start()+60].split(b'\x00')[0]
                    try:
                        text = raw.decode('utf-8', errors='replace').strip()
                    except: continue
                    if len(text) < 4: continue
                    if text in all_msgs: continue

                    # 上下文: 前 512 字节
                    ctx_start = max(0, m.start() - 512)
                    ctx = data[ctx_start:m.start() + 80]

                    # 提取 wxid
                    wxids = list(set(w.decode() for w in wxid_pat.findall(ctx)))

                    # 提取时间戳
                    timestamps = []
                    for off in range(0, len(ctx) - 4):
                        val = struct.unpack('<I', ctx[off:off+4])[0]
                        if 1500000000 < val < 1900000000:
                            timestamps.append(val)

                    all_msgs[text] = {
                        'addr': addr + m.start(),
                        'text': text[:200],
                        'wxid': wxids[0] if wxids else '',
                        'timestamps': sorted(set(timestamps))[:3],
                        'round': round_n,
                    }
                    round_new += 1

                addr += mbi.RegionSize if mbi.RegionSize > 0 else 0x1000
            except:
                addr += 0x10000

        # 统计
        has_ts = sum(1 for m in all_msgs.values() if m['timestamps'])
        has_wxid = sum(1 for m in all_msgs.values() if m['wxid'])

        status = f"[{now}] +{round_new} 新 | 累计 {len(all_msgs)} 条 | {has_ts} 条带时间戳 | {has_wxid} 条带wxid"
        print(status, ' ' * 10, end='\r')

        # 第一次发现带时间戳的消息时，显示样例
        if round_new > 0:
            new_ones = [m for m in all_msgs.values() if m['round'] == round_n]
            # 显示最新的几条
            print()
            for m in new_ones[-min(5, len(new_ones)):]:
                ts_str = ''
                if m['timestamps']:
                    ts_str = time.strftime('%m-%d %H:%M', time.localtime(m['timestamps'][0]))
                wid = m['wxid'][:25] if m['wxid'] else ''
                print(f"  [{ts_str}][{wid}] {m['text'][:50]}")
            print()

        # 每 30 轮存一次
        if round_n % 30 == 0:
            path = f'{OUTDIR}/live_v2_{int(time.time())}.json'
            with open(path, 'w', encoding='utf-8') as f:
                json.dump({
                    'total': len(all_msgs),
                    'has_timestamp': has_ts,
                    'has_wxid': has_wxid,
                    'messages': list(all_msgs.values()),
                }, f, ensure_ascii=False, indent=2)

        time.sleep(2)

    except (pymem.exception.ProcessNotFound, pymem.exception.PymemError):
        # 进程消失了，等待重启
        print(f"\n微信进程消失，等待重启...")
        pid = None
        pm = None
        time.sleep(3)
        continue
    except KeyboardInterrupt:
        print("\n\n停止监控")
        path = f'{OUTDIR}/live_v2_final_{int(time.time())}.json'
        with open(path, 'w', encoding='utf-8') as f:
            json.dump({
                'total': len(all_msgs),
                'messages': list(all_msgs.values()),
            }, f, ensure_ascii=False, indent=2)
        print(f"保存: {path}")
        print(f"共 {len(all_msgs)} 条消息")
        sys.exit(0)
