# -*- coding: utf-8 -*-
"""
M112 路线B — 全量备份实验监控器
目标: 在手机→电脑备份过程中捕获:
  - 内存中出现的 XML 消息
  - 中文文本消息
  - flue.dll 中的 SQLCipher key 线索
  - 数据库文件变化

流程: 启动本脚本 → 登录微信 → 手机备份到电脑
"""
import pymem, psutil, struct, sys, re, time, json, os, datetime
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

OUTDIR = r'C:\Users\OK\Desktop\wx_export\backup_experiment'
os.makedirs(OUTDIR, exist_ok=True)

# 模式
xml_pat = re.compile(b'<msg>.*?</msg>', re.DOTALL)
chinese_pat = re.compile(b'([\xe4-\xe9][\xb8-\xbf][\x80-\xbf]){3,}')
wxid_pat = re.compile(b'wxid_[a-zA-Z0-9_]{10,30}')
hex_key_pat = re.compile(b'0x[0-9a-fA-F]{64,128}')

log_file = os.path.join(OUTDIR, 'backup_log.txt')

def log(msg):
    line = f'[{datetime.datetime.now().strftime("%H:%M:%S")}] {msg}'
    print(line)
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(line + '\n')

def find_pids():
    """找所有相关进程 PID"""
    result = {'weixin': [], 'wechatappex': []}
    for proc in psutil.process_iter(['pid', 'name']):
        name = proc.info['name']
        if name == 'Weixin.exe':
            result['weixin'].append(proc.info['pid'])
        elif 'WeChatAppEx' in name:
            result['wechatappex'].append(proc.info['pid'])
    return result

# ── 主流程 ──
print("=" * 60)
print("M112 路线B — 全量备份实验监控器")
print("=" * 60)
print()
print("流程:")
print("  1. 本脚本已启动")
print("  2. 你登录微信")
print("  3. 你打开 设置→备份与恢复→备份聊天记录到电脑")
print("  4. 手机扫码 → 开始备份")
print()
print("监控内容:")
print("  - 内存中出现的 XML 消息")
print("  - 出现的中文文本 (实时增量)")
print("  - SQLCipher key 候选 (flue.dll)")
print("  - 关键进程变化")
print()

log("备份实验开始")

all_texts = set()
all_xml = []
flue_bases = {}
prev_pids = set()

round_n = 0
try:
    while True:
        round_n += 1
        pids = find_pids()

        # 检查进程变化
        current_pids = set(pids['weixin'] + pids['wechatappex'])
        new_pids = current_pids - prev_pids
        if new_pids:
            log(f"新进程: {new_pids}")
        prev_pids = current_pids

        # 对每个 WeChatAppEx 进程检查 flue.dll
        for pid in pids['wechatappex']:
            if pid not in flue_bases:
                try:
                    pm = pymem.Pymem(pid)
                    for mod in pm.list_modules():
                        if 'flue.dll' in mod.name.lower():
                            flue_bases[pid] = mod.lpBaseOfDll
                            log(f"WeChatAppEx PID {pid}: flue.dll @ 0x{mod.lpBaseOfDll:x}")
                            # 检查 sqlite3_key_v2 地址
                            key_func = mod.lpBaseOfDll + 0x2a9c805
                            log(f"  sqlite3_key_v2 @ 0x{key_func:x}")
                            break
                except: pass

        # 扫描 Weixin.exe 内存 (全部私有堆)
        for pid in pids['weixin']:
            try:
                pm = pymem.Pymem(pid)
                # 扫全内存找中文文本和 XML
                addr = 0
                while addr < 0x7fffffffffff:
                    try:
                        mbi = pymem.memory.virtual_query(pm.process_handle, addr)
                        if mbi.State == 0x1000 and mbi.RegionSize > 0:
                            # 只读前 64KB 做快速检测
                            try:
                                data = pm.read_bytes(addr, min(mbi.RegionSize, 0x10000))
                            except:
                                addr += max(mbi.RegionSize, 0x1000)
                                continue

                            # XML 消息
                            for m in xml_pat.finditer(data):
                                xml_text = data[m.start():m.end()]
                                xml_str = xml_text.decode('utf-8', errors='replace')
                                if xml_str not in all_xml:
                                    all_xml.append(xml_str)
                                    if len(all_xml) <= 10:
                                        log(f"  XML[{len(all_xml)}]: {xml_str[:80]}")

                            # 中文文本
                            for m in chinese_pat.finditer(data):
                                raw = data[m.start():m.start()+60].split(b'\x00')[0]
                                try:
                                    text = raw.decode('utf-8', errors='replace').strip()
                                except: continue
                                if len(text) >= 4 and text not in all_texts:
                                    all_texts.add(text)

                        addr += mbi.RegionSize if mbi.RegionSize > 0 else 0x10000
                    except:
                        addr += 0x10000
            except: pass

        # 每轮输出状态
        if round_n % 5 == 0:
            status = f"文本: {len(all_texts)} | XML: {len(all_xml)} | flue.dll PIDs: {list(flue_bases.keys())}"
            print(f"  [{datetime.datetime.now().strftime('%H:%M:%S')}] {status}", end='\r')

        # 每 10 轮检查 WeChatAppEx 的 flue.dll key 搜索
        if round_n % 10 == 0:
            for pid, flue_base in flue_bases.items():
                try:
                    pm = pymem.Pymem(pid)
                    # 扫 flue.dll 附近的堆内存找 key
                    key_func = flue_base + 0x2a9c805
                    # 读 sqlite3_key_v2 附近的代码
                    code = pm.read_bytes(key_func, 32)
                    log(f"  flue key func @ PID {pid}: {code[:16].hex()}")
                except: pass

        # 保存 checkpoint
        if round_n % 30 == 0 and (len(all_texts) > 0 or len(all_xml) > 0):
            path = f'{OUTDIR}/checkpoint_{int(time.time())}.json'
            with open(path, 'w', encoding='utf-8') as f:
                json.dump({
                    'texts_count': len(all_texts),
                    'xml_count': len(all_xml),
                    'flue_pids': list(flue_bases.keys()),
                    'sample_texts': sorted(all_texts)[:200],
                    'sample_xml': all_xml[:20],
                }, f, ensure_ascii=False, indent=2)
            log(f"Checkpoint saved: {path}")

        time.sleep(2)

except KeyboardInterrupt:
    print("\n\n停止监控")
    path = f'{OUTDIR}/backup_final_{int(time.time())}.json'
    with open(path, 'w', encoding='utf-8') as f:
        json.dump({
            'texts_count': len(all_texts),
            'xml_count': len(all_xml),
            'flue_pids': list(flue_bases.keys()),
            'all_texts': sorted(all_texts),
            'all_xml': all_xml,
        }, f, ensure_ascii=False, indent=2)
    log(f"最终保存: {path}")
    print(f"共 {len(all_texts)} 文本, {len(all_xml)} XML")
