# -*- coding: utf-8 -*-
"""
扫描全部内存，找到当前 Weixin.exe 进程中中文文本所在的区域
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

print(f"PID: {pid}")
pm = pymem.Pymem(pid)
wx_base = None
for mod in pm.list_modules():
    if 'weixin.dll' in mod.name.lower():
        wx_base = mod.lpBaseOfDll
        break
print(f"weixin.dll: 0x{wx_base:x}")
print()

chinese_pat = re.compile(b'([\xe4-\xe9][\xb8-\xbf][\x80-\xbf]){3,}')

# 枚举所有区域并快速扫第一个 64KB 看是否有中文文本
regions_with_text = []
addr = 0
while addr < 0x7fffffffffff:
    try:
        mbi = pymem.memory.virtual_query(pm.process_handle, addr)
        if mbi.State == 0x1000 and mbi.RegionSize > 0:
            # 只读前 64KB 做快速检测
            check_size = min(mbi.RegionSize, 0x10000)
            try:
                data = pm.read_bytes(addr, check_size)
                if chinese_pat.search(data):
                    regions_with_text.append((addr, mbi.RegionSize, mbi.Type))
            except: pass
        addr += mbi.RegionSize if mbi.RegionSize > 0 else 0x10000
    except:
        addr += 0x10000

print(f"包含中文文本的区域: {len(regions_with_text)}")
print()

# 按地址排序
regions_with_text.sort(key=lambda x: x[0])

# 分组显示 (相邻区域合并)
if regions_with_text:
    last_end = 0
    group_start = 0
    group_end = 0
    for rbase, rsize, rtype in regions_with_text:
        if rbase > last_end + 0x100000:  # 超过 1MB 间隔分新组
            if group_end > 0:
                type_str = "priv" if rtype == 0x20000 else ("map" if rtype == 0x40000 else "img")
                print(f"  0x{group_start:012x} - 0x{group_end:012x} ({group_end-group_start}MB) [{type_str}]")
            group_start = rbase
            group_end = rbase + rsize
        else:
            group_end = max(group_end, rbase + rsize)
        last_end = rbase + rsize
    type_str = "priv" if rtype == 0x20000 else ("map" if rtype == 0x40000 else "img")
    print(f"  0x{group_start:012x} - 0x{group_end:012x} ({(group_end-group_start)//1024//1024}MB) [{type_str}]")
else:
    print("没有找到中文文本。")
    print("可能原因: 没有打开聊天窗口翻页，或数据不存在于 Weixin.exe 内存中")
