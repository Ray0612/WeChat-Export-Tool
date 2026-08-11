# -*- coding: utf-8 -*-
"""
硬盘监控 — 实时监控备份过程中微信的磁盘写入
监控目录:
  - xwechat_files 整个目录
  - Backup 目录
  - 用户数据库目录
"""
import sys, time, os, datetime, json, hashlib
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

OUTDIR = r'C:\Users\OK\Desktop\wx_export\backup_experiment'
os.makedirs(OUTDIR, exist_ok=True)

# 监控的根目录
WATCH_DIRS = [
    r'D:\储存信息\xwechat_files',
]

# 已知的文件快照: path → (size, mtime)
snapshot = {}
all_events = []

def take_snapshot():
    """递归扫描目录，记录文件大小和修改时间"""
    snap = {}
    for base_dir in WATCH_DIRS:
        if not os.path.exists(base_dir):
            continue
        for root, dirs, files in os.walk(base_dir):
            for f in files:
                try:
                    fp = os.path.join(root, f)
                    stat = os.stat(fp)
                    snap[fp] = (stat.st_size, stat.st_mtime)
                except: pass
    return snap

def format_size(s):
    if s < 1024: return f'{s}B'
    if s < 1024*1024: return f'{s//1024}KB'
    return f'{s//1024//1024}MB'

def log(msg):
    line = f'[{datetime.datetime.now().strftime("%H:%M:%S")}] {msg}'
    print(line)

# 日志文件
log_file = os.path.join(OUTDIR, 'disk_monitor_log.txt')
with open(log_file, 'w', encoding='utf-8') as f:
    f.write('Disk Monitor Log\n')

def log_save(msg):
    line = f'[{datetime.datetime.now().strftime("%H:%M:%S")}] {msg}'
    print(line)
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(line + '\n')

log_save('=' * 50)
log_save('硬盘监控启动')
log_save('=' * 50)

# 初始快照
log_save('创建初始快照...')
snapshot = take_snapshot()
log_save(f'已记录 {len(snapshot)} 个文件')
log_save('')
log_save('请开始手机→电脑备份')
log_save('')

round_n = 0
try:
    while True:
        round_n += 1
        current = take_snapshot()

        new_files = []
        modified_files = []
        deleted_files = []

        for fp, (size, mtime) in current.items():
            if fp not in snapshot:
                new_files.append((fp, size, mtime))
            else:
                old_size, old_mtime = snapshot[fp]
                if size != old_size or abs(mtime - old_mtime) > 0.1:
                    modified_files.append((fp, size, mtime, size - old_size))

        for fp in snapshot:
            if fp not in current:
                deleted_files.append(fp)

        snapshot = current

        significant = []

        # 报告新文件和变化
        if new_files:
            log_save(f'--- 新文件 ({len(new_files)} 个) ---')
            for fp, size, mtime in sorted(new_files, key=lambda x: x[2])[:20]:
                log_save(f'  + {fp} ({format_size(size)})')
            if len(new_files) > 20:
                log_save(f'  ... 还有 {len(new_files)-20} 个')

        if modified_files:
            # 只报告有意义的变化 (> 1KB)
            sig = [(fp, s, m, d) for fp, s, m, d in modified_files if abs(d) > 1024 or 'backup' in fp.lower() or 'message' in fp.lower() or '.db' in fp.lower()]
            significant.extend(sig)
            if sig:
                log_save(f'--- 文件变化 ({len(significant)} 个有意义) ---')
                for fp, size, mtime, delta in sorted(significant, key=lambda x: -abs(x[3]))[:15]:
                    direction = '+' if delta > 0 else ''
                    log_save(f'  ~ {fp} ({format_size(size)}, {direction}{format_size(delta)})')

                    # 如果是数据库文件，复制一份做分析
                    if size > 1024 and ('.db' in fp.lower() or 'backup' in fp.lower()) and 'wal' not in fp and 'shm' not in fp:
                        try:
                            copy_dir = os.path.join(OUTDIR, 'file_snapshots')
                            os.makedirs(copy_dir, exist_ok=True)
                            safe_name = fp.replace(':', '').replace('\\', '_').replace('/', '_')
                            dst = os.path.join(copy_dir, f'{int(time.time())}_{safe_name}')
                            # 只读前 1MB
                            with open(fp, 'rb') as src_f:
                                data = src_f.read(min(size, 1024*1024))
                            with open(dst, 'wb') as dst_f:
                                dst_f.write(data)
                            log_save(f'    -> 已保存快照: {dst}')
                        except Exception as e:
                            log_save(f'    -> 保存失败: {e}')

        if new_files or significant:
            # 保存事件日志
            event_path = os.path.join(OUTDIR, f'disk_events_{int(time.time())}.json')
            try:
                with open(event_path, 'w', encoding='utf-8') as f:
                    json.dump({
                        'new_files': [(fp, format_size(s)) for fp, s, _, _ in new_files[:50]],
                        'modified': [(fp, format_size(s), f'{d:+d}') for fp, s, _, d in significant[:30]],
                    }, f, ensure_ascii=False, indent=2)
            except: pass

        if round_n % 12 == 0:  # 约每 60 秒
            log_save(f'[状态] 监控中... {len(snapshot)} 个文件')

        time.sleep(5)

except KeyboardInterrupt:
    log_save('\n停止监控')
    log_save(f'共记录 {len(all_events)} 个事件')
    log_save(f'最终快照: {len(snapshot)} 个文件')
