"""
实时监控 v2 — 快速循环扫 0x1a400000000-0x1a600000000 找中文
当文本出现 → 回溯找 vtable 对象
用法: 开微信 → 运行 → 翻聊天窗口
"""
import pymem, psutil, struct, sys, re, time, json, datetime
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

OUTDIR = r'C:\Users\OK\Desktop\wx_export'

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
print(f"PID: {pid}  weixin.dll: 0x{wx_base:x}")

# 监控 0x1a400000000-0x1a600000000 范围
# 先枚举范围内的所有子区域
sub_regions = []
addr = 0x1a400000000
while addr < 0x1a600000000:
    try:
        mbi = pymem.memory.virtual_query(pm.process_handle, addr)
        if mbi.State == 0x1000 and mbi.RegionSize > 0:
            sub_regions.append((addr, mbi.RegionSize))
        addr += mbi.RegionSize if mbi.RegionSize > 0 else 0x10000
    except:
        addr += 0x10000

print(f"子区域: {len(sub_regions)} 块, {sum(s for _,s in sub_regions)//1024//1024}MB")
print()

chinese_pat = re.compile(b'([\xe4-\xe9][\xb8-\xbf][\x80-\xbf]){3,}')

# 每次只扫 1MB 小区域，快速轮转
total_texts = {}
total_objects = {}
round_n = 0
samples_for_backtrack = []

try:
    while True:
        round_n += 1
        now = datetime.datetime.now().strftime('%H:%M:%S')
        new_texts = 0

        # 每轮只扫 1/4 的区域 (快速轮转)
        region_batch = len(sub_regions) // 4
        start_idx = (round_n - 1) % 4 * region_batch
        batch = sub_regions[start_idx:start_idx + region_batch]

        for rbase, rsize in batch:
            # 每个区域只读前 1MB (如果 > 1MB)
            read_size = min(rsize, 0x100000)
            try:
                data = pm.read_bytes(rbase, read_size)
            except:
                continue

            for m in chinese_pat.finditer(data):
                raw = data[m.start():m.start()+48].split(b'\x00')[0]
                try:
                    text = raw.decode('utf-8', errors='replace').strip()
                except:
                    continue
                if len(text) < 4:
                    continue
                if text not in total_texts:
                    abs_addr = rbase + m.start()
                    total_texts[text] = abs_addr
                    new_texts += 1
                    samples_for_backtrack.append((abs_addr, text))

        if new_texts > 0:
            print(f"[{now}] +{new_texts} 文本 | 累计 {len(total_texts)}")

            # 对新文本做回溯找 vtable
            for abs_addr, text in samples_for_backtrack[-new_texts:]:
                max_lb = 0x200
                for lb in range(0x80, max_lb, 8):
                    cand = abs_addr - lb
                    if cand & 7:
                        continue
                    if cand in total_objects:
                        continue
                    try:
                        obj_raw = pm.read_bytes(cand, 0x80)
                    except:
                        continue
                    vt = struct.unpack('<Q', obj_raw[:8])[0]
                    if vt < code_start or vt >= code_end:
                        continue
                    # 试 SSO 格式
                    fb = obj_raw[0x28]
                    if 0 < fb <= 30:
                        try:
                            content = obj_raw[0x29:0x29+fb].decode('utf-8', errors='replace')
                            if text[:8] in content:
                                sfb = obj_raw[0x38]
                                sender = obj_raw[0x39:0x39+sfb].decode('utf-8', errors='replace') if 0 < sfb <= 30 else ''
                                total_objects[cand] = {'vtable_rva': vt - wx_base, 'content': content, 'sender': sender}
                                rva = vt - wx_base
                                print(f"    >>> vtable weixin.dll+0x{rva:x} at 0x{cand:012x}: [{sender[:20]}] {content[:50]}")
                                break
                        except:
                            pass
                    # 试 heap ptr 格式
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
                                total_objects[cand] = {'vtable_rva': vt - wx_base, 'content': hp, 'sender': sender, 'mode': 'heap'}
                                rva = vt - wx_base
                                print(f"    >>> vtable weixin.dll+0x{rva:x} at 0x{cand:012x} [{sender[:20]}] {hp[:50]}")
                                break
                        except:
                            pass

        if total_objects and round_n % 4 == 0:
            # 打印统计
            vtables = {}
            for o in total_objects.values():
                rva = o['vtable_rva']
                vtables[rva] = vtables.get(rva, 0) + 1
            print(f"  vtable 分布: {', '.join(f'+0x{rva:x}={cnt}' for rva, cnt in vtables.items())}")

        if new_texts > 0 and round_n % 8 == 0:
            path = f'{OUTDIR}/live_{int(time.time())}.json'
            with open(path, 'w', encoding='utf-8') as f:
                json.dump({
                    'total_texts': len(total_texts),
                    'total_objects': len(total_objects),
                    'objects': list(total_objects.values())[-200:],
                    'sample_texts': list(total_texts.keys())[-200:],
                }, f, ensure_ascii=False, indent=2)
            print(f"  保存: {path}")

        time.sleep(1)

except KeyboardInterrupt:
    print("\n停止")
    path = f'{OUTDIR}/live_final_{int(time.time())}.json'
    with open(path, 'w', encoding='utf-8') as f:
        json.dump({
            'total_texts': len(total_texts),
            'total_objects': len(total_objects),
            'objects': list(total_objects.values()),
        }, f, ensure_ascii=False, indent=2)
    print(f"保存: {path}")
