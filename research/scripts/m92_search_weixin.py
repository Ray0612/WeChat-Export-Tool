"""
M92 — 在 Weixin.exe 中找 sqlite3 handle
Weixin.exe 静态链接 SQLite，handle 应该在里面
"""
import pymem, psutil, struct, time
import pymem.memory

# Find Weixin.exe
pid = None
for proc in psutil.process_iter(['pid', 'name']):
    if proc.info['name'] == 'Weixin.exe':
        pid = proc.info['pid']
        break

print(f"Weixin.exe PID: {pid}")

pm = pymem.Pymem(pid)

# Find the main module (weixin.dll / Weixin.exe)
main_mod = None
for mod in pm.list_modules():
    name = mod.name.lower()
    if 'weixin' in name and ('.dll' in name or '.exe' in name):
        if main_mod is None or mod.SizeOfImage > main_mod.SizeOfImage:
            main_mod = mod

print(f"Main module: {main_mod.name} at 0x{main_mod.lpBaseOfDll:x}, size 0x{main_mod.SizeOfImage:x}")

# The "SQLite format 3" string is in this module's code section
# Search for "main" string within this module
base = main_mod.lpBaseOfDll
size = main_mod.SizeOfImage

print("Searching for 'main' string in main module...")
main_addrs = []

# Search in chunks (skip first 0x1000 which is PE header)
for off in range(0x1000, size, 4096):
    try:
        chunk = pm.read_bytes(base + off, min(4096, size - off))
        pos = chunk.find(b'main\x00')
        while pos >= 0:
            main_addrs.append(base + off + pos)
            pos = chunk.find(b'main\x00', pos + 1)
    except:
        pass

print(f"'main' strings in main module: {len(main_addrs)}")

# Filter: "main" should be near "SELECT" or "PRAGMA" or SQL code
# to be the database name used by SQLite
interesting_mains = []
for a in main_addrs:
    try:
        ctx = pm.read_bytes(a - 64, 128)
        nearby = ''.join(chr(b) if 32 <= b < 127 else '.' for b in ctx)
        if any(k in nearby for k in ['sqlite3_', 'SELECT', 'PRAGMA', 'format']):
            interesting_mains.append(a)
            print(f"  SQL-related 'main' at 0x{a:x}")
    except:
        pass

# For each SQL-related "main", search for pointers to it
print(f"\nSearching for handle pointers...")
for main_addr in interesting_mains:
    # Search .data and heaps for the pointer
    for scan_base in [base, 0x15b000000000]:
        end = scan_base + size if scan_base == base else 0x15b200000000
        scan_addr = scan_base

        while scan_addr < end:
            try:
                mbi = pymem.memory.virtual_query(pm.process_handle, scan_addr)
                if mbi.State == 0x1000 and mbi.RegionSize <= 65536:
                    try:
                        chunk = pm.read_bytes(scan_addr, min(mbi.RegionSize, 65536))
                        main_packed = struct.pack('<Q', main_addr)
                        for off in range(0, len(chunk) - 8, 8):
                            if chunk[off:off+8] == main_packed:
                                abs_addr = scan_addr + off
                                # Try as aDb[0].zDbName
                                for delta in [0x20, 0x28, 0x18, 0x30, 0x10]:
                                    h_cand = abs_addr - delta
                                    try:
                                        aDb_test = struct.unpack('<Q', pm.read_bytes(h_cand + delta, 8))[0]
                                        if aDb_test == abs_addr:
                                            # Also check aDb[0] for pBt
                                            pBt = struct.unpack('<Q', pm.read_bytes(abs_addr + 8, 8))[0]
                                            if pBt > 0x100000:
                                                print(f"\n>>> HANDLE FOUND at 0x{h_cand:x}")
                                                print(f"    aDb at 0x{abs_addr:x} (aDb at +0x{delta:x})")
                                                print(f"    zDbName='main', pBt=0x{pBt:x}")

                                                # Dump handle
                                                hd = pm.read_bytes(h_cand, 128)
                                                for i in range(0, 128, 16):
                                                    hex_p = ' '.join(f'{b:02x}' for b in hd[i:i+16])
                                                    asc = ''.join(chr(b) if 32 <= b < 127 else '.' for b in hd[i:i+16])
                                                    print(f"    +{i:03x}: {hex_p}  {asc}")
                                                exit()
                                    except:
                                        pass
                    except:
                        pass
                scan_addr += mbi.RegionSize if mbi.RegionSize > 0 else 0x10000
            except:
                scan_addr += 0x10000

print("No handle found in Weixin.exe either")
