# -*- coding: utf-8 -*-
"""
综合 key 搜索 v2 — 使用多种方法找 key
"""
import pymem, psutil, re, hashlib, hmac, struct, sys
from Crypto.Cipher import AES
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

pid = None
for proc in psutil.process_iter(['pid', 'name']):
    if proc.info['name'] and proc.info['name'].lower() == 'weixin.exe':
        try:
            for f in proc.open_files():
                if 'message_0.db' in f.path and 'biz' not in f.path:
                    pid = proc.info['pid']
                    break
        except: pass
        if pid: break

print(f'PID: {pid}')
pm = pymem.Pymem(pid)

db_path = 'D:/储存信息/xwechat_files/wxid_caccoealsdbj12_e8c8/db_storage/message/message_0.db'
with open(db_path, 'rb') as f:
    page1 = f.read(4096)

def verify_key(hex_key):
    """Try to verify a 64-char hex key against message_0.db"""
    if len(hex_key) != 64:
        return False
    try:
        raw = bytes.fromhex(hex_key)
    except:
        return False
    if len(raw) != 32:
        return False

    salt = page1[:16]
    mac_salt = bytes(x ^ 0x3a for x in salt)
    mac_key = hashlib.pbkdf2_hmac('sha512', raw, mac_salt, 2, dklen=32)
    iv = page1[-80:-64]

    cipher = AES.new(raw, AES.MODE_CBC, iv=iv)
    dec = cipher.decrypt(page1[16:-80])
    return dec[:16] == b'SQLite format 3\x00'

# Method 1: Pattern scan x'<64hex>'
print('\n=== Method 1: x\'<64hex>\' pattern ===')
addrs = pm.pattern_scan_all(b"x'", return_multiple=True)
print(f'  Pattern hits: {len(addrs)}')
for a in addrs[:5000]:
    try:
        b = pm.read_bytes(a, 3 + 64 + 1)
    except: continue
    if len(b) < 67: continue
    if b[66] != ord("'"): continue
    hex_part = b[2:66]
    try:
        hs = hex_part.decode('ascii')
    except: continue
    if re.match(r'^[0-9a-fA-F]{64}$', hs):
        if verify_key(hs):
            print(f'  ✅ KEY FOUND: {hs}')
            with open('C:/Users/OK/Desktop/wx_export/sqlcipher_key_found.txt', 'w') as f:
                f.write(hs)
            sys.exit(0)

# Method 2: Plain 64-char hex strings (without x' prefix)
print('\n=== Method 2: Plain 64-char hex strings ===')
hex_pat = re.compile(b'[0-9a-fA-F]{64}')
found = set()
addr = 0
count = 0
while addr < 0x7fffffffffff and count < 1000:
    try:
        mbi = pymem.memory.virtual_query(pm.process_handle, addr)
        if mbi.State == 0x1000:
            try:
                data = pm.read_bytes(addr, min(mbi.RegionSize, 0x10000))
            except:
                addr += max(mbi.RegionSize, 0x1000)
                continue
            for m in hex_pat.finditer(data):
                hs = data[m.start():m.start()+64].decode('ascii')
                if hs not in found:
                    found.add(hs)
                    count += 1
                    if verify_key(hs):
                        print(f'  ✅ KEY FOUND: {hs}')
                        with open('C:/Users/OK/Desktop/wx_export/sqlcipher_key_found.txt', 'w') as f:
                            f.write(hs)
                        sys.exit(0)
        addr += mbi.RegionSize if mbi.RegionSize > 0 else 0x10000
    except:
        addr += 0x10000
print(f'  Scanned {count} hex strings, no valid key')

# Method 3: x'<64hex><32hex>' (key+salt)
print('\n=== Method 3: x\'<96hex>\' pattern ===')
for a in addrs[:5000]:
    try:
        b = pm.read_bytes(a, 3 + 96 + 1)
    except: continue
    if len(b) < 99: continue
    if b[98] != ord("'"): continue
    hex_part = b[2:98]
    try:
        hs = hex_part.decode('ascii')
    except: continue
    if re.match(r'^[0-9a-fA-F]{96}$', hs):
        key_part = hs[:64]
        if verify_key(key_part):
            print(f'  ✅ KEY FOUND: {key_part}')
            with open('C:/Users/OK/Desktop/wx_export/sqlcipher_key_found.txt', 'w') as f:
                f.write(key_part)
            sys.exit(0)

print('\nAll methods exhausted. Key not found.')
