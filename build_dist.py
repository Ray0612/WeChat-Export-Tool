# -*- coding: utf-8 -*-
"""构建全量发布包"""
import os, sys, shutil, subprocess

ROOT = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(ROOT, 'dist', 'WeChatExport')
print('='*50)
print('构建全量发布包')
print('='*50)

# 清理
for d in ['build']:
    p = os.path.join(ROOT, d)
    if os.path.exists(p): shutil.rmtree(p)

# PyInstaller
print('\n[1] 打包 Python GUI...')
subprocess.run([
    sys.executable, '-m', 'PyInstaller', '--noconfirm', '--onefile', '--windowed',
    '--name', 'WeChatExport',
    '--distpath', DIST,
    '--paths', ROOT,
    '--paths', os.path.join(ROOT, 'scripts'),
    '--hidden-import', 'wcdb_server',
    '--collect-all', 'wcdb_server',
    os.path.join(ROOT, 'gui', 'app_v3.py')
], cwd=ROOT, check=True)

print('\n[2] 复制运行环境...')
os.makedirs(os.path.join(DIST, 'scripts'), exist_ok=True)
os.makedirs(os.path.join(DIST, 'dll'), exist_ok=True)
os.makedirs(os.path.join(DIST, 'runtime'), exist_ok=True)

# Node.js 运行时 (从 PATH 查找或环境变量)
NODE_EXE = os.environ.get('NODE_EXE') or shutil.which('node') or shutil.which('node.exe')
if NODE_EXE and os.path.exists(NODE_EXE):
    shutil.copy(NODE_EXE, os.path.join(DIST, 'runtime', 'node.exe'))
    print('  [OK] node.exe')
else:
    print('  [WARN] node.exe not found, set NODE_EXE env var')

# Node.js 依赖
for mod in ['koffi', 'fzstd']:
    src = os.path.join(ROOT, 'scripts', 'node_modules', mod)
    dst = os.path.join(DIST, 'scripts', 'node_modules', mod)
    if os.path.exists(src):
        if os.path.exists(dst): shutil.rmtree(dst)
        shutil.copytree(src, dst)
        print(f'  [OK] node_modules/{mod}')

# scripts
for f in ['wcdb_server.js', 'wcdb_server.py', 'get_key.js']:
    shutil.copy(os.path.join(ROOT, 'scripts', f), os.path.join(DIST, 'scripts'))
print('  [OK] scripts')

# koffi 原生模块
KOFI_NATIVE = os.path.join(ROOT, 'scripts', 'node_modules', '@koromix')
dst = os.path.join(DIST, 'scripts', 'node_modules', '@koromix')
if os.path.exists(KOFI_NATIVE):
    if os.path.exists(dst): shutil.rmtree(dst)
    shutil.copytree(KOFI_NATIVE, dst)
    print('  [OK] @koromix/koffi-win32-x64')

# DLL 目录: 优先从环境变量, 回退到项目内的 dll/ 或 APP 副本
def _find_dll(name, env_var, subpath):
    path = os.environ.get(env_var)
    if path and os.path.exists(os.path.join(path, name)):
        return os.path.join(path, name)
    # 项目内 dll/ 目录
    local = os.path.join(ROOT, 'dll', name)
    if os.path.exists(local): return local
    # APP 副本
    app = os.path.join(ROOT, 'APP', 'WeChatExport', 'dll', name)
    if os.path.exists(app): return app
    return None

# WCDB DLLs
for f in ['WCDB.dll', 'wcdb_api.dll', 'SDL2.dll']:
    src = _find_dll(f, 'WCDB_DLL_DIR', '')
    if src:
        shutil.copy(src, os.path.join(DIST, 'dll'))
        print(f'  [OK] {f}')
    else:
        print(f'  [WARN] {f} not found')

# wx_key.dll
KEY_DLL_DIR = os.environ.get('KEY_DLL_DIR')
if KEY_DLL_DIR and os.path.isdir(KEY_DLL_DIR):
    for f in os.listdir(KEY_DLL_DIR):
        if f.endswith('.dll'):
            shutil.copy(os.path.join(KEY_DLL_DIR, f), os.path.join(DIST, 'dll'))
            print(f'  [OK] {f}')
else:
    for candidate in [
        os.path.join(ROOT, 'dll'),
        os.path.join(ROOT, 'APP', 'WeChatExport', 'dll'),
    ]:
        if os.path.isdir(candidate):
            for f in os.listdir(candidate):
                if f == 'wx_key.dll':
                    shutil.copy(os.path.join(candidate, f), os.path.join(DIST, 'dll'))
                    print(f'  [OK] {f}')
                    break
            break

# VC++ 运行时 DLLs
VC_DIR = os.environ.get('VC_RUNTIME_DIR')
if VC_DIR and os.path.isdir(VC_DIR):
    src_dir = VC_DIR
else:
    src_dir = os.path.join(ROOT, 'APP', 'WeChatExport', 'runtime')
    if not os.path.isdir(src_dir):
        src_dir = os.path.join(ROOT, 'runtime')
    if not os.path.isdir(src_dir):
        src_dir = None

if src_dir:
    for f in ['msvcp140.dll', 'msvcp140_1.dll', 'vcruntime140.dll', 'vcruntime140_1.dll']:
        src = os.path.join(src_dir, f)
        if os.path.exists(src):
            shutil.copy(src, os.path.join(DIST, 'runtime'))
            print(f'  [OK] {f}')

# Electron
ELECTRON_SRC = os.path.join(ROOT, 'node_modules', 'electron', 'dist')
ELECTRON_DST = os.path.join(DIST, 'electron')
if os.path.exists(ELECTRON_SRC):
    os.makedirs(ELECTRON_DST, exist_ok=True)
    for f in ['electron.exe', 'chrome_100_percent.pak', 'chrome_200_percent.pak',
              'resources.pak', 'v8_context_snapshot.bin', 'icudtl.dat',
              'snapshot_blob.bin', 'vk_swiftshader.dll', 'vk_swiftshader_icd.json',
              'd3dcompiler_47.dll', 'libEGL.dll', 'libGLESv2.dll', 'ffmpeg.dll',
              'vulkan-1.dll', 'msvcp140.dll', 'vcruntime140.dll', 'vcruntime140_1.dll']:
        src = os.path.join(ELECTRON_SRC, f)
        if os.path.exists(src):
            shutil.copy(src, ELECTRON_DST)
    for d in ['locales', 'resources']:
        src = os.path.join(ELECTRON_SRC, d)
        if os.path.exists(src):
            shutil.copytree(src, os.path.join(ELECTRON_DST, d), dirs_exist_ok=True)
    print('  [OK] electron')

# 图标
for ico in ['icon.ico', 'icon.png']:
    src = os.path.join(ROOT, 'gui', ico)
    if os.path.exists(src):
        shutil.copy(src, os.path.join(DIST, ico))
        print(f'  [OK] {ico}')

print('\n[3] 创建启动器...')
with open(os.path.join(DIST, '启动工具.bat'), 'w', encoding='utf-8') as f:
    f.write('''@echo off
chcp 65001 >nul
title 微信导出工具
echo 正在启动...
start "" "WeChatExport.exe"
''')

# 计算大小
total = 0
for dp, dn, fns in os.walk(DIST):
    for f in fns:
        try: total += os.path.getsize(os.path.join(dp, f))
        except: pass

print(f'\n[完成]\n  路径: {DIST}\n  大小: {total // 1024 // 1024}MB\n')
print('直接运行 启动工具.bat 或 WeChatExport.exe 即可')
