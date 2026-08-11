# -*- coding: utf-8 -*-
"""
使用 pywxdump 的方法直接搜索 key
参考: pywxdump 的 get_key_by_mem_search 方法
"""
import ctypes, ctypes.wintypes, struct, os, sys, psutil
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010

kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
OpenProcess = kernel32.OpenProcess
OpenProcess.restype = ctypes.wintypes.HANDLE
OpenProcess.argtypes = [ctypes.wintypes.DWORD, ctypes.wintypes.BOOL, ctypes.wintypes.DWORD]
CloseHandle = kernel32.CloseHandle
ReadProcessMemory = kernel32.ReadProcessMemory

# Find Weixin PID with DB handle
pid = None
for proc in psutil.process_iter(['pid', 'name']):
    if proc.info['name'].lower() == 'weixin.exe':
        try:
            for f in proc.open_files():
                if 'message_0.db' in f.path and 'biz' not in f.path:
                    pid = proc.info['pid']
                    break
        except: pass
        if pid: break

print('PID:', pid)

hProcess = OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)

# Get Weixin.dll memory range
import pymem
pm = pymem.Pymem(pid)
weixin_dll_base = 0
weixin_dll_size = 0
for mod in pm.list_modules():
    if 'weixin.dll' in mod.name.lower():
        weixin_dll_base = mod.lpBaseOfDll
        weixin_dll_size = mod.SizeOfImage
        break

print('Weixin.dll: 0x%x (size: 0x%x)' % (weixin_dll_base, weixin_dll_size))

# Search for phone type strings in Weixin.dll range
phone_types = [b'iphone\x00', b'android\x00', b'ipad\x00']

def search_memory(h, pattern, start, end, max_num=10):
    """Search for pattern in memory range"""
    results = []
    addr = start
    chunk_size = 0x10000
    pattern_len = len(pattern)
    while addr < end and len(results) < max_num:
        try:
            array = ctypes.create_string_buffer(chunk_size)
            ret = ReadProcessMemory(h, ctypes.c_void_p(addr), array, chunk_size, 0)
            if ret:
                data = bytes(array)
                pos = 0
                while True:
                    pos = data.find(pattern, pos)
                    if pos < 0: break
                    results.append(addr + pos)
                    pos += 1
            addr += chunk_size
        except:
            addr += chunk_size
    return results

print('Searching for phone type strings...')
type_addrs = []
for pt in phone_types:
    addrs = search_memory(hProcess, pt, weixin_dll_base, weixin_dll_base + weixin_dll_size, 3)
    print(f'  {pt.decode():10s}: {len(addrs)} found')
    type_addrs.extend(addrs)

type_addrs.sort()
if not type_addrs:
    print('No phone type strings found in Weixin.dll!')
    print('Trying full process memory search...')
    # Search entire process for these strings
    for pt in phone_types:
        addrs = search_memory(hProcess, pt, 0x100000, 0x7fffffffffff, 3)
        print(f'  {pt.decode():10s}: {len(addrs)} found')
        type_addrs.extend(addrs)
    type_addrs.sort()

print('Total type addresses found:', len(type_addrs))
for a in type_addrs[:10]:
    print(f'  0x{a:x}')

# Now scan backward from each type address to find the key
def read_key_at(h, address):
    """Try to read a key at the given address"""
    # Read 8 bytes as pointer
    ptr_bytes = ctypes.create_string_buffer(8)
    if ReadProcessMemory(h, ctypes.c_void_p(address), ptr_bytes, 8, 0) == 0:
        return None
    key_addr = int.from_bytes(bytes(ptr_bytes), 'little')
    if key_addr < 0x100000 or key_addr > 0x7fffffffffff:
        return None
    # Read 32 bytes from that pointer
    key_bytes = ctypes.create_string_buffer(32)
    if ReadProcessMemory(h, ctypes.c_void_p(key_addr), key_bytes, 32, 0) == 0:
        return None
    return bytes(key_bytes)

print('\nScanning backward for key...')
keys_found = []
for i, addr in enumerate(type_addrs):
    for offset in range(0, 2000, 8):
        test_addr = addr - offset
        key = read_key_at(hProcess, test_addr)
        if key and len(key) == 32:
            # Check if it looks like a valid key (high entropy)
            distinct = len(set(key))
            if distinct >= 20:  # Should have decent entropy
                keys_found.append((addr - offset, key.hex(), distinct))
                if len(keys_found) >= 20:
                    break
    if len(keys_found) >= 20:
        break

print(f'Found {len(keys_found)} candidate keys')

# Verify each key against message_0.db
if keys_found:
    from Crypto.Cipher import AES
    import hashlib, hmac

    db_path = 'D:/储存信息/xwechat_files/wxid_caccoealsdbj12_e8c8/db_storage/message/message_0.db'
    with open(db_path, 'rb') as f:
        page1 = f.read(4096)

    for addr, key_hex, ent in keys_found[:10]:
        key_bytes = bytes.fromhex(key_hex)
        # Try as 64-byte? Actually pywxdump returns 32-byte key
        # Use as raw key for PBKDF2
        for salt in [b'', b'salt', b'wxid_caccoealsdbj12']:
            derived = hashlib.pbkdf2_hmac('sha1', key_bytes, salt, 64000, dkLen=64)
            enc = derived[:32]
            hmac_key = derived[32:64]
            iv = hmac.new(hmac_key, struct.pack('>I', 1) + b'\x00' * 12, hashlib.sha1).digest()[:16]
            try:
                cipher = AES.new(enc, AES.MODE_CBC, iv=iv)
                dec = cipher.decrypt(page1)
                if dec[:16] == b'SQLite format 3\x00':
                    print(f'\n✅ KEY FOUND at 0x{addr:x}!')
                    print(f'   32-byte key: {key_hex}')
                    print(f'   Salt: {salt}')
                    print(f'   Full 64-byte derived: {derived.hex()}')
                    with open('C:/Users/OK/Desktop/wx_export/sqlcipher_key_found.txt', 'w') as f:
                        f.write(f'key={key_hex}\nderived_64={derived.hex()}\nsalt={salt.decode()}\n')
                    break
            except: pass
    else:
        print('No key verified correctly with database')

CloseHandle(hProcess)
