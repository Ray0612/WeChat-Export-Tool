# -*- coding: utf-8 -*-
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

# 扫 0x1a400000000-0x1a400100000 找文本并 dump 周围内存
data = b''
try:
    data = pm.read_bytes(0x01a400000000, 0x100000)
except: pass

chinese_pat = re.compile(b'([\xe4-\xe9][\xb8-\xbf][\x80-\xbf]){3,}')

# 找几个有完整中文消息的文本
found = []
for m in chinese_pat.finditer(data):
    raw = data[m.start():m.start()+48].split(b'\x00')[0]
    try:
        text = raw.decode('utf-8', errors='replace').strip()
    except: continue
    if len(text) >= 6 and len(found) < 5:
        found.append((0x01a400000000 + m.start(), text, m.start()))

for abs_addr, text, offset in found:
    print(f"=== 0x{abs_addr:012x} → \"{text[:40]}\" ===")

    # dump 文本之前的 0x180 字节 (找对象头)
    start_dump = abs_addr - 0x200
    end_dump = abs_addr + 0x40
    start_dump = max(start_dump & ~0xf, 0x01a400000000)
    try:
        dump = pm.read_bytes(start_dump, end_dump - start_dump)
    except: continue

    text_off_in_dump = abs_addr - start_dump

    # 扫 vtable 指针
    print(f"  回溯找 vtable:")
    for lookback in range(0x10, 0x200, 8):
        cand = abs_addr - lookback
        if cand & 7: continue
        if cand < start_dump: continue
        idx = cand - start_dump
        if idx + 8 > len(dump): continue
        val = struct.unpack('<Q', dump[idx:idx+8])[0]
        if code_start <= val < code_end:
            rva = val - wx_base
            print(f"    -{lookback:3d} (0x{cand:012x}): weixin.dll+0x{rva:x}")

    # dump 从文本前的对齐地址开始
    aligned = (abs_addr - 0x80) & ~0xf
    dump2 = pm.read_bytes(aligned, 0xA0)
    text_off2 = abs_addr - aligned
    print(f"  内存布局:")
    for i in range(0, 0xA0, 16):
        hexs = ' '.join(f'{b:02x}' for b in dump2[i:i+16])
        asc = ''.join(chr(b) if 32<=b<127 else '.' for b in dump2[i:i+16])
        marker = ' <-- 文本' if aligned+i <= abs_addr < aligned+i+16 else ''
        print(f"    +{i:02x}: {hexs:48s} {asc}{marker}")

    # 试解析可能的 SSO string (多种偏移)
    for sso_off in range(0, 0x80, 8):
        fb = dump2[sso_off]
        if 1 <= fb <= 40:
            try:
                s = dump2[sso_off+1:sso_off+1+fb].decode('utf-8', errors='replace')
                if len(s) >= 3:
                    print(f"    +{sso_off:02x}: [inline len={fb}] {s[:40]}")
            except: pass

    # 试 QWORD ptr + length
    for sso_off in range(0, 0x80, 8):
        if sso_off + 16 > 0xA0: break
        ptr, length = struct.unpack('<QQ', dump2[sso_off:sso_off+16])
        if 1 <= length <= 500 and 0x100000 <= ptr < 0x7fffffffffff:
            try:
                raw_s = pm.read_bytes(ptr, min(length, 40))
                s = raw_s.decode('utf-8', errors='replace')
                if len(s) >= 3:
                    print(f"    +{sso_off:02x}: [ptr=0x{ptr:x} len={length}] {s}")
            except: pass

    print()
