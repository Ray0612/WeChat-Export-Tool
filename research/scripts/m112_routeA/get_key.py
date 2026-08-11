# -*- coding: utf-8 -*-
"""
wx_key.dll key 提取器 — 仿 WeFlow 实现
管理员权限 + 找微信进程 + InitializeHook + PollKeyData
"""
import ctypes, sys, os, time, subprocess, json

# ── 自提权 ──
def elevate():
    if ctypes.windll.shell32.IsUserAnAdmin():
        return True
    script = os.path.abspath(__file__)
    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, f'"{script}"', None, 1)
    return False

if not elevate():
    sys.exit(0)

print('=' * 50)
print('wx_key.dll Key Extractor')
print('=' * 50)

# ── 1. 找微信 PID ──
print('\n[1] 查找微信进程...')
try:
    result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq Weixin.exe', '/FO', 'CSV', '/NH'],
                          capture_output=True, text=True, timeout=10)
    pid = None
    for line in result.stdout.strip().split('\n'):
        if 'Weixin.exe' in line:
            parts = [p.strip('"') for p in line.split('","')]
            pid = int(parts[1])
            break
    if not pid:
        print('[-] 微信未运行，请先打开微信')
        sys.exit(1)
    print(f'[+] Weixin.exe PID: {pid}')
except Exception as e:
    print(f'[-] 查找失败: {e}')
    sys.exit(1)

# ── 2. 加载 wx_key.dll ──
print('\n[2] 加载 wx_key.dll...')

# 找 DLL 路径
dll_candidates = [
    os.path.join(os.path.dirname(__file__), '..', '..', 'tools', 'weflow', 'source', 'enjoyZhou-WeFlow-70aff53', 'resources', 'key', 'win32', 'x64', 'wx_key.dll'),
    os.path.join(os.path.dirname(__file__), '..', '..', 'tools', 'wx_key', 'assets', 'dll', 'wx_key.dll'),
    r'C:\Users\OK\AppData\Local\Programs\WeFlow\resources\resources\key\win32\x64\wx_key.dll',
]

dll_path = None
for p in dll_candidates:
    if os.path.exists(p):
        dll_path = os.path.abspath(p)
        break

if not dll_path:
    print('[-] wx_key.dll 未找到')
    sys.exit(1)

print(f'[+] DLL: {dll_path}')

try:
    dll = ctypes.CDLL(dll_path)
except Exception as e:
    print(f'[-] 加载失败: {e}')
    sys.exit(1)

# ── 3. 绑定函数 ──
dll.InitializeHook.argtypes = [ctypes.c_uint32]
dll.InitializeHook.restype = ctypes.c_bool
dll.PollKeyData.argtypes = [ctypes.c_char_p, ctypes.c_int]
dll.PollKeyData.restype = ctypes.c_bool
dll.GetStatusMessage.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.POINTER(ctypes.c_int)]
dll.GetStatusMessage.restype = ctypes.c_bool
dll.CleanupHook.argtypes = []
dll.CleanupHook.restype = ctypes.c_bool
dll.GetLastErrorMsg.restype = ctypes.c_char_p

# ── 4. 调用 InitializeHook ──
print(f'\n[3] InitializeHook({pid})...')
result = dll.InitializeHook(pid)

if not result:
    err = dll.GetLastErrorMsg()
    err_msg = err.decode('utf-8', errors='replace') if err else '未知错误'
    print(f'[-] InitializeHook 失败: {err_msg}')

    # 读日志
    buf = ctypes.create_string_buffer(512)
    level = ctypes.c_int()
    print('\n[DLL 日志]:')
    while dll.GetStatusMessage(buf, 512, level):
        print(f'  [{level.value}] {buf.value.decode("utf-8", errors="replace")}')
    sys.exit(1)

print('[+] InitializeHook 成功，正在监听 key...')

# ── 5. 轮询 key ──
key_buf = ctypes.create_string_buffer(128)
log_buf = ctypes.create_string_buffer(512)
log_level = ctypes.c_int()

start = time.time()
timeout = 60

print(f'\n[4] 轮询 key (超时 {timeout}s)...')
print('   请确保微信已登录，可尝试翻看聊天记录\n')

while time.time() - start < timeout:
    if dll.PollKeyData(key_buf, 128):
        key = key_buf.value.decode('ascii')
        print(f'\n{"="*50}')
        print(f'✅ KEY: {key}')
        print(f'{"="*50}')

        # 保存
        out = r'C:\Users\OK\Desktop\wx_export\sqlcipher_key_captured.txt'
        with open(out, 'w') as f:
            f.write(key)
        print(f'   已保存: {out}')
        dll.CleanupHook()
        sys.exit(0)

    while dll.GetStatusMessage(log_buf, 512, log_level):
        msg = log_buf.value.decode('utf-8', errors='replace')
        print(f'  {msg}')

    time.sleep(0.1)

print('\n[-] 超时未获取到 key')
dll.CleanupHook()
