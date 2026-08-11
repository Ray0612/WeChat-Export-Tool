"""
在 weixin.dll 中找到消息对象真正的 vtable 地址
思路: 搜 .rdata 中所有虚函数表，找包含 0x80 字节消息对象特征的
"""
import pymem, psutil, struct, sys, re
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

# 获取 weixin.dll 信息
wx_base = None
wx_size = 0
for mod in pm.list_modules():
    if 'weixin.dll' in mod.name.lower():
        wx_base = mod.lpBaseOfDll
        wx_size = mod.SizeOfImage
        break

print(f"weixin.dll: base=0x{wx_base:x}, size=0x{wx_size:x} ({wx_size//1024//1024}MB)")

# 找到 .rdata 段范围
# 扫描模块内的区域，找 PE 段信息
rdata_start = 0
rdata_end = 0
addr = wx_base
while addr < wx_base + wx_size:
    try:
        mbi = pymem.memory.virtual_query(pm.process_handle, addr)
        if mbi.State != 0x1000:
            addr += max(mbi.RegionSize, 0x10000)
            continue
        # 检查保护属性: 只读数据通常是 PAGE_READONLY
        if mbi.Protect == 0x02:  # PAGE_READONLY
            if rdata_start == 0:
                rdata_start = addr
            rdata_end = addr + mbi.RegionSize
        addr += mbi.RegionSize
    except:
        addr += 0x10000

print(f".rdata: 0x{rdata_start:x} - 0x{rdata_end:x} ({rdata_end - rdata_start} bytes)")
print()

# 策略: 在 .rdata 中搜索所有 vtable 候选
# vtable 的特征: 连续 N 个 8 字节指针指向 weixin.dll 代码段
code_start = wx_base
code_end = wx_base + 0xaf0e000  # 代码段大小

print("在 .rdata 中搜索 vtable 候选...")
vtable_candidates = []

# 读 .rdata 块 (分段读)
chunk_size = 0x100000  # 1MB chunks
pos = rdata_start
while pos < rdata_end:
    try:
        chunk = pm.read_bytes(pos, min(chunk_size, rdata_end - pos))
        # 滑窗扫描: 每 8 字节检查是否是指向代码段的指针
        for off in range(0, len(chunk) - 16, 8):
            val = struct.unpack('<Q', chunk[off:off+8])[0]
            # 候选条件: 指向 weixin.dll 代码段
            if code_start <= val < code_end:
                # 检查这是否是 vtable 条目 (前4字节是有效指令?)
                # 真正的 vtable 应该有多个连续的函数指针
                # 即当前地址的 -8 和 +8 也应该是代码指针
                abs_addr = pos + off
                # 检查周围几个条目
                nearby_ok = 0
                for delta in [-8, 8, 16, 24, 32]:
                    try:
                        nv = struct.unpack('<Q', chunk[off+delta:off+delta+8])[0]
                        if code_start <= nv < code_end:
                            nearby_ok += 1
                    except: pass
                if nearby_ok >= 3:  # 至少 3 个连续函数指针
                    vtable_candidates.append(abs_addr)
        pos += chunk_size
        print(f"  扫到 0x{pos:x}... ({len(vtable_candidates)} 候选)", end='\r')
    except:
        pos += 0x10000

print(f"\n找到 {len(vtable_candidates)} 个 vtable 候选")
print()

# 对这些候选去重 (相邻8字节算同一个vtable)
deduped = []
for c in vtable_candidates:
    if not deduped or c > deduped[-1] + 16:
        deduped.append(c)

print(f"去重后: {len(deduped)} 个唯一的 vtable")
print()

# 检查与 0x1b4158 最近的 vtable
target_rva = 0x1b4158
target_abs = wx_base + target_rva
print(f"目标: weixin.dll+0x{target_rva:x} = 0x{target_abs:x}")
print()

nearest = None
nearest_dist = float('inf')
for v in deduped:
    dist = abs(v - target_abs)
    if dist < nearest_dist:
        nearest_dist = dist
        nearest = v

if nearest:
    nearest_rva = nearest - wx_base
    print(f"最近的 vtable: weixin.dll+0x{nearest_rva:x} = 0x{nearest:x} (距离 = {nearest_dist})")
    # dump 内容
    data = pm.read_bytes(nearest, 64)
    print(f"  前 8 个函数指针:")
    for i in range(8):
        ptr = struct.unpack('<Q', data[i*8:i*8+8])[0]
        if code_start <= ptr < code_end:
            in_dll = True
        else:
            in_dll = False
        print(f"    [{i}] 0x{ptr:x} (in dll: {in_dll})")

print()

# 也看看目标地址附近
print(f"目标地址 0x{target_abs:x} 附近的内存:")
for delta in [-48, -40, -32, -24, -16, -8, 0, 8, 16, 24, 32, 40, 48]:
    addr = target_abs + delta
    try:
        val = struct.unpack('<Q', pm.read_bytes(addr, 8))[0]
        in_code = code_start <= val < code_end
        print(f"  {delta:+3d}: 0x{addr:x} = 0x{val:x} {'<- CODE' if in_code else ''}")
    except:
        print(f"  {delta:+3d}: 0x{addr:x} = (unreadable)")
