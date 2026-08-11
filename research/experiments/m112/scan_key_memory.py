# -*- coding: utf-8 -*-
"""
在 WeChatAppEx 内存中搜索 SQLCipher 的 64 字节 key
已知: key 是 64 字节 (32 enc + 32 hmac), 高熵
WeChat 正在运行，key 一定在进程内存中
"""
import pymem, psutil, struct, sys, hashlib, os, time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

OUTDIR = r'C:\Users\OK\Desktop\wx_export\backup_experiment'
os.makedirs(OUTDIR, exist_ok=True)

# Find WeChatAppEx PIDs
pids = []
for proc in psutil.process_iter(['pid', 'name']):
    if 'WeChatAppEx' in proc.info['name']:
        pids.append(proc.info['pid'])

print(f'WeChatAppEx PIDs: {pids}')

for pid in pids:
    print(f'\n=== PID {pid} ===')
    try:
        pm = pymem.Pymem(pid)
    except:
        print('  Cannot open')
        continue

    # Find flue.dll base
    flue_base = None
    for mod in pm.list_modules():
        if 'flue.dll' in mod.name.lower():
            flue_base = mod.lpBaseOfDll
            print(f'  flue.dll: 0x{flue_base:x}')
            print(f'  sqlite3_key_v2: 0x{flue_base + 0x2a9c805:x}')
            break

    # Search heap regions for 64-byte high-entropy blocks near flue
    # Strategy: find 64 consecutive bytes with high entropy (SQLCipher key)
    print('  Scanning heaps for 64-byte high-entropy blocks...')

    candidates = []
    region_count = 0
    addr = 0
    while addr < 0x7fffffffffff:
        try:
            mbi = pymem.memory.virtual_query(pm.process_handle, addr)
            if mbi.State == 0x1000 and mbi.Type == 0x20000:
                if mbi.RegionSize <= 0x100000:  # ≤ 1MB
                    try:
                        data = pm.read_bytes(addr, mbi.RegionSize)
                    except:
                        addr += max(mbi.RegionSize, 0x1000)
                        continue
                    region_count += 1

                    for off in range(0, len(data) - 64, 8):
                        chunk = data[off:off+64]
                        # Check entropy: high distinct byte count
                        distinct = len(set(chunk))
                        if distinct >= 55 and chunk[:4] != b'\x00\x00\x00\x00':
                            # Potential key! Check if it looks like random data
                            # Also check it's near a valid pointer
                            if off >= 8:
                                prev_qw = struct.unpack('<Q', data[off-8:off])[0]
                                next_qw = struct.unpack('<Q', data[off+64:off+72])[0] if off+72 <= len(data) else 0
                                # A key often sits between heap metadata (pointers)
                                if (0x100000 <= prev_qw < 0x7fffffffffff or
                                    0x100000 <= next_qw < 0x7fffffffffff):
                                    candidates.append((addr + off, chunk))
                    if len(candidates) > 20:
                        break
            addr += mbi.RegionSize if mbi.RegionSize > 0 else 0x10000
        except:
            addr += 0x10000

    print(f'  Scanned {region_count} heap regions')
    print(f'  Found {len(candidates)} key candidates')

    # Verify candidates: try to decrypt message_0.db page 1
    if candidates:
        from Crypto.Cipher import AES
        import hmac

        DB_PATH = 'D:/储存信息/xwechat_files/wxid_caccoealsdbj12_e8c8/db_storage/message/message_0.db'

        with open(DB_PATH, 'rb') as f:
            page1 = f.read(4096)

        for abs_addr, key_data in candidates[:10]:
            enc_key = key_data[:32]
            hmac_key = key_data[32:64]
            iv = hmac.new(hmac_key, struct.pack('>I', 1) + b'\x00' * 12, hashlib.sha1).digest()[:16]

            try:
                cipher = AES.new(enc_key, AES.MODE_CBC, iv=iv)
                dec = cipher.decrypt(page1)
                if dec[:16] == b'SQLite format 3\x00':
                    print(f'\n  ✅ KEY FOUND at 0x{abs_addr:x}!')
                    print(f'  Key hex: {key_data.hex()}')
                    print(f'  Enc key: {enc_key.hex()}')
                    print(f'  HMAC key: {hmac_key.hex()}')
                    # Save key
                    key_path = f'{OUTDIR}/sqlcipher_key.bin'
                    with open(key_path, 'wb') as f:
                        f.write(key_data)
                    print(f'  Saved to: {key_path}')
                    break
                elif any(32 <= b < 127 for b in dec[:32]):
                    pass  # partial match but not correct
            except: pass
        else:
            print('  No candidate verified correctly')

    if not candidates:
        print('  No high-entropy 64-byte blocks found')
