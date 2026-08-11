"""
路线 A — 暴力扫描 vtable 匹配的消息对象
vtable = weixin.dll + 0x1b4158  (+0x28 = message_content)
用法: 开微信，运行脚本。然后翻聊天窗口。
"""
import pymem, psutil, struct, datetime, json, os, re, sys, time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

OUTDIR = r'C:\Users\OK\Desktop\wx_export'
os.makedirs(OUTDIR, exist_ok=True)

# ── 1. 找 Weixin.exe PID ──
pid = None
for proc in psutil.process_iter(['pid', 'name']):
    if proc.info['name'] == 'Weixin.exe':
        try:
            for f in proc.open_files():
                if 'message_0.db' in f.path:
                    pid = proc.info['pid']
                    break
        except:
            pass
        if pid: break
if not pid:
    print("找不到 Weixin.exe")
    sys.exit(1)

pm = pymem.Pymem(pid)

wx_base = None
for mod in pm.list_modules():
    if 'weixin.dll' in mod.name.lower():
        wx_base = mod.lpBaseOfDll
        break
if not wx_base:
    print("找不到 weixin.dll")
    sys.exit(1)

vtable_target = wx_base + 0x1b4158
vtable_bytes = struct.pack('<Q', vtable_target)

print(f"PID: {pid}  |  weixin.dll: 0x{wx_base:x}  |  vtable: 0x{vtable_target:x}")
print()

# ── 2. SSO string 读取 ──
def try_read_string(addr, max_len=128):
    try:
        raw = pm.read_bytes(addr, 24)
    except:
        return None
    # 格式1: 首字节为内联长度
    fb = raw[0]
    if 0 < fb <= 20 and all(32 <= b < 127 or b >= 0x80 for b in raw[1:1+fb]):
        return raw[1:1+fb].decode('utf-8', errors='replace').strip()
    # 格式2: QWORD 指针 + QWORD 长度
    ptr, length = struct.unpack('<QQ', raw[:16])
    if 0 < length <= 10000 and 0x100000 <= ptr < 0x7fffffffffff:
        try:
            data = pm.read_bytes(ptr, min(length, max_len))
            return data.decode('utf-8', errors='replace').strip()
        except:
            pass
    # 格式3: 从 addr 开始的 C 字符串
    try:
        data = pm.read_bytes(addr, 48)
        end = data.find(b'\x00')
        if end > 0:
            text = data[:end].decode('utf-8', errors='replace').strip()
            if len(text) >= 2: return text
    except:
        pass
    return None

def looks_like_msg(text):
    if not text or len(text) < 2: return False
    printable = sum(1 for c in text if 0x20 <= ord(c) < 0x7f or ord(c) >= 0x80)
    return printable >= len(text) * 0.5

# ── 3. 扫描: 用 bytes.find 批量搜 vtable ──
def scan_region(base, size):
    found = []
    hits = 0
    chunk_size = 0x10000  # 64KB
    pos = 0
    vtb_len = len(vtable_bytes)
    while pos < size:
        try:
            chunk = pm.read_bytes(base + pos, min(chunk_size, size - pos))
            off = 0
            while True:
                off = chunk.find(vtable_bytes, off)
                if off < 0: break
                addr = base + pos + off
                # 对齐检查 (8 字节对齐)
                if addr & 7 != 0:
                    off += 1
                    continue
                hits += 1
                if addr + 0x80 <= base + size:
                    content = try_read_string(addr + 0x28)
                    if content and looks_like_msg(content):
                        sender = try_read_string(addr + 0x38)
                        found.append({'addr': addr, 'content': content, 'sender': sender or ''})
                off += 8
            pos += chunk_size
        except:
            pos += 0x10000
    return found, hits

# ── 4. 枚举堆区 ──
def get_heaps():
    regions = []
    addr = 0
    while addr < 0x7fffffffffff:
        try:
            mbi = pymem.memory.virtual_query(pm.process_handle, addr)
            if mbi.State == 0x1000 and mbi.Type == 0x20000:
                if mbi.RegionSize >= 0x100000:
                    regions.append((addr, mbi.RegionSize))
            addr += mbi.RegionSize if mbi.RegionSize > 0 else 0x10000
        except:
            addr += 0x10000
    return regions

# ── 5. 主循环 ──
print("枚举内存区域...")
heaps = get_heaps()
print(f"找到 {len(heaps)} 个大块堆区 (≥1MB)")
total_mb = sum(sz for _, sz in heaps) // 1024 // 1024
print(f"总大小: {total_mb}MB")
print()

all_msgs = {}
seen = set()
round_n = 0

try:
    while True:
        round_n += 1
        now = datetime.datetime.now().strftime('%H:%M:%S')
        print(f"=== 第 {round_n} 轮 ({now}) ===", flush=True)

        t0 = time.time()
        new = 0
        total_hits = 0
        for rbase, rsz in heaps:
            results, hits = scan_region(rbase, rsz)
            total_hits += hits
            for r in results:
                if r['addr'] not in seen:
                    seen.add(r['addr'])
                    k = f"{r['content'][:50]}|{r['sender'][:30]}"
                    if k not in all_msgs:
                        all_msgs[k] = r
                        new += 1

        elapsed = time.time() - t0
        print(f"  vtable hits: {total_hits}  |  新消息: {new}  |  累计: {len(all_msgs)}  |  耗时: {elapsed:.1f}s")

        if new > 0:
            for m in list(all_msgs.values())[-min(new, 8):]:
                show = m['content'][:80] + '...' if len(m['content']) > 80 else m['content']
                sender = m['sender'][:20] if m['sender'] else '(?)'
                print(f"  [{sender}] {show}")

        path = os.path.join(OUTDIR, f'scan_round{round_n}_{int(time.time())}.json')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump({'round': round_n, 'total': len(all_msgs), 'msgs': list(all_msgs.values())},
                      f, ensure_ascii=False, indent=2)
        print(f"  保存: {path}")
        print()

        time.sleep(8)

except KeyboardInterrupt:
    print("\n停止")
    path = os.path.join(OUTDIR, f'scan_final_{int(time.time())}.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump({'total': len(all_msgs), 'msgs': list(all_msgs.values())},
                  f, ensure_ascii=False, indent=2)
    print(f"最终: {path}  |  共 {len(all_msgs)} 条")
