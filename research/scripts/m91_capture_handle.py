"""
M91 — 用 Windows Debug API 附到 WeChatAppEx
在 sqlite3_key_v2 函数处设断点，读取 RCX（handle）
"""
import pymem, psutil, struct, time

# Find WeChatAppEx with flue.dll
pid = None
for proc in psutil.process_iter(['pid', 'name', 'exe']):
    name = proc.info['name'] or ''
    exe = proc.info.get('exe', '') or ''
    if 'wechatappex' in name.lower() and 'xwechat' in exe.lower():
        # Check if it has flue.dll loaded
        try:
            pm = pymem.Pymem(proc.info['pid'])
            for mod in pm.list_modules():
                if 'flue.dll' in mod.name.lower():
                    pid = proc.info['pid']
                    flue_base = mod.lpBaseOfDll
                    break
            pm.close_process()
        except:
            pass
        if pid:
            break

if not pid:
    print("No WeChatAppEx with flue.dll found")
    exit()

# sqlite3_key_v2 function in flue.dll at RVA 0x2a9c805
func_rva = 0x2a9c805
func_addr = flue_base + func_rva

print(f"WeChatAppEx PID: {pid}")
print(f"flue.dll base: 0x{flue_base:x}")
print(f"sqlite3_key_v2: 0x{func_addr:x}")

# Use CreateRemoteThread to inject code that reads RCX
# But this requires shellcode... let me try a simpler approach

# Instead: use pymem to write a breakpoint (INT3 = 0xCC) at the function
# and intercept it

# But wait, we can't intercept with pymem alone. We need Frida or a debugger.
# Let me try reading the function's return value pattern instead.

# At the function exit point (line 419 in Ghidra), RAX should have the result
# But we want RCX (input handle), not RAX (output)

# Actually, let me just try writing and reading a specific memory address
# The 0x2f8 wrapper object is allocated and returned through FUN_1816c9080
# In WeChatAppEx's .data section, search for a pattern

# Let me read the .data section and look for the initialized wrapper
data_va = flue_base + 0xc2b7000
data_size = 0x491df0

print(f"\nReading .data section (0x{data_va:x}, {data_size} bytes)...")
try:
    data = pm.read_bytes(data_va, data_size)
except:
    print("Cannot read .data section")

# Instead, let me try to read the function's own code to find where it
# stores key data between calls

# The function at 0x2a9c805 stores the codec at lVar3+0x130 (line 329)
# and the key at puVar6+6 (line 248-251)
# These are offsets within the pPager structure

# To find the handle, I can look for the codec object in the .data section
# by searching for a reference to the sqlite3_key_v2 function

# Actually, let me just use a simpler heuristic:
# In X64 Windows, every thread has a TEB. sqlite3 uses TLS for thread-specific data.
# The handle might be in a class member offset.

# The SIMPLEST thing: search for the string address of "main" as a QWORD
# anywhere in the process, then verify the structure
main_str_in_flue = flue_base + 0xa8f38a2
lo32 = main_str_in_flue & 0xFFFFFFFF

print(f"\nSearching for 'main' pointer in all writable memory...")
import pymem.memory

base = 0x100000
found = 0
while base < 0x7fffffffffff:
    try:
        mbi = pymem.memory.virtual_query(pm.process_handle, base)
        if mbi.State == 0x1000 and mbi.RegionSize <= 65536:
            try:
                data = pm.read_bytes(base, min(mbi.RegionSize, 65536))
                for off in range(0, len(data)-8, 8):
                    if data[off] == (lo32 & 0xFF) and data[off+1] == ((lo32 >> 8) & 0xFF):
                        full = struct.unpack('<Q', data[off:off+8])[0]
                        if full == main_str_in_flue:
                            abs_addr = base + off
                            # Check if this looks like aDb[0].zDbName
                            # The struct aDb[0] has: zDbName(8), pBt(8)
                            # and the handle should be before it
                            # Look backward for a valid handle start
                            for back in range(32, 256, 8):
                                try:
                                    h_start = abs_addr - back
                                    # Check if h_start looks like a handle
                                    # handle has: nDb, init, openFlags, errCode, etc.
                                    # Just check if it has a vtable at +0
                                    pass
                                except:
                                    pass
                            print(f"  'main' ptr at 0x{abs_addr:x}")
                            # Check what's before this
                            ctx = pm.read_bytes(abs_addr-32, 48)
                            asc = ''.join(chr(b) if 32 <= b < 127 else '.' for b in ctx)

                            # For each potential handle (every 8 bytes, up to 256 back)
                            for back_off in range(0, 256, 8):
                                h_candidate = abs_addr - back_off
                                # Check if this contains a pointer to aDb
                                # handle + 0x20 = aDb pointer
                                try:
                                    aDb_ref = struct.unpack('<Q', pm.read_bytes(h_candidate + 0x20, 8))[0]
                                    if aDb_ref == abs_addr - 0:  # This is where aDb starts
                                        print(f"    *** HANDLE at 0x{h_candidate:x}! aDb at +0x20 ***")
                                        found += 1
                                except:
                                    pass
            except:
                pass
        base += mbi.RegionSize if mbi.RegionSize > 0 else 0x10000
    except:
        base += 0x10000

print(f"\nDone. Handles found: {found}")
