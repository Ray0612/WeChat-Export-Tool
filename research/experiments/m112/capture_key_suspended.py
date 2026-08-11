# -*- coding: utf-8 -*-
"""
使用 CREATE_SUSPENDED 启动 Weixin.exe，在 main 函数执行前 hook key
"""
import ctypes, ctypes.wintypes, frida, time, sys, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

OUTDIR = r'C:\Users\OK\Desktop\wx_export'

# Windows API types
CREATE_SUSPENDED = 0x00000004
PROCESS_ALL_ACCESS = 0x1FFFFF

kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

CreateProcessW = kernel32.CreateProcessW
CreateProcessW.argtypes = [
    ctypes.wintypes.LPCWSTR, ctypes.wintypes.LPWSTR,
    ctypes.c_void_p, ctypes.c_void_p,
    ctypes.wintypes.BOOL, ctypes.wintypes.DWORD,
    ctypes.c_void_p, ctypes.wintypes.LPCWSTR,
    ctypes.c_void_p, ctypes.c_void_p
]
CreateProcessW.restype = ctypes.wintypes.BOOL

ResumeThread = kernel32.ResumeThread
ResumeThread.argtypes = [ctypes.wintypes.HANDLE]
ResumeThread.restype = ctypes.wintypes.DWORD

class PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [
        ('hProcess', ctypes.wintypes.HANDLE),
        ('hThread', ctypes.wintypes.HANDLE),
        ('dwProcessId', ctypes.wintypes.DWORD),
        ('dwThreadId', ctypes.wintypes.DWORD),
    ]

class STARTUPINFOW(ctypes.Structure):
    _fields_ = [
        ('cb', ctypes.wintypes.DWORD),
        ('lpReserved', ctypes.wintypes.LPWSTR),
        ('lpDesktop', ctypes.wintypes.LPWSTR),
        ('lpTitle', ctypes.wintypes.LPWSTR),
        ('dwX', ctypes.wintypes.DWORD),
        ('dwY', ctypes.wintypes.DWORD),
        ('dwXSize', ctypes.wintypes.DWORD),
        ('dwYSize', ctypes.wintypes.DWORD),
        ('dwXCountChars', ctypes.wintypes.DWORD),
        ('dwYCountChars', ctypes.wintypes.DWORD),
        ('dwFillAttribute', ctypes.wintypes.DWORD),
        ('dwFlags', ctypes.wintypes.DWORD),
        ('wShowWindow', ctypes.wintypes.WORD),
        ('cbReserved2', ctypes.wintypes.WORD),
        ('lpReserved2', ctypes.c_byte * 1),
        ('hStdInput', ctypes.wintypes.HANDLE),
        ('hStdOutput', ctypes.wintypes.HANDLE),
        ('hStdError', ctypes.wintypes.HANDLE),
    ]

weixin_path = r'C:\Program Files\Tencent\Weixin\Weixin.exe'
if not os.path.exists(weixin_path):
    print(f'[-] Weixin.exe not found')
    sys.exit(1)

print(f'[+] Starting Weixin.exe suspended...')

si = STARTUPINFOW()
si.cb = ctypes.sizeof(si)
pi = PROCESS_INFORMATION()

success = CreateProcessW(
    weixin_path, None, None, None, False,
    CREATE_SUSPENDED, None, None,
    ctypes.byref(si), ctypes.byref(pi)
)

if not success:
    print(f'[-] CreateProcess failed: {ctypes.get_last_windows_error()}')
    sys.exit(1)

pid = pi.dwProcessId
hProcess = pi.hProcess
hThread = pi.hThread
print(f'[+] Suspended process PID: {pid}')

# Attach Frida to the suspended process
try:
    device = frida.get_local_device()
    session = device.attach(pid)
    print('[+] Frida attached')

    # Hook the key function
    hook_code = '''
    // Hook module load to catch Weixin.dll as soon as it loads
    Process.on("module-loaded", function(m) {
        if (m.name.indexOf("Weixin.dll") !== -1) {
            console.log("[+] Weixin.dll loaded at " + m.base);
            Interceptor.attach(m.base.add(0x55d0f0), {
                onEnter: function(args) {
                    console.log("[+] KEY FUNCTION CALLED!");
                    for (var i = 0; i < 4; i++) {
                        try {
                            var d = Memory.readByteArray(args[i], 32);
                            var a = new Uint8Array(d);
                            var s = {};
                            for (var j = 0; j < a.length; j++) s[a[j]] = true;
                            if (Object.keys(s).length >= 20) {
                                var h = "";
                                for (var j = 0; j < a.length; j++) h += ("0" + a[j].toString(16)).slice(-2);
                                console.log("[KEY] " + h);
                            }
                        } catch(e) {}
                    }
                }
            });
            console.log("[+] Hook set on key function");
        }
    });

    // Also check if already loaded
    var m = Process.findModuleByName("Weixin.dll");
    if (m) {
        console.log("[+] Weixin.dll already loaded, hooking directly");
        Interceptor.attach(m.base.add(0x55d0f0), {
            onEnter: function(args) {
                console.log("[+] KEY FUNCTION CALLED!");
                for (var i = 0; i < 4; i++) {
                    try {
                        var d = Memory.readByteArray(args[i], 32);
                        var a = new Uint8Array(d);
                        var s = {};
                        for (var j = 0; j < a.length; j++) s[a[j]] = true;
                        if (Object.keys(s).length >= 20) {
                            var h = "";
                            for (var j = 0; j < a.length; j++) h += ("0" + a[j].toString(16)).slice(-2);
                            console.log("[KEY] " + h);
                        }
                    } catch(e) {}
                }
            }
        });
    }
    '''

    script = session.create_script(hook_code)
    script.on('message', lambda m, d: print(f'{m.get("payload", "")}'))
    script.load()
    print('[+] Script loaded, resuming process...')

    # Resume the process
    ResumeThread(hThread)
    print('[+] Process resumed, waiting for key...')

    # Wait for key
    time.sleep(20)
    session.detach()

except Exception as e:
    print(f'[-] Error: {e}')
    # Resume anyway
    try:
        ResumeThread(hThread)
    except: pass

# Cleanup
kernel32.CloseHandle(hProcess)
kernel32.CloseHandle(hThread)
