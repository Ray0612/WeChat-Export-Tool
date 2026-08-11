"""
Debug: 看文本地址周围的内存布局
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

wx_base = None
for mod in pm.list_modules():
    if 'weixin.dll' in mod.name.lower():
        wx_base = mod.lpBaseOfDll
        break

code_start = wx_base
code_end = wx_base + 0xaf0e000

# 找一个已知的文本地址
# 从 scan_heaps.py 输出知道的: "两个小猫猫就喜欢站在路中间呀" at 0x01a400053020
test_addrs = [0x01a400053020, 0x01a40007b6c1, 0x01a400052fe0, 0x01a40007b607, 0x01a400044caa]

for test_addr in test_addrs:
    # 先检查这个地址是否可读
    try:
        mbi = pymem.memory.virtual_query(pm.process_handle, test_addr)
        print(f"地址 0x{test_addr:012x}:")
        print(f"  State=0x{mbi.State:08x} Type=0x{mbi.Type:08x} Protect=0x{mbi.Protect:08x}")
        print(f"  RegionBase=0x{mbi.BaseAddress:012x} RegionSize=0x{mbi.RegionSize:x}")

        # 读该区域前 256 字节
        region_start = test_addr & ~0xfff  # page align
        data = pm.read_bytes(region_start, 256)

        # 找 0x01a400053020 在其中的偏移
        offset_in_data = test_addr - region_start
        print(f"  文本在数据中的偏移: 0x{offset_in_data:x}")

        # 往前读 0x200 字节
        lookback_start = max(region_start, test_addr - 0x200)
        lookback_data = pm.read_bytes(lookback_start, test_addr + 0x50 - lookback_start)
        print(f"  往前 0x200: 从 0x{lookback_start:012x}, {len(lookback_data)} 字节")
        print()

        # 打印周围内存 (从 test_addr-0x100 到 test_addr+0x30)
        start = max(lookback_start, test_addr - 0x100)
        dump = pm.read_bytes(start, 0x130)
        print(f"  [{start:012x}] 周围 0x130 字节:")
        print(f"  {'偏移':>8s} {'hex':>48s}  ascii")
        for i in range(0, len(dump), 16):
            a = start + i
            hexs = ' '.join(f'{b:02x}' for b in dump[i:i+16])
            asc = ''.join(chr(b) if 32 <= b < 127 else '.' for b in dump[i:i+16])
            marker = ' <-- 文本' if a + 16 > test_addr >= a else ''
            print(f"  +{i:04x}: {hexs:48s} {asc}{marker}")

        # 回溯扫描可能的对象起始
        print(f"\n  回溯扫描 (从 test_addr 往回 -0x10 到 -0x200):")
        text_abs = test_addr
        for lb in range(0x10, 0x200, 8):
            cand = text_abs - lb
            if cand & 7: continue
            try:
                val = struct.unpack('<Q', pm.read_bytes(cand, 8))[0]
                in_code = code_start <= val < code_end
                if in_code:
                    print(f"    回溯 -{lb:3d} (0x{cand:012x}): vtable=0x{val:016x} in_dll={in_code}")
                    # 读整个对象
                    obj = pm.read_bytes(cand, 0x80)
                    for j in range(8):
                        qw = struct.unpack('<Q', obj[j*8:j*8+8])[0]
                        qw_in_code = code_start <= qw < code_end
                        chk = ''
                        if j == 5:  # +0x28
                            chk = ' <- +0x28 content'
                        if j == 7:  # +0x38
                            chk = ' <- +0x38 sender'
                        print(f"      +{j*2:02x}: 0x{qw:016x}{' <- code' if qw_in_code else ''}{chk}")
                    # 试读 +0x28 SSO
                    fb = obj[0x28]
                    if 0 < fb <= 30:
                        txt = obj[0x29:0x29+fb].decode('utf-8', errors='replace')
                        print(f"      +0x28 inline({fb}): [{txt}]")

                    # +0x38 SSO
                    sfb = obj[0x38]
                    if 0 < sfb <= 30:
                        stxt = obj[0x39:0x39+sfb].decode('utf-8', errors='replace')
                        print(f"      +0x38 sender({sfb}): [{stxt}]")
                    print()
            except: pass

    except Exception as e:
        print(f"地址 0x{test_addr:012x}: ERROR {e}")
    print("---\n")
