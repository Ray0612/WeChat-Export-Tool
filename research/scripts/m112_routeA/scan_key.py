# -*- coding: utf-8 -*-
"""
路线 B — 扫 WeChatAppEx 内存找 SQLCipher key
Key 可能在:
1. sqlite3_key_v2 的调用参数 (flue.dll+0x2a9c805)
2. 32/64 字节的高熵数据块 (AES key 特征)
3. 已知 key 格式: `0x` 开头的 hex string
"""
import pymem, psutil, struct, sys, os, time, re
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# 找 WeChatAppEx PID
target_pids = []
for proc in psutil.process_iter(['pid', 'name']):
    if 'WeChatAppEx' in proc.info['name']:
        target_pids.append(proc.info['pid'])

print(f"WeChatAppEx PID(s): {target_pids}")

if not target_pids:
    print("找不到 WeChatAppEx, 尝试 Weixin.exe...")
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.info['name'] == 'Weixin.exe':
            target_pids.append(proc.info['pid'])
            break

for pid in target_pids:
    print(f"\n=== PID {pid} ===")
    try:
        pm = pymem.Pymem(pid)
    except:
        print(f"  无法打开进程")
        continue

    # 找 flue.dll (仅在 WeChatAppEx 中)
    flue_base = None
    for mod in pm.list_modules():
        if 'flue.dll' in mod.name.lower():
            flue_base = mod.lpBaseOfDll
            print(f"  flue.dll: 0x{flue_base:x}")
            break

    # 枚举内存区域
    regions = []
    addr = 0
    while addr < 0x7fffffffffff:
        try:
            mbi = pymem.memory.virtual_query(pm.process_handle, addr)
            if mbi.State == 0x1000 and mbi.Type == 0x20000 and 0x10000 <= mbi.RegionSize <= 0x1000000:
                regions.append((addr, mbi.RegionSize))
            addr += mbi.RegionSize if mbi.RegionSize > 0 else 0x10000
        except:
            addr += 0x10000

    print(f"  堆区域: {len(regions)} 块, {sum(s for _,s in regions)//1024//1024}MB")

    # 搜 key 模式: 32字节高熵 + '0x' hex string
    # SQLCipher key 通常以 hex string 形式传递: "0xABCDEF012345..."
    hex_key_pat = re.compile(b'0x[0-9a-fA-F]{64,128}')

    key_candidates = []
    for rbase, rsize in regions:
        try:
            data = pm.read_bytes(rbase, min(rsize, 0x100000))
        except:
            continue
        for m in hex_key_pat.finditer(data):
            key_str = data[m.start():m.end()].decode('ascii')
            key_candidates.append((rbase + m.start(), key_str[:70]))
        if len(key_candidates) > 100:
            break

    print(f"  Hex key 候选: {len(key_candidates)}")
    for addr, key in key_candidates[:10]:
        print(f"    0x{addr:x}: {key}...")

    # 如果没有 hex key, 搜 32/64 字节高熵 (AES key 原始字节)
    if not key_candidates:
        print(f"  搜索 AES key 特征 (32/64 字节高熵)...")
        entropy_candidates = []
        for rbase, rsize in regions[:50]:  # 只扫前 50 块
            try:
                data = pm.read_bytes(rbase, min(rsize, 0x100000))
            except:
                continue
            for off in range(0, len(data) - 32, 4):
                chunk = data[off:off+32]
                # 统计不同字节数 (高熵 ≈ 28+ 不同字节)
                distinct = len(set(chunk))
                if distinct >= 28 and b'\x00' not in chunk[:8]:
                    entropy_candidates.append((rbase + off, chunk.hex()[:64]))
                    if len(entropy_candidates) >= 20:
                        break
            if entropy_candidates:
                break

        print(f"  高熵 32-byte 候选: {len(entropy_candidates)}")
        for addr, key in entropy_candidates[:5]:
            print(f"    0x{addr:x}: {key}")

    # sqlite3_key_v2 调用参数扫描
    if flue_base:
        print(f"\n  搜索 sqlite3_key_v2 附近的关键参数...")
        sqlite3_key_addr = flue_base + 0x2a9c805
        try:
            code_nearby = pm.read_bytes(sqlite3_key_addr, 100)
            print(f"    函数附近代码 (首 20B): {code_nearby[:20].hex()}")
        except:
            print(f"    无法读取 sqlite3_key_v2 地址")
