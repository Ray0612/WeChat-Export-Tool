"""
M91 — Debug breakpoint to capture sqlite3 handle (RCX)
"""
import ctypes, ctypes.wintypes, psutil, time, sys

k32 = ctypes.WinDLL('kernel32', use_last_error=True)
DWORD = ctypes.wintypes.DWORD
BYTE = ctypes.wintypes.BYTE
WORD = ctypes.wintypes.WORD

PROCESS_ALL_ACCESS = 0x1F0FFF
DBG_CONTINUE = 0x00010002
EXCEPTION_DEBUG_EVENT = 1
CREATE_PROCESS_DEBUG_EVENT = 3
EXIT_PROCESS_DEBUG_EVENT = 5
EXCEPTION_BREAKPOINT = 0x80000003
CONTEXT_FULL = 0x10007

class DEBUG_EVENT(ctypes.Structure):
    _fields_ = [
        ("dwDebugEventCode", DWORD),
        ("dwProcessId", DWORD),
        ("dwThreadId", DWORD),
        ("u", BYTE * 168),
    ]

class CONTEXT64(ctypes.Structure):
    _fields_ = [
        ("P1Home", ctypes.c_uint64), ("P2Home", ctypes.c_uint64),
        ("P3Home", ctypes.c_uint64), ("P4Home", ctypes.c_uint64),
        ("P5Home", ctypes.c_uint64), ("P6Home", ctypes.c_uint64),
        ("ContextFlags", DWORD), ("MxCsr", DWORD),
        ("SegCs", WORD), ("SegDs", WORD), ("SegEs", WORD),
        ("SegFs", WORD), ("SegGs", WORD), ("SegSs", WORD),
        ("EFlags", DWORD),
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

print("=" * 60)
print("M91 — Debug Breakpoint Capture")
print("=" * 60)

# Find WeChatAppEx
import pymem
pid = None
for proc in psutil.process_iter(['pid', 'name', 'exe']):
    name = proc.info['name'] or ''
    exe = proc.info.get('exe', '') or ''
    if 'wechatappex' in name.lower() and 'xwechat' in exe.lower():
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

if not pid:
    print("ERROR: WeChatAppEx not found")
    sys.exit(1)

func_addr = flue_base + 0x2a9c805
print(f"PID: {pid}")
print(f"flue: 0x{flue_base:x}")
print(f"breakpoint: 0x{func_addr:x}")

# Open process
hProc = k32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
if not hProc:
    print(f"OpenProcess failed: {ctypes.get_last_error()}")
    sys.exit(1)

# Read original byte
orig = ctypes.c_byte()
k32.ReadProcessMemory(hProc, func_addr, ctypes.byref(orig), 1, None)
print(f"orig byte: 0x{orig.value:02x}")

# Attach
print("Attaching...")
if not k32.DebugActiveProcess(pid):
    err = ctypes.get_last_error()
    print(f"DebugActiveProcess failed: {err}")
    k32.CloseHandle(hProc)
    if err == 5: print("ACCESS_DENIED - sandbox blocking debug")
    sys.exit(1)

print("Setting INT3...")
time.sleep(0.3)
int3 = ctypes.c_byte(0xCC)
k32.WriteProcessMemory(hProc, func_addr, ctypes.byref(int3), 1, None)

# Event loop
ev = DEBUG_EVENT()
bp_ready = False
found = False

while True:
    if not k32.WaitForDebugEvent(ctypes.byref(ev), 30000):
        print("Timeout")
        break

    code = ev.dwDebugEventCode

    if code == CREATE_PROCESS_DEBUG_EVENT:
        # First event - we can set breakpoint here
        k32.ContinueDebugEvent(ev.dwProcessId, ev.dwThreadId, DBG_CONTINUE)
        bp_ready = True
        print("Process created, ready for breakpoint.")
        print("Send a message in WeChat NOW to trigger sqlite3_key_v2...")
        continue

    elif code == EXCEPTION_DEBUG_EVENT:
        exc = ctypes.c_uint32.from_buffer(ev.u, 0).value

        if exc == EXCEPTION_BREAKPOINT and bp_ready:
            hThread = k32.OpenThread(0x0010, False, ev.dwThreadId)
            if hThread:
                ctx = CONTEXT64()
                ctx.ContextFlags = CONTEXT_FULL
                if k32.GetThreadContext(hThread, ctypes.byref(ctx)):
                    if ctx.Rip == func_addr + 1:
                        print(f"\n>>> BREAKPOINT HIT! <<<")
                        print(f"Thread: {ev.dwThreadId}")
                        print(f"RCX = 0x{ctx.Rcx:016x}  <<< sqlite3* HANDLE")
                        print(f"RDX = 0x{ctx.Rdx:016x}")
                        print(f"R8  = 0x{ctx.R8:016x}")
                        print(f"R9  = {ctx.R9}")
                        found = True

                        # Dump handle
                        buf = ctypes.create_string_buffer(256)
                        k32.ReadProcessMemory(hProc, ctx.Rcx, buf, 256, None)
                        print(f"\nHandle dump:")
                        for i in range(0, 256, 16):
                            h = ' '.join(f'{buf[j]:02x}' for j in range(i, min(i+16, 256)))
                            a = ''.join(chr(buf[j]) if 32 <= buf[j] < 127 else '.' for j in range(i, min(i+16, 256)))
                            print(f"  +{i:03x}: {h}  {a}")

                        k32.WriteProcessMemory(hProc, func_addr, ctypes.byref(orig), 1, None)
                        break
                k32.CloseHandle(hThread)

        k32.ContinueDebugEvent(ev.dwProcessId, ev.dwThreadId, DBG_CONTINUE)

    elif code == EXIT_PROCESS_DEBUG_EVENT:
        print("Process exited")
        break

    else:
        k32.ContinueDebugEvent(ev.dwProcessId, ev.dwThreadId, DBG_CONTINUE)

if not found:
    k32.WriteProcessMemory(hProc, func_addr, ctypes.byref(orig), 1, None)
    print("Breakpoint not hit")

k32.DebugActiveProcessStop(pid)
k32.CloseHandle(hProc)
print("\nDone")
