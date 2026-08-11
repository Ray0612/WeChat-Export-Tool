"""
扫描 — 枚举所有堆区大小 + 在已知地址范围 0x1a400000000-0x1a600000000 搜中文
"""
import pymem, psutil, struct, sys, re, time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

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

# 枚举所有私有堆，按大小排序
heaps = []
addr = 0
while addr < 0x7fffffffffff:
    try:
        mbi = pymem.memory.virtual_query(pm.process_handle, addr)
        if mbi.State == 0x1000 and mbi.Type == 0x20000:
            if mbi.RegionSize >= 0x10000:
                heaps.append((addr, mbi.RegionSize, mbi.Protect))
        addr += mbi.RegionSize if mbi.RegionSize > 0 else 0x10000
    except:
        addr += 0x10000

heaps.sort(key=lambda x: -x[1])

print(f"所有堆区 (按大小排序):")
total = 0
for rbase, rsize, rprot in heaps[:30]:
    print(f"  0x{rbase:012x} - 0x{rbase+rsize:012x} ({rsize//1024//1024:4d}MB) protect=0x{rprot:08x}")
    total += rsize
print(f"  ... (共 {len(heaps)} 块, {total//1024//1024}MB)")
print()

# 特别看 0x1a400000000 附近的区域
print(f"=== 0x1a400000000 附近的区域 ===")
nearby = [(a, s) for a, s, p in heaps if 0x1a400000000 <= a < 0x1a600000000]
nearby.sort(key=lambda x: x[0])
for rbase, rsize in nearby:
    print(f"  0x{rbase:012x} - 0x{rbase+rsize:012x} ({rsize//1024//1024:4d}MB)")
print(f"  共 {len(nearby)} 块")

# 搜中文文本
print(f"\n=== 扫 0x1a400000000-0x1a600000000 找中文 ===")
chinese_pat = re.compile(b'([\xe4-\xe9][\xb8-\xbf][\x80-\xbf]){2,}')

found_texts = []
for rbase, rsize in nearby:
    chunk_size = 0x100000
    pos = 0
    while pos < rsize:
        try:
            chunk = pm.read_bytes(rbase + pos, min(chunk_size, rsize - pos))
            for m in chinese_pat.finditer(chunk):
                text = chunk[m.start():m.start()+80].split(b'\x00')[0]
                try:
                    decoded = text.decode('utf-8', errors='replace')
                    if len(decoded) >= 3:
                        found_texts.append((rbase + pos + m.start(), decoded.strip()))
                except: pass
            pos += chunk_size
        except:
            pos += 0x10000

print(f"找到 {len(found_texts)} 个中文文本\n")
for addr, text in found_texts[:50]:
    show = text[:60]
    print(f"  0x{addr:012x}: {show}")
