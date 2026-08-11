"""
从中文文本位置回溯找出消息对象结构
1. 扫堆找中文文本
2. 回溯 0x80-0x200 字节，找 vtable 指针 (指向 weixin.dll 代码段)
3. 验证 +0x28 包含目标文本
4. 提取 vtable RVA 和对象地址
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

print(f"PID: {pid}  weixin.dll: 0x{wx_base:x}")
print()

# 枚举所有私有堆
heaps = []
addr = 0
while addr < 0x7fffffffffff:
    try:
        mbi = pymem.memory.virtual_query(pm.process_handle, addr)
        if mbi.State == 0x1000 and mbi.Type == 0x20000:
            if mbi.RegionSize >= 0x100000:
                heaps.append((addr, mbi.RegionSize))
        addr += mbi.RegionSize if mbi.RegionSize > 0 else 0x10000
    except:
        addr += 0x10000

print(f"堆: {len(heaps)} 块, {sum(s for _, s in heaps)//1024//1024}MB")
print()

# 针对含中文的大块区域进行深度扫描
chinese_pat = re.compile(b'([\xe4-\xe9][\xb8-\xbf][\x80-\xbf]){3,}')

found_objects = {}  # addr → object info
chunk_size = 0x100000

# 限制扫描量: 只扫最大的 10 块区域 (我们有 34935 个文本了，说明足够多区域有数据)
heaps.sort(key=lambda x: -x[1])
scan_targets = heaps[:10]

for idx, (rbase, rsize) in enumerate(scan_targets):
    print(f"堆 {idx+1}/{len(scan_targets)}: 0x{rbase:012x} ({rsize//1024//1024}MB)")
    t0 = time.time()
    pos = 0
    texts_in_region = 0

    while pos < rsize:
        try:
            chunk = pm.read_bytes(rbase + pos, min(chunk_size, rsize - pos))
            # 找中文文本
            for m in chinese_pat.finditer(chunk):
                text_start = m.start()
                text_abs = rbase + pos + text_start
                # 取文本前 20 字节用于验证
                raw_text = chunk[text_start:text_start+40].split(b'\x00')[0]
                try:
                    text_decoded = raw_text.decode('utf-8', errors='replace').strip()
                except:
                    continue
                if len(text_decoded) < 3:
                    continue
                texts_in_region += 1

                # 回溯: 从 text_start 往回最多 0x200 字节，找对象起始
                max_lookback = min(0x200, text_start)
                for lookback in range(0x80, max_lookback, 8):
                    candidate = text_abs - lookback
                    if candidate & 7 != 0:
                        continue
                    if candidate in found_objects:
                        continue
                    try:
                        obj_raw = pm.read_bytes(candidate, 0x80)
                        vt = struct.unpack('<Q', obj_raw[:8])[0]
                        # vtable 必须指向 weixin.dll
                        if vt < code_start or vt >= code_end:
                            continue

                        # 验证: +0x28 应当是 SSO string
                        # 尝试格式1: 首字节 = 内联长度
                        fb = obj_raw[0x28]
                        if 0 < fb <= 30 and fb < len(raw_text):
                            inline_text = obj_raw[0x29:0x29+fb].decode('utf-8', errors='replace')
                            if text_decoded[:10] in inline_text:
                                # 读 sender
                                sfb = obj_raw[0x38]
                                sender = ''
                                if 0 < sfb <= 30:
                                    sender = obj_raw[0x39:0x39+sfb].decode('utf-8', errors='replace')
                                found_objects[candidate] = {
                                    'vtable': vt,
                                    'vtable_rva': vt - wx_base,
                                    'content': inline_text,
                                    'sender': sender,
                                    'offset_text': text_start - lookback,
                                }
                                break  # 找到了，继续下一个文本

                        # 格式2: QWORD 指针
                        ptr, length = struct.unpack('<QQ', obj_raw[0x28:0x38])
                        if 0 < length <= 10000 and 0x100000 <= ptr < 0x7fffffffffff:
                            try:
                                heap_text = pm.read_bytes(ptr, min(length, 100)).decode('utf-8', errors='replace')
                                if text_decoded[:10] in heap_text:
                                    sptr = struct.unpack('<Q', obj_raw[0x38:0x40])[0]
                                    sender = ''
                                    if 0x100000 <= sptr < 0x7fffffffffff:
                                        try:
                                            slen = struct.unpack('<Q', obj_raw[0x40:0x48])[0]
                                            sender = pm.read_bytes(sptr, min(slen, 50)).decode('utf-8', errors='replace')
                                        except: pass
                                    found_objects[candidate] = {
                                        'vtable': vt,
                                        'vtable_rva': vt - wx_base,
                                        'content': heap_text,
                                        'sender': sender,
                                        'mode': 'heap',
                                    }
                                    break
                            except: pass
                    except:
                        pass
            pos += chunk_size
        except:
            pos += 0x10000

    elapsed = time.time() - t0
    print(f"  文本: {texts_in_region} | 找到对象: {len(found_objects)} | 耗时: {elapsed:.1f}s")
    if found_objects:
        # 打印最新的几个
        objs = list(found_objects.values())
        for o in objs[-3:]:
            print(f"    vtable: weixin.dll+0x{o['vtable_rva']:x} | {o['content'][:40]} | sender={o['sender'][:20]}")

print(f"\n=== 共 {len(found_objects)} 个消息对象 ===")

# 按 vtable RVA 分组
from collections import Counter
vtables = Counter()
for o in found_objects.values():
    vtables[o['vtable_rva']] += 1

print(f"\nvtable 分布:")
for rva, count in vtables.most_common(10):
    show = ''
    if found_objects:
        example = next(o for o in found_objects.values() if o['vtable_rva'] == rva)
        show = f" e.g. {example['content'][:30]}"
    print(f"  weixin.dll+0x{rva:x}: {count} 个{show}")

# 保存
path = r'C:\Users\OK\Desktop\wx_export\found_objects.json'
with open(path, 'w', encoding='utf-8') as f:
    json.dump({
        'total': len(found_objects),
        'vtables': dict(vtables),
        'objects': list(found_objects.values())[:500],
    }, f, ensure_ascii=False, indent=2)
print(f"\n已保存: {path}")
