# -*- coding: utf-8 -*-
"""
使用 wx_key.dll 提取微信数据库密钥
DLL 通过 shellcode 注入远程线程，绕过 Chromium 沙箱
"""
import ctypes, sys, time, psutil, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Load DLL
dll_path = r'C:\Users\OK\Desktop\wx_key\assets\dll\wx_key.dll'
if not os.path.exists(dll_path):
    print(f'[-] DLL not found: {dll_path}')
    # Try alternate path
    alt = r'C:\Users\OK\Desktop\wx_key\build\windows\runner\Release\wx_key.dll'
    if os.path.exists(alt):
        dll_path = alt
    else:
        sys.exit(1)

print(f'[+] Loading {dll_path}')
dll = ctypes.CDLL(dll_path)

# Define functions
dll.InitializeHook.argtypes = [ctypes.c_uint32]
dll.InitializeHook.restype = ctypes.c_bool

dll.PollKeyData.argtypes = [ctypes.c_char_p, ctypes.c_int]
dll.PollKeyData.restype = ctypes.c_bool

dll.GetStatusMessage.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.POINTER(ctypes.c_int)]
dll.GetStatusMessage.restype = ctypes.c_bool

dll.CleanupHook.argtypes = []
dll.CleanupHook.restype = ctypes.c_bool

dll.GetLastErrorMsg.restype = ctypes.c_char_p

# Find Weixin.exe PID
pid = None
for proc in psutil.process_iter(['pid', 'name']):
    if proc.info['name'] and proc.info['name'].lower() == 'weixin.exe':
        pid = proc.info['pid']
        break

if not pid:
    print('[-] Weixin.exe not running')
    sys.exit(1)

print(f'[+] Weixin.exe PID: {pid}')
print(f'[+] Calling InitializeHook({pid})...')

result = dll.InitializeHook(pid)
if not result:
    err = dll.GetLastErrorMsg()
    print(f'[-] InitializeHook failed: {err}')
    sys.exit(1)

print('[+] InitializeHook succeeded! Polling for key...')

# Poll for key
key_buf = ctypes.create_string_buffer(128)
log_buf = ctypes.create_string_buffer(512)
log_level = ctypes.c_int()

start = time.time()
key_found = False

while time.time() - start < 30:
    # Check for key
    if dll.PollKeyData(key_buf, 128):
        key = key_buf.value.decode('ascii')
        print(f'\n{"="*50}')
        print(f'✅ KEY FOUND!')
        print(f'   64-char key: {key}')
        print(f'{"="*50}')

        # Save key
        key_path = r'C:\Users\OK\Desktop\wx_export\sqlcipher_key_captured.txt'
        with open(key_path, 'w') as f:
            f.write(key)
        print(f'   Saved to: {key_path}')
        key_found = True
        break

    # Check logs
    while dll.GetStatusMessage(log_buf, 512, log_level):
        prefix = ['[INFO]', '[OK]', '[ERR]'][log_level.value]
        msg = log_buf.value.decode('utf-8', errors='replace')
        print(f'  {prefix} {msg}')

    time.sleep(0.1)

# Cleanup
print('\n[*] Cleaning up...')
dll.CleanupHook()

if not key_found:
    print('[-] No key captured within 30 seconds')
    print('Please make sure WeChat is logged in and try again.')
