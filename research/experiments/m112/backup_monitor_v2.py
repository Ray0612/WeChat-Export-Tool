# -*- coding: utf-8 -*-
"""
M112 路线B — 备份监控器 v2
专抓备份过程中出现的 XML 消息 + datasrctime 时间戳
"""
import pymem, psutil, struct, sys, re, time, json, os, datetime
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

OUTDIR = r'C:\Users\OK\Desktop\wx_export\backup_experiment'
os.makedirs(OUTDIR, exist_ok=True)
log_file = os.path.join(OUTDIR, 'backup_v2_log.txt')

# 关键模式
datasrctime_pat = re.compile(b'<datasrctime>(.*?)</datasrctime>')
msg_block_pat = re.compile(b'<msg>.*?</msg>', re.DOTALL)
datadesc_pat = re.compile(b'<datadesc>(.*?)</datadesc>')
title_pat = re.compile(b'<title>(.*?)</title>')

def log(msg):
    line = f'[{datetime.datetime.now().strftime("%H:%M:%S")}] {msg}'
    print(line)
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(line + '\n')

log("=" * 50)
log("备份监控 v2 启动")
log("=" * 50)

captured_msgs = []   # {time, content, source}
all_texts = set()

round_n = 0
try:
    while True:
        round_n += 1

        for proc in psutil.process_iter(['pid', 'name']):
            name = proc.info['name']
            if name not in ('Weixin.exe', 'WeixinExt.exe') and 'WeChatAppEx' not in name:
                continue
            pid = proc.info['pid']
            try:
                pm = pymem.Pymem(pid)
            except:
                continue

            # 扫描私有堆和映射内存
            addr = 0
            while addr < 0x7fffffffffff:
                try:
                    mbi = pymem.memory.virtual_query(pm.process_handle, addr)
                    if mbi.State != 0x1000 or mbi.RegionSize <= 0:
                        addr += max(mbi.RegionSize, 0x1000)
                        continue
                    try:
                        data = pm.read_bytes(addr, min(mbi.RegionSize, 0x20000))
                    except:
                        addr += max(mbi.RegionSize, 0x1000)
                        continue

                    # 1. 找 datasrctime (备份时间戳)
                    for m in datasrctime_pat.finditer(data):
                        ts_raw = m.group(1).decode('utf-8', errors='replace').strip()
                        # 找这条消息附近的 text
                        ctx = data[m.start():m.start()+2000]
                        # 试着提取 des 或 title
                        content = ''
                        for pat in [datadesc_pat, title_pat]:
                            cm = pat.search(ctx[200:])
                            if cm:
                                content = cm.group(1).decode('utf-8', errors='replace').strip()
                                break
                        if not content:
                            # 提取纯文本
                            raw = ctx[400:800].split(b'\x00')[0]
                            content = raw.decode('utf-8', errors='replace').strip()[:100]

                        msg_key = f'{ts_raw}|{content[:30]}'
                        if msg_key not in [m['key'] for m in captured_msgs[-100:]]:
                            captured_msgs.append({
                                'key': msg_key,
                                'time': ts_raw,
                                'content': content,
                                'pid': pid,
                                'proc': name,
                            })
                            log(f"[MSG] {ts_raw} | {content[:60]}")

                    # 2. 找完整 msg 块
                    for m in msg_block_pat.finditer(data):
                        xml = data[m.start():m.end()]
                        # 提取 title
                        tm = title_pat.search(xml)
                        if tm:
                            title = tm.group(1).decode('utf-8', errors='replace').strip()
                            if title not in all_texts:
                                all_texts.add(title)
                                log(f"[XML] {title[:60]}")

                    addr += mbi.RegionSize if mbi.RegionSize > 0 else 0x1000
                except:
                    addr += 0x10000

        # 实时状态
        if round_n % 5 == 0:
            print(f"  [{datetime.datetime.now().strftime('%H:%M:%S')}] MSG: {len(captured_msgs)} | XML: {len(all_texts)}", end='\r')

        # 每 30 轮保存 checkpoint
        if round_n % 30 == 0 and (captured_msgs or all_texts):
            path = f'{OUTDIR}/cp_v2_{int(time.time())}.json'
            with open(path, 'w', encoding='utf-8') as f:
                json.dump({
                    'msgs': captured_msgs[-200:],
                    'xml_titles': sorted(all_texts)[-200:],
                }, f, ensure_ascii=False, indent=2)

        time.sleep(2)

except KeyboardInterrupt:
    log("\n停止")
    path = f'{OUTDIR}/backup_v2_final_{int(time.time())}.json'
    with open(path, 'w', encoding='utf-8') as f:
        json.dump({'msgs': captured_msgs, 'xml_titles': sorted(all_texts)}, f, ensure_ascii=False, indent=2)
    log(f"保存: {path}")
    log(f"共 {len(captured_msgs)} 条带时间戳消息, {len(all_texts)} 条 XML")
