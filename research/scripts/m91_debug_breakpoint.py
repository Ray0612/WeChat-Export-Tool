"""
M91 — Windows Debug API 断点
附到 WeChatAppEx → 在 sqlite3_key_v2 设断点 → 读 RCX (handle)
"""
import ctypes
from ctypes import wintypes
import psutil, time, struct, sys

# Windows API constants
DEBUG_PROCESS = 0x00000001
DEBUG_ONLY_THIS_PROCESS = 0x00000002
DBG_CONTINUE = 0x00010002
DBG_EXCEPTION_NOT_HANDLED = 0x80010001
EXCEPTION_DEBUG_EVENT = 1
CREATE_PROCESS_DEBUG_EVENT = 3
EXIT_PROCESS_DEBUG_EVENT = 5
EXCEPTION_BREAKPOINT = 0x80000003
EXCEPTION_SINGLE_STEP = 0x80000004
CONTEXT_FULL = 0x10007

# Load kernel32
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

class DEBUG_EVENT(ctypes.Structure):
    _fields_ = [
        ("dwDebugEventCode", wintypes.DWORD),
        ("dwProcessId", wintypes.DWORD),
        ("dwThreadId", wintypes.DWORD),
        ("u", wintypes.BYTE * 164),  # Union placeholder
    ]

class CONTEXT(ctypes.Structure):
    _fields_ = [
        ("P1Home", wintypes.DWORD64),
        ("P2Home", wintypes.DWORD64),
        ("P3Home", wintypes.DWORD64),
        ("P4Home", wintypes.DWORD64),
        ("P5Home", wintypes.DWORD64),
        ("P6Home", wintypes.DWORD64),
        ("ContextFlags", wintypes.DWORD),
        ("MxCsr", wintypes.DWORD),
        ("SegCs", wintypes.WORD),
        ("SegDs", wintypes.WORD),
        ("SegEs", wintypes.WORD),
        ("SegFs", wintypes.WORD),
        ("SegGs", wintypes.WORD),
        ("SegSs", wintypes.WORD),
        ("EFlags", wintypes.DWORD),
        ("Dr0", wintypes.DWORD64),
        ("Dr1", wintypes.DWORD64),
        ("Dr2", wintypes.DWORD64),
        ("Dr3", wintypes.DWORD64),
        ("Dr6", wintypes.DWORD64),
        ("Dr7", wintypes.DWORD64),
        ("Rax", wintypes.DWORD64),
        ("Rcx", wintypes.DWORD64),
        ("Rdx", wintypes.DWORD64),
        ("Rbx", wintypes.DWORD64),
        ("Rsp", wintypes.DWORD64),
        ("Rbp", wintypes.DWORD64),
        ("Rsi", wintypes.DWORD64),
        ("Rdi", wintypes.DWORD64),
        ("R8", wintypes.DWORD64),
        ("R9", wintypes.DWORD64),
        ("R10", wintypes.DWORD64),
        ("R11", wintypes.DWORD64),
        ("R12", wintypes.DWORD64),
        ("R13", wintypes.DWORD64),
        ("R14", wintypes.DWORD64),
        ("R15", wintypes.DWORD64),
        ("Rip", wintypes.DWORD64),
    ]

# Set up function signatures
kernel32.DebugActiveProcess.argtypes = [wintypes.DWORD]
kernel32.DebugActiveProcess.restype = wintypes.BOOL

kernel32.WaitForDebugEvent.argtypes = [ctypes.POINTER(DEBUG_EVENT), wintypes.DWORD]
kernel32.WaitForDebugEvent.restype = wintypes.BOOL

kernel32.ContinueDebugEvent.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.DWORD]
kernel32.ContinueDebugEvent.restype = wintypes.BOOL

kernel32.ReadProcessMemory.argtypes = [wintypes.HANDLE, wintypes.LPCVOID, wintypes.LPVOID, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
kernel32.ReadProcessMemory.restype = wintypes.BOOL

kernel32.WriteProcessMemory.argtypes = [wintypes.HANDLE, wintypes.LPCVOID, wintypes.LPVOID, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
kernel32.WriteProcessMemory.restype = wintypes.BOOL

kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE

kernel32.GetThreadContext.argtypes = [wintypes.HANDLE, ctypes.POINTER(CONTEXT)]
kernel32.GetThreadContext.restype = wintypes.BOOL

kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL

kernel32.DebugActiveProcessStop.argtypes = [wintypes.DWORD]
kernel32.DebugActiveProcessStop.restype = wintypes.BOOL

kernel32.OpenThread.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenThread.restype = wintypes.HANDLE

THREAD_GET_CONTEXT = 0x0002
THREAD_SUSPEND_RESUME = 0x0002
PROCESS_VM_READ = 0x0010
PROCESS_VM_WRITE = 0x0020
PROCESS_VM_OPERATION = 0x0008

# Step 1: Find WeChatAppEx with flue.dll
print("Step 1: Finding WeChatAppEx process...")
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
                    # Get handle to this process for reading/writing
                    hProcess = kernel32.OpenProcess(
                        PROCESS_VM_READ | PROCESS_VM_WRITE | PROCESS_VM_OPERATION,
                        False, pid)
                    if not hProcess:
                        pm.close_process()
                        continue
                    print(f"  PID: {pid}, flue: 0x{flue_base:x}")
                    break
            pm.close_process()
        except Exception as e:
            pass
        if pid:
            break

if not pid or not hProcess:
    print("ERROR: Cannot find WeChatAppEx")
    sys.exit(1)

# Step 2: Set breakpoint address
func_rva = 0x2a9c805
func_addr = flue_base + func_rva
print(f"\nStep 2: sqlite3_key_v2 at 0x{func_addr:x}")

# Read original byte at function entry
orig_byte = ctypes.c_byte()
read = ctypes.c_size_t()
kernel32.ReadProcessMemory(hProcess, func_addr, ctypes.byref(orig_byte), 1, ctypes.byref(read))
original_code = orig_byte.value
print(f"  Original first byte: 0x{original_code:02x}")

# Step 3: Attach debugger
print(f"\nStep 3: Attaching to PID {pid}...")
if not kernel32.DebugActiveProcess(pid):
    err = ctypes.get_last_error()
    print(f"  DebugActiveProcess failed: error {err} (ACCESS_DENIED={5})")
    kernel32.CloseHandle(hProcess)
    sys.exit(1)

print("  Attached! Handling initial events...")

# Step 4: Handle debug events
# First, handle the CREATE_PROCESS_DEBUG_EVENT
event = DEBUG_EVENT()
breakpoint_set = False
bp_hit = False
handle_value = 0
timeout = 5000  # 5 second timeout for events

while not (bp_hit or not breakpoint_set):
    if not kernel32.WaitForDebugEvent(ctypes.byref(event), timeout):
        print("  Timeout waiting for debug event")
        break

    if event.dwDebugEventCode == EXCEPTION_DEBUG_EVENT:
        # Get exception info from the union
        # The exception record is at offset 0 in the union
        # ExceptionCode is at offset 0
        exc_code = ctypes.c_uint32.from_buffer(event.u, 0).value

        if exc_code == EXCEPTION_BREAKPOINT:
            if not breakpoint_set:
                # This is the initial breakpoint from DebugActiveProcess
                print("  Initial breakpoint hit (debugger attach)")

                # Now set our breakpoint: write 0xCC at function entry
                int3 = ctypes.c_byte(0xCC)
                written = ctypes.c_size_t()
                if kernel32.WriteProcessMemory(hProcess, func_addr, ctypes.byref(int3), 1, ctypes.byref(written)):
                    print(f"  INT3 breakpoint set at 0x{func_addr:x}")
                    breakpoint_set = True
                else:
                    print(f"  Failed to write breakpoint")
                    break
            else:
                # Check if it's OUR breakpoint
                context = CONTEXT()
                context.ContextFlags = CONTEXT_FULL

                # Get thread handle to read context
                hThread = kernel32.OpenThread(THREAD_GET_CONTEXT, False, event.dwThreadId)
                if hThread:
                    if kernel32.GetThreadContext(hThread, ctypes.byref(context)):
                        if context.Rip == func_addr + 1:  # RIP is at next instruction
                            bp_hit = True
                            handle_value = context.Rcx
                            print(f"\n>>> BREAKPOINT HIT! <<<")
                            print(f"    Thread: {event.dwThreadId}")
                            print(f"    RIP: 0x{context.Rip:x}")
                            print(f"    RCX (handle): 0x{context.Rcx:x}")
                            print(f"    RDX (db name): 0x{context.Rdx:x}")
                            print(f"    R8 (key): 0x{context.R8:x}")
                            print(f"    R9 (key len): {context.R9}")
                            print(f"\n*** sqlite3 HANDLE = 0x{context.Rcx:x} ***")
                            sys.exit(0)
                    kernel32.CloseHandle(hThread)

                # Not our breakpoint, continue
                kernel32.ContinueDebugEvent(event.dwProcessId, event.dwThreadId, DBG_CONTINUE)
                continue
        elif exc_code == EXCEPTION_SINGLE_STEP:
            # Single step (might be from breakpoint handling)
            pass

    kernel32.ContinueDebugEvent(event.dwProcessId, event.dwThreadId, DBG_CONTINUE)

# Cleanup
if breakpoint_set and not bp_hit:
    # Restore original byte
    orig = ctypes.c_byte(original_code)
    written = ctypes.c_size_t()
    kernel32.WriteProcessMemory(hProcess, func_addr, ctypes.byref(orig), 1, ctypes.byref(written))

kernel32.DebugActiveProcessStop(pid)
kernel32.CloseHandle(hProcess)
print("\nDone")
