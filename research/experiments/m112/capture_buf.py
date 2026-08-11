# -*- coding: utf-8 -*-
"""
Buf 文件捕获器 — 实时监控 temp/phone/Buf 目录
一旦有新 Buf 文件出现，立即复制，在文件被删除前截取数据
"""
import sys, time, os, datetime, shutil
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

OUTDIR = r'C:\Users\OK\Desktop\wx_export\backup_experiment\buf_captures'
os.makedirs(OUTDIR, exist_ok=True)

BUF_DIR = 'D:/储存信息/xwechat_files/wxid_caccoealsdbj12_e8c8/temp/phone/Buf'
MIG_DB  = 'D:/储存信息/xwechat_files/wxid_caccoealsdbj12_e8c8/temp/phone/migration.db'

# 已见过的文件名
seen_buf = set()
last_mig_size = 0

def capture_file(src, label='buf'):
    """复制文件到输出目录"""
    if not os.path.exists(src): return
    try:
        size = os.path.getsize(src)
        if size == 0: return
        ts = int(time.time())
        fname = os.path.basename(src)
        dst = os.path.join(OUTDIR, f'{ts}_{label}_{size}_{fname}')
        shutil.copy2(src, dst)
        return dst
    except: return None

def log(msg):
    line = '[%s] %s' % (datetime.datetime.now().strftime('%H:%M:%S'), msg)
    print(line)
    with open(os.path.join(OUTDIR, 'capture_log.txt'), 'a', encoding='utf-8') as f:
        f.write(line + '\n')

log('=' * 50)
log('Buf 捕获器启动')
log('=' * 50)
log('监控目录: %s' % BUF_DIR)
log('')
log('请开始手机→电脑备份')
log('')

# 创建初始快照
if os.path.exists(BUF_DIR):
    for f in os.listdir(BUF_DIR):
        seen_buf.add(f)
    log('已有 %d 个 Buf 文件 (跳过)' % len(seen_buf))

round_n = 0
try:
    while True:
        round_n += 1
        captured = []

        # 1. 监控 Buf 目录
        if os.path.exists(BUF_DIR):
            current_files = set(os.listdir(BUF_DIR))
            new_files = current_files - seen_buf

            for f in new_files:
                fp = os.path.join(BUF_DIR, f)
                # 立刻复制！延迟几毫秒都可能被删
                dst = capture_file(fp, 'buf')
                if dst:
                    captured.append(dst)
                    size = os.path.getsize(fp) if os.path.exists(fp) else 0
                    log('捕获 Buf: %s (%d KB)' % (f, size//1024))
                seen_buf.add(f)

        # 2. 监控 migration.db 变化
        if os.path.exists(MIG_DB):
            cur_size = os.path.getsize(MIG_DB)
            if cur_size != last_mig_size:
                dst = capture_file(MIG_DB, 'mig')
                if dst:
                    log('捕获 migration.db (%d KB)' % (cur_size//1024))
                last_mig_size = cur_size

        # 3. 如果有捕获，分析文件类型
        if captured:
            for fp in captured:
                try:
                    with open(fp, 'rb') as f:
                        header = f.read(32)
                    # 检查文件类型
                    if header[:16] == b'SQLite format 3\x00':
                        log('  -> 标准 SQLite 数据库')
                    elif b'<msg>' in header or b'<title>' in header:
                        log('  -> XML 消息数据!')
                        # 显示前 200 字节
                        with open(fp, 'rb') as f:
                            preview = f.read(500).decode('utf-8', errors='replace')
                        log('  -> 预览: %s' % preview[:150])
                    elif len(set(header[:32])) > 20:
                        log('  -> 高熵数据 (可能是加密的)')
                        log('  -> Header: %s' % header[:16].hex())
                    else:
                        log('  -> 未知格式, header: %s' % header[:16].hex())
                except: pass

        if round_n % 12 == 0:
            log('[心跳] 监控中...')

        time.sleep(2)

except KeyboardInterrupt:
    log('\n停止捕获')
    log('共捕获 %d 个文件' % len(os.listdir(OUTDIR)))
