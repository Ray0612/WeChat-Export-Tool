"""
诊断 — 验证 vtable 地址 + 找到消息对象所在区域
"""
import pymem, psutil, struct, sys
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
wx_base = None
for mod in pm.list_modules():
    if 'weixin.dll' in mod.name.lower():
        wx_base = mod.lpBaseOfDll
        break

print(f"PID: {pid}")
print(f"weixin.dll base: 0x{wx_base:x}")
print(f"rva (ghidra): 180000000")
print(f"delta: wx_base - 0x180000000 = 0x{wx_base - 0x180000000:x}")
print()

# 验证 vtable 地址在 weixin.dll 范围内是否正确
vt_base = wx_base + 0x1b4158
vt_derived = wx_base + 0x1b4308

print("=== 验证 vtable 地址 ===")
for name, addr in [("基类 vtable (+0x1b4158)", vt_base), ("派生 vtable (+0x1b4308)", vt_derived)]:
    try:
        data = pm.read_bytes(addr, 32)
        # 前8字节应该是函数指针
        func_ptr = struct.unpack('<Q', data[:8])[0]
        in_dll = wx_base <= func_ptr < wx_base + 0xaf0e000
        print(f"  {name}: 0x{addr:x} → 首函数 → 0x{func_ptr:x} (in weixin.dll: {in_dll})")
        hexs = ' '.join(f'{b:02x}' for b in data[:24])
        print(f"    raw: {hexs}")
    except Exception as e:
        print(f"  {name}: ERROR {e}")

print()

# 在所有内存区域类型中搜索 vtable
print("=== 搜索 vtable 在内存中的出现 ===")
vt_bytes = struct.pack('<Q', vt_base)
vt_bytes_derived = struct.pack('<Q', vt_derived)

# 也试试 Ghidra 相对地址
ghidra_vt = 0x180000000 + 0x1b4158
ghidra_vt_bytes = struct.pack('<Q', ghidra_vt)

total_vt = 0
total_vtd = 0
total_ghidra = 0
addr = 0
while addr < 0x7fffffffffff:
    try:
        mbi = pymem.memory.virtual_query(pm.process_handle, addr)
        if mbi.State == 0x1000 and mbi.RegionSize <= 0x1000000:  # ≤16MB
            try:
                chunk = pm.read_bytes(addr, min(mbi.RegionSize, 0x10000))  # just check first 64KB
                c_vt = chunk.count(vt_bytes)
                c_vtd = chunk.count(vt_bytes_derived)
                c_gh = chunk.count(ghidra_vt_bytes)
                if c_vt or c_vtd or c_gh:
                    print(f"  0x{addr:x} ({mbi.Type:08x} {mbi.Protect:08x}) [{mbi.RegionSize//1024}KB]")
                    if c_vt: print(f"    基类 vtable (runtime): {c_vt}")
                    if c_vtd: print(f"    派生 vtable (runtime): {c_vtd}")
                    if c_gh: print(f"    Ghidra 地址: {c_gh}")
                    total_vt += c_vt
                    total_vtd += c_vtd
                    total_ghidra += c_gh
            except: pass
        addr += mbi.RegionSize if mbi.RegionSize > 0 else 0x10000
    except:
        addr += 0x10000

print(f"\n总计:")
print(f"  基类 vtable (runtime): {total_vt}")
print(f"  派生 vtable (runtime): {total_vtd}")
print(f"  Ghidra 地址: {total_ghidra}")
