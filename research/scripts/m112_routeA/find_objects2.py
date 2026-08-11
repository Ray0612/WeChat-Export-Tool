"""
从中文文本回溯 — 直接扫 0x01a400000000-0x01a500000000 范围
"""
import pymem, psutil, struct, sys, re, time, json
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
print(f"PID: {pid}  weixin.dll: 0x{wx_base:x}  code: 0x{code_start:x}-0x{code_end:x}")
print()

# 直接扫 0x01a400000000-0x01a500000000
SCAN_START = 0x01a400000000
SCAN_END   = 0x01a500000000

chinese_pat = re.compile(b'([\xe4-\xe9][\xb8-\xbf][\x80-\xbf]){3,}')
chunk_size = 0x100000

found_objects = {}
found_count = 0

addr = SCAN_START
while addr < SCAN_END:
    try:
        mbi = pymem.memory.virtual_query(pm.process_handle, addr)
        if mbi.State != 0x1000:
            addr += max(mbi.RegionSize, 0x1000)
            continue
        if mbi.RegionSize == 0:
            addr += 0x1000
            continue

        # 扫这一个区域
        rsize = min(mbi.RegionSize, 0x200000)  # 最多 2MB
        data = pm.read_bytes(addr, rsize)

        # 找中文文本
        for m in chinese_pat.finditer(data):
            text_abs = addr + m.start()
            raw = data[m.start():m.start()+48].split(b'\x00')[0]
            try:
                text = raw.decode('utf-8', errors='replace').strip()
            except:
                continue
            if len(text) < 3:
                continue

            # 回溯找对象头
            max_lb = min(0x200, m.start())
            for lb in range(0x80, max_lb, 8):
                cand = text_abs - lb
                if cand & 7:
                    continue
                if cand in found_objects:
                    continue
                try:
                    obj_raw = pm.read_bytes(cand, 0x80)
                except:
                    continue
                vt = struct.unpack('<Q', obj_raw[:8])[0]
                if vt < code_start or vt >= code_end:
                    continue

                # 试 SSO 格式: 首字节长度
                fb = obj_raw[0x28]
                if 0 < fb <= 30:
                    try:
                        inline = obj_raw[0x29:0x29+fb].decode('utf-8', errors='replace')
                        if text[:8] in inline:
                            sfb = obj_raw[0x38]
                            sender = obj_raw[0x39:0x39+sfb].decode('utf-8', errors='replace') if 0 < sfb <= 30 else ''
                            found_objects[cand] = {
                                'vtable_rva': vt - wx_base, 'content': inline, 'sender': sender
                            }
                            found_count += 1
                            break
                    except:
                        pass

                # 试 SSO 格式: QWORD 指针
                ptr, length = struct.unpack('<QQ', obj_raw[0x28:0x38])
                if 0 < length <= 10000 and 0x100000 <= ptr < 0x7fffffffffff:
                    try:
                        hp = pm.read_bytes(ptr, min(length, 100)).decode('utf-8', errors='replace')
                        if text[:8] in hp:
                            sptr = struct.unpack('<Q', obj_raw[0x38:0x40])[0]
                            sender = ''
                            if 0x100000 <= sptr < 0x7fffffffffff:
                                try:
                                    slen = struct.unpack('<Q', obj_raw[0x40:0x48])[0]
                                    sender = pm.read_bytes(sptr, min(slen, 50)).decode('utf-8', errors='replace')
                                except: pass
                            found_objects[cand] = {
                                'vtable_rva': vt - wx_base, 'content': hp, 'sender': sender, 'mode': 'heap'
                            }
                            found_count += 1
                            break
                    except:
                        pass

        if found_count > 0 and found_count % 10 == 0:
            print(f"  0x{addr:012x}: {len(found_objects)} 个对象...", end='\r')

        addr += mbi.RegionSize if mbi.RegionSize > 0 else 0x1000
    except:
        addr += 0x10000

print(f"\n\n=== 共 {len(found_objects)} 个对象 ===")

# 按 vtable RVA 分组
from collections import Counter
vtables = Counter()
for o in found_objects.values():
    vtables[o['vtable_rva']] += 1

print(f"\nvtable 分布:")
for rva, count in vtables.most_common(15):
    ex = next(o for o in found_objects.values() if o['vtable_rva'] == rva)
    print(f"  weixin.dll+0x{rva:x}: {count} 个 | e.g. {ex['content'][:40]} | sender={ex['sender'][:20]}")

# 显示内容
print(f"\n消息内容样例:")
for addr, o in sorted(found_objects.items())[:30]:
    print(f"  0x{addr:012x} [{o['sender'][:20]}] {o['content'][:60]}")
