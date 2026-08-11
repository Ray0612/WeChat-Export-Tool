"""
M91 — Windows Debug API: 断点捕获 sqlite3 handle
"""
import ctypes, ctypes.wintypes, psutil, time, sys

kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
PROCESS_ALL_ACCESS = 0x1F0FFF
DBG_CONTINUE = 0x00010002
DBG_EXCEPTION_NOT_HANDLED = 0x80010001
EXCEPTION_DEBUG_EVENT = 1
CREATE_PROCESS_DEBUG_EVENT = 3
EXIT_PROCESS_DEBUG_EVENT = 5
EXCEPTION_BREAKPOINT = 0x80000003
CONTEXT_FULL = 0x10007

class DEBUG_EVENT(ctypes.Structure):
    _fields_ = [
        ("dwDebugEventCode", ctypes.wintypes.DWORD),
        ("dwProcessId", ctypes.wintypes.DWORD),
        ("dwThreadId", ctypes.wintypes.DWORD),
        ("u", ctypes.wintypes.BYTE * 168),
    ]

class CONTEXT(ctypes.Structure):
    _fields_ = [
        ("P1Home", ctypes.wintypes.DWORD64), ("P2Home", ctypes.wintypes.DWORD64),
        ("P3Home", ctypes.wintypes.DWORD64), ("P4Home", ctypes.wintypes.DWORD64),
        ("P5Home", ctypes.wintypes.DWORD64), ("P6Home", ctypes.wintypes.DWORD64),
        ("ContextFlags", ctypes.wintypes.DWORD), ("MxCsr", ctypes.wintypes.DWORD),
        ("SegCs", wintypes.WORD), ("SegDs", wintypes.WORD),
        ("SegEs", wintypes.WORD), ("SegFs", wintypes.WORD),
        ("SegGs", wintypes.WORD), ("SegSs", wintypes.WORD),
        ("EFlags", ctypes.wintypes.DWORD),
        ("Dr0", ctypes.wintypes.DWORD64), ("Dr1", ctypes.wintypes.DWORD64),
        ("Dr2", ctypes.wintypes.DWORD64), ("Dr3", ctypes.wintypes.DWORD64),
        ("Dr6", ctypes.wintypes.DWORD64), ("Dr7", ctypes.wintypes.DWORD64),
        ("Rax", ctypes.wintypes.DWORD64), ("Rcx", ctypes.wintypes.DWORD64),
        ("Rdx", ctypes.wintypes.DWORD64), ("Rbx", ctypes.wintypes.DWORD64),
        ("Rsp", ctypes.wintypes.DWORD64), ("Rbp", ctypes.wintypes.DWORD64),
        ("Rsi", ctypes.wintypes.DWORD64), ("Rdi", ctypes.wintypes.DWORD64),
        ("R8", ctypes.wintypes.DWORD64), ("R9", ctypes.wintypes.DWORD64),
        ("R10", ctypes.wintypes.DWORD64), ("R11", ctypes.wintypes.DWORD64),
        ("R12", ctypes.wintypes.DWORD64), ("R13", ctypes.wintypes.DWORD64),
        ("R14", ctypes.wintypes.DWORD64), ("R15", ctypes.wintypes.DWORD64),
        ("Rip", ctypes.wintypes.DWORD64),
    ]

print("=" * 60)
print("M91 — Debugger Breakpoint Handler")
print("=" * 60)

# Find WeChatAppEx
pid = None
for proc in psutil.process_iter(['pid', 'name', 'exe']):
    name = proc.info['name'] or ''
    exe = proc.info.get('exe', '') or ''
    if 'wechatappex' in name.lower() and 'xwechat' in exe.lower():
        import pymem
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
    print("ERROR: WeChatAppEx not found")
    sys.exit(1)

func_addr = flue_base + 0x2a9c805
print(f"PID: {pid}")
print(f"flue.dll: 0x{flue_base:x}")
print(f"sqlite3_key_v2: 0x{func_addr:x}")

# Open process
hProcess = kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
if not hProcess:
    err = ctypes.get_last_error()
    print(f"OpenProcess failed: error {err}")
    sys.exit(1)

# Save original byte
orig = ctypes.c_byte()
read = ctypes.c_size_t()
kernel32.ReadProcessMemory(hProcess, func_addr, ctypes.byref(orig), 1, ctypes.byref(read))
print(f"Original byte: 0x{orig.value:02x}")

# Attach debugger
print(f"\nAttaching debugger...")
if not kernel32.DebugActiveProcess(pid):
    err = ctypes.get_last_error()
    print(f"DebugActiveProcess failed: error {err}")
    kernel32.CloseHandle(hProcess)
    if err == 5:
        print("ACCESS_DENIED — Chromium sandbox blocking debug.")
        print("Try: run as Administrator, or disable sandbox.")
    sys.exit(1)

print("Attached! Setting breakpoint...")
time.sleep(0.5)

# Write INT3
int3 = ctypes.c_byte(0xCC)
written = ctypes.c_size_t()
kernel32.WriteProcessMemory(hProcess, func_addr, ctypes.byref(int3), 1, ctypes.byref(written))

# Debug event loop
event = DEBUG_EVENT()
bp_active = True
found = False

print("\nBreakpoint set. Now send a message in WeChat to trigger sqlite3_key_v2...")
print("Waiting for breakpoint...\n")

while bp_active:
    if not kernel32.WaitForDebugEvent(ctypes.byref(event), 30000):
        print("Timeout (30s). No breakpoint hit.")
        break

    if event.dwDebugEventCode == EXCEPTION_DEBUG_EVENT:
        exc_code = ctypes.c_uint32.from_buffer(event.u, 0).value

        if exc_code == EXCEPTION_BREAKPOINT:
            # Check if at our address by reading RIP
            hThread = kernel32.OpenThread(0x0010, False, event.dwThreadId)  # THREAD_GET_CONTEXT
            if hThread:
                ctx = CONTEXT()
                ctx.ContextFlags = CONTEXT_FULL
                if kernel32.GetThreadContext(hThread, ctypes.byref(ctx)):
                    # Check if RIP is at breakpoint (INT3 at func_addr, RIP points to func_addr+1)
                    if ctx.Rip == func_addr + 1:
                        print(f">>> BREAKPOINT HIT! <<<")
                        print(f"Thread: {event.dwThreadId}")
                        print(f"RIP:    0x{ctx.Rip:x}")
                        print(f"RCX:    0x{ctx.Rcx:x}  ← sqlite3* HANDLE")
                        print(f"RDX:    0x{ctx.Rdx:x}  ← db name (zDbName)")
                        print(f"R8:     0x{ctx.R8:x}   ← key bytes")
                        print(f"R9:     0x{ctx.R9:x}   ← key length")
                        print(f"\n*** sqlite3 HANDLE = 0x{ctx.Rcx:x} ***")
                        found = True

                        # Dump the handle structure
                        hd = ctypes.create_string_buffer(128)
                        kr = ctypes.c_size_t()
                        kernel32.ReadProcessMemory(hProcess, ctx.Rcx, hd, 128, ctypes.byref(kr))
                        print(f"\nHandle dump (first 128 bytes):")
                        for i in range(0, 128, 16):
                            hex_p = ' '.join(f'{hd[j]:02x}' for j in range(i, min(i+16, 128)))
                            asc = ''.join(chr(hd[j]) if 32 <= hd[j] < 127 else '.' for j in range(i, min(i+16, 128)))
                            print(f"  +{i:03x}: {hex_p}  {asc}")

                        # Restore original byte
                        kernel32.WriteProcessMemory(hProcess, func_addr, ctypes.byref(orig), 1, ctypes.byref(written))
                        print(f"\nBreakpoint removed. Detaching...")
                        bp_active = False
                        break
                    else:
                        print(f"  Breakpoint at 0x{ctx.Rip:x} (not our address), continuing...")
                kernel32.CloseHandle(hThread)

        elif exc_code == 0x80000003:
            # Could be another breakpoint
            pass

        kernel32.ContinueDebugEvent(event.dwProcessId, event.dwThreadId, DBG_CONTINUE)
        continue

    elif event.dwDebugEventCode == EXIT_PROCESS_DEBUG_EVENT:
        print("Process exited.")
        break

    elif event.dwDebugEventCode == CREATE_PROCESS_DEBUG_EVENT:
        # Initial process creation event
        kernel32.ContinueDebugEvent(event.dwProcessId, event.dwThreadId, DBG_CONTINUE)
        continue

    else:
        kernel32.ContinueDebugEvent(event.dwProcessId, event.dwThreadId, DBG_CONTINUE)

# Cleanup
if not found:
    # Restore original byte
    kernel32.WriteProcessMemory(hProcess, func_addr, ctypes.byref(orig), 1, ctypes.byref(written))
    print("Breakpoint not hit.")

kernel32.DebugActiveProcessStop(pid)
kernel32.CloseHandle(hProcess)
print("\nDone.")
