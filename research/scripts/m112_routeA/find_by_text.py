"""
备用方案 — 直接用中文消息文本定位对象
1. 扫内存中的中文文本 (3+ 个连续中文字符)
2. 验证文本周围的 0x80 字节范围内是否有 vtable 模式
3. 提取 vtable 地址和对象布局
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

wx_base = None
for mod in pm.list_modules():
    if 'weixin.dll' in mod.name.lower():
        wx_base = mod.lpBaseOfDll
        break

code_start = wx_base
code_end = wx_base + 0xaf0e000

print(f"PID: {pid}  weixin.dll: 0x{wx_base:x}")
print()

# 找堆区域
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

print(f"堆区域: {len(heaps)} 块")
print()

# UTF-8 中文字符范围: 0xE4 0xB8-0xBF xxx 起的三字节序列
# 简化: 搜连续的宽字符
chinese_pattern = re.compile(b'([\xe4-\xe9][\xb8-\xbf][\x80-\xbf]){3,}')

found_objects = {}  # addr → {'vtable': ..., 'content': ..., 'sender': ...}

# 只扫前几块堆 (用户可能正在聊天的区域)
scan_limit = min(5, len(heaps))
for idx in range(scan_limit):
    rbase, rsize = heaps[idx]
    print(f"扫描堆 {idx+1}/{scan_limit}: 0x{rbase:x} ({rsize//1024//1024}MB)")
    chunk_size = 0x100000
    pos = 0
    t0 = time.time()

    while pos < rsize:
        try:
            chunk = pm.read_bytes(rbase + pos, min(chunk_size, rsize - pos))
            # 找中文文本
            for m in chinese_pattern.finditer(chunk):
                text_start_in_chunk = m.start()
                text_abs = rbase + pos + text_start_in_chunk
                text = chunk[text_start_in_chunk:text_start_in_chunk+60].split(b'\x00')[0]
                text = text.decode('utf-8', errors='replace').strip()
                if len(text) < 3: continue

                # 回溯检查前面 0x80 字节是不是对象
                for lookback in range(0x80, min(0x200, text_start_in_chunk), 8):
                    candidate_start = text_abs - lookback
                    if candidate_start & 7 != 0: continue
                    try:
                        # 检查这里是不是对象: 有 vtable 指针指向 weixin.dll
                        obj_raw = pm.read_bytes(candidate_start, 0x80)
                        vt = struct.unpack('<Q', obj_raw[:8])[0]
                        if code_start <= vt < code_end:
                            # 检查 +0x28 是不是包含我们的文本
                            content_start = candidate_start + 0x28
                            # 试多种 SSO 格式
                            fb = pm.read_bytes(content_start, 1)[0]
                            if 0 < fb <= 30:
                                raw = pm.read_bytes(content_start, fb + 1)
                                candidate_text = raw[1:1+fb].decode('utf-8', errors='replace')
                                if text[:10] in candidate_text:
                                    addr = candidate_start
                                    if addr not in found_objects:
                                        sender_raw = b''
                                        try:
                                            sfb = pm.read_bytes(addr + 0x38, 1)[0]
                                            if 0 < sfb <= 30:
                                                sdata = pm.read_bytes(addr + 0x38, sfb + 1)
                                                sender = sdata[1:1+sfb].decode('utf-8', errors='replace')
                                            else:
                                                sender = ''
                                        except:
                                            sender = ''
                                        found_objects[addr] = {
                                            'vtable': vt,
                                            'vtable_rva': vt - wx_base,
                                            'content': candidate_text,
                                            'sender': sender,
                                        }
                                        break
                    except:
                        pass

            pos += chunk_size
        except:
            pos += 0x10000

    elapsed = time.time() - t0
    print(f"  耗时: {elapsed:.1f}s | 当前: {len(found_objects)} 个对象")

print(f"\n总共找到 {len(found_objects)} 个消息对象\n")

# 去重 + 汇总
vtables = set()
for addr, obj in sorted(found_objects.items(), key=lambda x: x[0]):
    rva = obj['vtable_rva']
    vtables.add(rva)
    print(f"  0x{addr:x}")
    print(f"    vtable: {obj['vtable']:016x} (weixin.dll+0x{rva:x})")
    print(f"    内容: {obj['content'][:60]}")
    print(f"    发送者: {obj['sender'][:30]}")
    print()

print(f"共 {len(vtables)} 个唯一的 vtable:")
for v in sorted(vtables):
    count = sum(1 for o in found_objects.values() if o['vtable_rva'] == v)
    print(f"  weixin.dll+0x{v:x} ({count} 个对象)")
