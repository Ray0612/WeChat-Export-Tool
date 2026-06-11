# -*- coding: utf-8 -*-
"""Key 提取 - 调 Node.js + koffi + wx_key.dll (和 WeFlow 一样)"""
import ctypes, subprocess, os, sys, time, json

if ctypes.windll.shell32.IsUserAnAdmin() == 0:
    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, f'"{__file__}"', None, 0)
    sys.exit(0)

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(os.environ.get('USERPROFILE', BASE), 'Desktop', 'wx_export')
os.makedirs(OUT, exist_ok=True)

script = os.path.join(BASE, 'scripts', 'get_key.js')
node = os.path.join(BASE, 'runtime', 'node.exe')
if not os.path.exists(node):
    node = os.path.join(BASE, 'runtime', 'node.exe')  # 还走这个路径，确保文件存在

print('[KEY] 启动 Node.js key 提取...')
result = subprocess.run([node, script], cwd=BASE, capture_output=True, text=True, timeout=180)
print(result.stdout)
if result.stderr:
    print(f'[KEY] 错误: {result.stderr[:200]}')
