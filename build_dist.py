# -*- coding: utf-8 -*-
"""构建全量发布包 - 打包所有依赖，点开即用"""
import os, sys, shutil, subprocess, platform

ROOT = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(ROOT, 'dist', 'WeChatExport')
print('='*50)
print('构建全量发布包')
print('='*50)

# 清理 build 目录
for d in ['build']:
    p = os.path.join(ROOT, d)
    if os.path.exists(p): shutil.rmtree(p)

print('\n[1] 打包 Python GUI (PyInstaller)...')
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

# Node.js 运行时
NODE_SRC = r'D:\Program Files\nodejs\node.exe'
if os.path.exists(NODE_SRC):
    shutil.copy(NODE_SRC, os.path.join(DIST, 'runtime', 'node.exe'))
    print('  [OK] node.exe')

# Node.js 依赖
for mod in ['koffi', 'fzstd']:
    src = os.path.join(ROOT, 'scripts', 'node_modules', mod)
    dst = os.path.join(DIST, 'scripts', 'node_modules', mod)
    if os.path.exists(src):
        if os.path.exists(dst): shutil.rmtree(dst)
        shutil.copytree(src, dst)
        print(f'  [OK] node_modules/{mod}')

# scripts
for f in ['wcdb_server.js', 'wcdb_server.py', 'get_key_wx.py', 'get_key.js']:
    shutil.copy(os.path.join(ROOT, 'scripts', f), os.path.join(DIST, 'scripts'))
print('  [OK] scripts')

# koffi 原生模块
KOFI_NATIVE = os.path.join(ROOT, 'scripts', 'node_modules', '@koromix')
dst = os.path.join(DIST, 'scripts', 'node_modules', '@koromix')
if os.path.exists(KOFI_NATIVE):
    if os.path.exists(dst): shutil.rmtree(dst)
    shutil.copytree(KOFI_NATIVE, dst)
    print('  [OK] @koromix/koffi-win32-x64')

# WCDB DLLs
WCDB_SRC = r'C:\Users\OK\AppData\Local\Programs\WeFlow\resources\resources\wcdb\win32\x64'
for f in ['WCDB.dll', 'wcdb_api.dll', 'SDL2.dll']:
    src = os.path.join(WCDB_SRC, f)
    if os.path.exists(src):
        shutil.copy(src, os.path.join(DIST, 'dll'))
        print(f'  [OK] {f}')

# wx_key.dll
KEY_SRC = r'C:\Users\OK\AppData\Local\Programs\WeFlow\resources\resources\key\win32\x64'
for f in os.listdir(KEY_SRC):
    if f.endswith('.dll'):
        shutil.copy(os.path.join(KEY_SRC, f), os.path.join(DIST, 'dll'))
        print(f'  [OK] {f}')

# VC++ 运行时 DLLs
RUNTIME_SRC = r'C:\Users\OK\AppData\Local\Programs\WeFlow'
for f in ['msvcp140.dll', 'msvcp140_1.dll', 'vcruntime140.dll', 'vcruntime140_1.dll']:
    src = os.path.join(RUNTIME_SRC, f)
    if os.path.exists(src):
        shutil.copy(src, os.path.join(DIST, 'runtime'))
        print(f'  [OK] {f}')

# Go decrypt 工具
GO_SRC = os.path.join(ROOT, 'scripts', 'decrypt.exe')
if os.path.exists(GO_SRC):
    shutil.copy(GO_SRC, os.path.join(DIST, 'tools'))
    print('  [OK] decrypt.exe')

# Electron (最小化 - 仅 WCDB 需要)
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
    # locales + resources 目录（electron 必需）
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
launcher = '''@echo off
chcp 65001 >nul
title 微信导出工具
echo 正在启动...
start "" "WeChatExport.exe"
'''
with open(os.path.join(DIST, '启动工具.bat'), 'w', encoding='utf-8') as f:
    f.write(launcher)

# 计算大小
total = 0
for dp, dn, fns in os.walk(DIST):
    for f in fns:
        try: total += os.path.getsize(os.path.join(dp, f))
        except: pass

print(f'\n[完成]')
print(f'  路径: {DIST}')
print(f'  大小: {total // 1024 // 1024}MB')
print()
print('在其他电脑上直接运行 启动工具.bat 或 WeChatExport.exe 即可')
