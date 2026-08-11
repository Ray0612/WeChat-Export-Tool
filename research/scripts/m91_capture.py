"""
M91 — Capture sqlite3 handle via debug breakpoint
"""
import ctypes, ctypes.wintypes, psutil, time, sys
import pymem

k32 = ctypes.WinDLL('kernel32', use_last_error=True)

# Set argtypes for 64-bit compat
k32.ReadProcessMemory.argtypes = [ctypes.wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
k32.ReadProcessMemory.restype = ctypes.wintypes.BOOL
k32.WriteProcessMemory.argtypes = [ctypes.wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
k32.WriteProcessMemory.restype = ctypes.wintypes.BOOL
k32.GetThreadContext.argtypes = [ctypes.wintypes.HANDLE, ctypes.c_void_p]
k32.GetThreadContext.restype = ctypes.wintypes.BOOL
k32.OpenThread.argtypes = [ctypes.wintypes.DWORD, ctypes.wintypes.BOOL, ctypes.wintypes.DWORD]
k32.OpenThread.restype = ctypes.wintypes.HANDLE
k32.WaitForDebugEvent.argtypes = [ctypes.c_void_p, ctypes.wintypes.DWORD]
k32.WaitForDebugEvent.restype = ctypes.wintypes.BOOL
k32.ContinueDebugEvent.argtypes = [ctypes.wintypes.DWORD, ctypes.wintypes.DWORD, ctypes.wintypes.DWORD]
k32.ContinueDebugEvent.restype = ctypes.wintypes.BOOL

DBG_CONTINUE = 0x00010002
EXCEPTION_DEBUG_EVENT = 1
CREATE_PROCESS_DEBUG_EVENT = 3
EXIT_PROCESS_DEBUG_EVENT = 5
EXCEPTION_BREAKPOINT = 0x80000003
CONTEXT_FULL = 0x10007

class CONTEXT64(ctypes.Structure):
    _fields_ = [
        ("P1Home", ctypes.c_uint64), ("P2Home", ctypes.c_uint64),
        ("P3Home", ctypes.c_uint64), ("P4Home", ctypes.c_uint64),
        ("P5Home", ctypes.c_uint64), ("P6Home", ctypes.c_uint64),
        ("ContextFlags", ctypes.c_uint32), ("MxCsr", ctypes.c_uint32),
        ("SegCs", ctypes.c_uint16), ("SegDs", ctypes.c_uint16),
        ("SegEs", ctypes.c_uint16), ("SegFs", ctypes.c_uint16),
        ("SegGs", ctypes.c_uint16), ("SegSs", ctypes.c_uint16),
        ("EFlags", ctypes.c_uint32),
        ("Dr0", ctypes.c_uint64), ("Dr1", ctypes.c_uint64),
        ("Dr2", ctypes.c_uint64), ("Dr3", ctypes.c_uint64),
        ("Dr6", ctypes.c_uint64), ("Dr7", ctypes.c_uint64),
        ("Rax", ctypes.c_uint64), ("Rcx", ctypes.c_uint64),
        ("Rdx", ctypes.c_uint64), ("Rbx", ctypes.c_uint64),
        ("Rsp", ctypes.c_uint64), ("Rbp", ctypes.c_uint64),
        ("Rsi", ctypes.c_uint64), ("Rdi", ctypes.c_uint64),
        ("R8", ctypes.c_uint64), ("R9", ctypes.c_uint64),
        ("R10", ctypes.c_uint64), ("R11", ctypes.c_uint64),
        ("R12", ctypes.c_uint64), ("R13", ctypes.c_uint64),
        ("R14", ctypes.c_uint64), ("R15", ctypes.c_uint64),
        ("Rip", ctypes.c_uint64),
    ]

# Find WeChatAppEx
pid = None
for proc in psutil.process_iter(['pid', 'name', 'exe']):
    if 'wechatappex' in proc.info['name'].lower() and 'xwechat' in proc.info.get('exe','').lower():
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
        if pid: break

func_addr = flue_base + 0x2a9c805
print(f"PID: {pid} | flue: 0x{flue_base:x} | bp: 0x{func_addr:x}")

hProc = k32.OpenProcess(0x1F0FFF, False, pid)
orig = ctypes.c_byte()
k32.ReadProcessMemory(hProc, func_addr, ctypes.byref(orig), 1, None)
print(f"Orig byte: 0x{orig.value:02x}")

# Attach
if not k32.DebugActiveProcess(pid):
    err = ctypes.get_last_error()
    print(f"DebugActiveProcess failed: {err}")
    k32.WriteProcessMemory(hProc, func_addr, ctypes.byref(ctypes.c_byte(orig.value)), 1, None)
    k32.CloseHandle(hProc)
    exit()

print("Attached. Waiting for CREATE_PROCESS event...")

# Event loop
bp_set = False
got_bp = False
rct = 0

while not got_bp:
    ev_buf = ctypes.create_string_buffer(176)  # sizeof DEBUG_EVENT
    if not k32.WaitForDebugEvent(ev_buf, 30000):
        print("Timeout")
        break

    # Check event code
    code = ctypes.c_uint32.from_buffer(ev_buf, 0).value
    pid_ev = ctypes.c_uint32.from_buffer(ev_buf, 4).value
    tid_ev = ctypes.c_uint32.from_buffer(ev_buf, 8).value

    if code == CREATE_PROCESS_DEBUG_EVENT:
        # Now set the breakpoint
        int3 = ctypes.c_byte(0xCC)
        k32.WriteProcessMemory(hProc, func_addr, ctypes.byref(int3), 1, None)
        bp_set = True
        print(f"INT3 set at 0x{func_addr:x}")
        print("Send a message in WeChat NOW...")
        k32.ContinueDebugEvent(pid_ev, tid_ev, DBG_CONTINUE)
        continue

    elif code == EXCEPTION_DEBUG_EVENT:
        exc = ctypes.c_uint32.from_buffer(ev_buf, 12).value  # ExceptionCode at offset 12 in UNION

        if exc == EXCEPTION_BREAKPOINT and bp_set:
            hThread = k32.OpenThread(0x0010, False, tid_ev)
            if hThread:
                ctx = CONTEXT64()
                ctx.ContextFlags = CONTEXT_FULL
                if k32.GetThreadContext(hThread, ctypes.byref(ctx)):
                    if ctx.Rip == func_addr + 1:
                        print(f"\n>>> BREAKPOINT HIT! <<<")
                        print(f"RCX (handle) = 0x{ctx.Rcx:016x}")
                        print(f"RDX (dbname) = 0x{ctx.Rdx:016x}")
                        print(f"R8  (key)    = 0x{ctx.R8:016x}")
                        print(f"R9  (keylen) = {ctx.R9}")
                        got_bp = True

                        # Dump handle
                        buf = ctypes.create_string_buffer(256)
                        k32.ReadProcessMemory(hProc, ctx.Rcx, buf, 256, None)
                        print(f"\nHandle first 256 bytes:")
                        for i in range(0, 256, 16):
                            h = ' '.join(f'{buf[j]:02x}' for j in range(i, min(i+16, 256)))
                            a = ''.join(chr(buf[j]) if 32 <= buf[j] < 127 else '.' for j in range(i, min(i+16, 256)))
                            print(f"  +{i:03x}: {h}  {a}")

                k32.CloseHandle(hThread)

        k32.ContinueDebugEvent(pid_ev, tid_ev, DBG_CONTINUE)

    elif code == EXIT_PROCESS_DEBUG_EVENT:
        print("Process exited")
        break

    else:
        k32.ContinueDebugEvent(pid_ev, tid_ev, DBG_CONTINUE)

# Restore original
k32.WriteProcessMemory(hProc, func_addr, ctypes.byref(orig), 1, None)

# Detach
k32.DebugActiveProcessStop(pid)
k32.CloseHandle(hProc)
print(f"\n{'CAPTURED!' if got_bp else 'Not captured'}")
