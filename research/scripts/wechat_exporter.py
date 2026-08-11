# 微信聊天记录导出工具
# 支持导出 TXT + PDF
# 用法: python wechat_exporter.py [--contact 联系人] [--format txt|pdf|both] [--limit 消息数] [--output 目录] [--max-contacts 数量]

import os
import sys
import re
import argparse
import sqlite3
from datetime import datetime
from pathlib import Path

# ===== 配置 =====
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "导出结果")
MAX_CONTACTS_DEFAULT = 0   # 0 = 无限制
MSG_LIMIT_DEFAULT = 10000

# 尝试导入依赖
try:
    from Cryptodome.Cipher import AES
except ImportError:
    AES = None

try:
    import pymem
except ImportError:
    pymem = None

try:
    from fpdf import FPDF
except ImportError:
    FPDF = None


# ========================================================================
#  第一步：从微信进程内存提取数据库密钥
# ========================================================================

def get_wechat_process():
    """查找微信进程（兼容 WeChat.exe 和 Weixin.exe）"""
    if pymem is None:
        raise Exception("缺少 pymem 库，请先安装: pip install pymem")

    for proc_name in ["WeChat.exe", "Weixin.exe"]:
        try:
            pm = pymem.Pymem(proc_name)
            print(f"  ✅ 已找到微信进程: {proc_name} (PID: {pm.process_id})")
            return pm, proc_name
        except pymem.exception.ProcessNotFound:
            continue
        except Exception:
            continue

    raise Exception(
        "未找到微信进程（WeChat.exe / Weixin.exe），请先登录微信\n"
        "  ⚠ 本工具需要管理员权限才能读取微信内存，请以管理员身份运行"
    )


def find_wechat_module(pm):
    """定位微信核心模块（4.x = Weixin.dll, 3.x = WeChatWin.dll）"""
    targets_4x = ["Weixin.dll"]
    targets_3x = ["WeChatWin.dll", "WeChat.dll"]
    all_modules = list(pm.list_modules())

    # 1. 精确匹配 4.x 核心 DLL
    for mod in all_modules:
        name = mod.name.split("\\")[-1].lower()
        if name == "weixin.dll":
            return mod

    # 2. 精确匹配 3.x 核心 DLL
    for mod in all_modules:
        name = mod.name.split("\\")[-1].lower()
        if name in ("wechatwin.dll", "wechat.dll"):
            return mod

    # 3. 模糊匹配
    for mod in all_modules:
        name = mod.name.split("\\")[-1].lower()
        if name == "weixin.exe":
            continue  # 跳过 EXE 自身，太小了
        for t in ["weixin.dll", "wechatwin.dll", "wechat.dll"]:
            if t in name:
                return mod

    # 4. 找最大的非系统 DLL
    best = None
    best_size = 0
    for mod in all_modules:
        name = mod.name.split("\\")[-1]
        if name.endswith(".dll") and not name.startswith(("api-", "ext-", "ntdll")):
            if mod.SizeOfImage > best_size:
                best_size = mod.SizeOfImage
                best = mod

    if best:
        return best

    # 调试
    print("  ⚠ 未找到目标模块，列出所有加载的模块：")
    for mod in all_modules:
        name = mod.name.split("\\")[-1]
        size_mb = mod.SizeOfImage / 1024 / 1024
        print(f"    {name:30s}  {size_mb:.1f}MB")
    raise Exception("无法找到微信核心模块")


def module_info(pm, module):
    return module.lpBaseOfDll, module.SizeOfImage


# ---------------------- 策略 1: 特征码扫描 ----------------------

def search_pattern_in_module(pm, base, size, pattern, chunk_size=1024 * 1024):
    """在模块内存中搜索字节模式，返回第一次匹配的位置（相对于 base）"""
    for offset in range(0, size, chunk_size):
        to_read = min(chunk_size, size - offset)
        try:
            data = pm.read_bytes(base + offset, to_read)
        except Exception:
            continue

        pos = data.find(pattern)
        if pos >= 0:
            return offset + pos
    return None


def search_all_patterns(pm, base, size, pattern, chunk_size=1024 * 1024):
    """搜索所有匹配位置"""
    positions = []
    for offset in range(0, min(size, 200 * 1024 * 1024), chunk_size):
        to_read = min(chunk_size, size - offset)
        try:
            data = pm.read_bytes(base + offset, to_read)
        except Exception:
            continue

        pos = 0
        while True:
            pos = data.find(pattern, pos)
            if pos < 0:
                break
            positions.append(offset + pos)
            pos += 1

            if len(positions) >= 50:  # 最多搜 50 处
                return positions
    return positions


def try_extract_key_near_pattern(pm, module_base, pattern_pos, offsets_to_try):
    """在特征位置附近尝试读取密钥"""
    for off in offsets_to_try:
        addr = module_base + pattern_pos + off
        try:
            # 尝试读取 32 字节（原始密钥）
            key_bytes = pm.read_bytes(addr, 32)
            hex_key = key_bytes.hex()
            if is_valid_hex_key(hex_key) and validate_key(hex_key):
                return hex_key
        except Exception:
            pass

        # 也尝试读取附近可能的 hex 字符串
        try:
            nearby = pm.read_bytes(addr - 32, 128)
            text = nearby.decode("ascii", errors="ignore")
            # 找 64 位 hex
            for m in re.finditer(r'[0-9a-fA-F]{64}', text):
                if validate_key(m.group()):
                    return m.group()
        except Exception:
            pass
    return None


def extract_key_via_signature(pm, module_base, module_size):
    """
    特征码扫描法：
    搜索数据库路径字符串（如 \\Msg\\MicroMsg.db），
    在其附近偏移处读取 32 字节（即数据库加密密钥）。
    """
    # 特征码：数据库路径（微信在内存中存储的路径字符串）
    patterns = [
        (b'\\Msg\\MicroMsg.db',     "MicroMsg.db"),
        (b'\\Msg\\Misc.db',         "Misc.db"),
        (b'\\Msg\\FTSContact.db',   "FTSContact.db"),
        (b'\\Msg\\Media.db',        "Media.db"),
        (b'\\Msg\\Snap.db',         "Snap.db"),
        (b'MicroMsg.db',           "MicroMsg.db(short)"),
        (b'Misc.db',               "Misc.db(short)"),
    ]

    # 密钥相对于特征串的可能偏移（根据 PyWxDump / wechat-dump-rs 经验）
    candidate_offsets = list(range(-0x30, -0x60, -8))  # -0x30, -0x38, -0x40, -0x48, -0x50, -0x58
    candidate_offsets += list(range(-0x80, -0x100, -8))  # 更远范围
    candidate_offsets += list(range(0x10, 0x60, 8))  # 正向范围

    for pattern_bytes, pattern_name in patterns:
        positions = search_all_patterns(pm, module_base, module_size, pattern_bytes)
        if not positions:
            continue

        for pos in positions:
            key = try_extract_key_near_pattern(pm, module_base, pos, candidate_offsets)
            if key:
                print(f"  🔍 特征码 '{pattern_name}' 定位成功 (偏移 0x{pos:x})")
                return key

    return None


# ---------------------- 策略 2: Hex 字符串搜索 ----------------------

def extract_key_via_hex_search(pm, module_base, module_size):
    """
    Hex 字符串搜索法（原方案改进版）：
    在可读内存区域搜索连续的 64 位 hex 字符串。
    """
    chunk_size = 1024 * 1024
    found_keys = set()

    # 只扫描前 50MB（代码段在开头，数据段在后面）
    scan_limit = min(module_size, 200 * 1024 * 1024)

    for offset in range(0, scan_limit, chunk_size):
        to_read = min(chunk_size, scan_limit - offset)
        try:
            data = pm.read_bytes(module_base + offset, to_read)
        except Exception:
            continue

        # 用正则找 64 位 hex
        for m in re.finditer(rb'[0-9a-fA-F]{64}', data):
            key = m.group().decode("ascii")
            found_keys.add(key)

    print(f"  🔍 发现 {len(found_keys)} 个候选 hex 密钥，正在验证...")
    for key in found_keys:
        if validate_key(key):
            return key

    return None


# ---------------------- 微信 4.x 专用策略 ----------------------

def is_wechat_v4(pm, module_base):
    """检测当前微信是否为 4.x 版本"""
    try:
        for m in pm.list_modules():
            name = m.name.split("\\")[-1].lower()
            if name == "weixin.dll":
                return True
            if name == "wechatwin.dll":
                return False
    except Exception:
        pass
    # 如果当前模块是 weixin.exe（且没找到 weixin.dll）-> 不是 4.x
    try:
        for m in pm.list_modules():
            if m.lpBaseOfDll == module_base:
                if m.name.split("\\")[-1].lower() == "weixin.exe":
                    return False
    except Exception:
        pass
    return None


def detect_wechat_version(pm):
    """检测微信版本号"""
    try:
        for m in pm.list_modules():
            name = m.name.split("\\")[-1].lower()
            if name == "weixin.exe":
                # 尝试读取版本信息
                import struct
                base = m.lpBaseOfDll
                # 尝试从 PE 头读取版本
                data = pm.read_bytes(base, 0x1000)
                # PE header starts at offset 0x3C
                pe_offset = struct.unpack_from("<I", data, 0x3C)[0]
                return "4.x"
    except Exception:
        pass
    return None


def extract_key_v4_setdbkey(pm, module_base, module_size):
    """
    微信 4.x 密钥提取：搜索 'SetDBKey' 字符串（ASCII + UTF-16）。
    """
    patterns = [
        (b"SetDBKey",              "ASCII"),
        (b"S\x00e\x00t\x00D\x00B\x00K\x00e\x00y\x00", "UTF-16LE"),
        (b"setCipherKey",          "setCipherKey(ASCII)"),
    ]
    chunk_size = 1024 * 1024
    scan_limit = min(module_size, 150 * 1024 * 1024)

    for pattern, desc in patterns:
        for offset in range(0, scan_limit, chunk_size):
            to_read = min(chunk_size, scan_limit - offset)
            try:
                data = pm.read_bytes(module_base + offset, to_read)
            except Exception:
                continue

            pos = 0
            while True:
                pos = data.find(pattern, pos)
                if pos < 0:
                    break

                print(f"    found '{desc}' at 0x{offset + pos:x}")
                abs_pos = offset + pos
                search_start = max(0, pos - 0x400)
                search_end = min(len(data), pos + 0x400)
                nearby = data[search_start:search_end]

                # 搜索 64 位 hex
                for m in re.finditer(rb'[0-9a-fA-F]{64}', nearby):
                    key = m.group().decode("ascii")
                    if validate_key(key):
                        print(f"  🔍 SetDBKey({desc}) 特征定位成功")
                        return key

                # 读取原始 32 字节（宽范围偏移）
                for off in list(range(-0x80, -0x200, -8)) + list(range(0x20, 0x100, 8)):
                    try:
                        raw = pm.read_bytes(module_base + offset + pos + off, 32)
                        if len(raw) == 32:
                            key = raw.hex()
                            if validate_key(key):
                                print(f"  🔍 SetDBKey({desc}) 附近发现密钥 @0x{offset + pos + off:x}")
                                return key
                    except Exception:
                        pass

                pos += 1

    return None


def extract_key_v4_dbpath(pm, module_base, module_size):
    """
    微信 4.x 密钥提取：搜索数据库路径字符串。
    """
    patterns = [
        (b'applet.db',       "applet.db"),
        (b'radium\\users',   "radium/users"),
        (b'xwechat',         "xwechat"),
        (b'MicroMsg.db',     "MicroMsg.db(4.x)"),
    ]

    candidate_offsets = list(range(-0x30, -0x60, -8))
    candidate_offsets += list(range(-0x80, -0x180, -8))
    candidate_offsets += list(range(0x10, 0x80, 8))

    for pattern_bytes, pattern_name in patterns:
        positions = search_all_patterns(pm, module_base, module_size, pattern_bytes)
        if not positions:
            continue

        for pos in positions:
            key = try_extract_key_near_pattern(pm, module_base, pos, candidate_offsets)
            if key:
                print(f"  🔍 V4特征 '{pattern_name}' 定位成功 (偏移 0x{pos:x})")
                return key

    return None


def extract_key_v4(pm, module_base, module_size):
    """微信 4.x 专用密钥提取"""
    print("\n  🔍 [4.x] 策略A: 关键词搜索(SetDBKey/CipherConfigName)...")
    key = extract_key_v4_setdbkey(pm, module_base, module_size)
    if key:
        return key

    print("\n  🔍 [4.x] 策略B: V4 数据库路径特征搜索...")
    key = extract_key_v4_dbpath(pm, module_base, module_size)
    if key:
        return key

    print("\n  🔍 [4.x] 策略C: 搜索 x'<64hex>' 格式密钥...")
    key = extract_key_v4_xhex(pm)
    if key:
        return key

    print("\n  🔍 [4.x] 策略D: 全内存扫描 32 字节高熵数据...")
    key = extract_key_v4_entropy_scan(pm)
    if key:
        return key

    return None


def extract_key_v4_xhex(pm):
    """
    搜索 'x'<64hex>'' 格式的密钥字符串。
    据分析，4.x 密钥以 PRAGMA 格式常驻堆内存。
    """
    import ctypes, ctypes.wintypes
    from ctypes import byref, POINTER, c_size_t, c_ulong

    class MEMORY_BASIC_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("BaseAddress", ctypes.c_void_p),
            ("AllocationBase", ctypes.c_void_p),
            ("AllocationProtect", ctypes.c_ulong),
            ("RegionSize", ctypes.c_size_t),
            ("State", ctypes.c_ulong),
            ("Protect", ctypes.c_ulong),
            ("Type", ctypes.c_ulong),
        ]

    MEM_COMMIT = 0x1000
    PAGE_READWRITE = 0x04
    PAGE_EXECUTE_READWRITE = 0x40

    kernel32 = ctypes.windll.kernel32
    h_process = ctypes.c_void_p(pm.process_handle)
    VirtualQueryEx = kernel32.VirtualQueryEx
    ReadProcessMemory = kernel32.ReadProcessMemory
    VirtualQueryEx.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(MEMORY_BASIC_INFORMATION), ctypes.c_size_t]
    ReadProcessMemory.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(c_size_t)]

    # 多模式搜索
    patterns = [
        (re.compile(rb"x'([0-9a-fA-F]{64})'"),  "x'<hex>'"),
        (re.compile(rb"x'([0-9a-fA-F]{64})"),   "x'<hex>(no close)"),
        (re.compile(rb"([0-9a-fA-F]{64})"),      "plain <64hex>"),
    ]

    address = 0x00010000  # 避开 NULL 页
    max_addr = 0x0007FFFF_FFFFFFFF  # 64-bit 用户空间上限
    checked = 0
    found_count = 0

    while address < max_addr:
        mbi = MEMORY_BASIC_INFORMATION()
        ret = VirtualQueryEx(h_process, ctypes.c_void_p(address), byref(mbi), ctypes.sizeof(mbi))
        if ret == 0:
            break

        if (mbi.State == MEM_COMMIT and
            mbi.Protect in (PAGE_READWRITE, PAGE_EXECUTE_READWRITE) and
            0 < mbi.RegionSize <= 16 * 1024 * 1024):  # 上限 16MB

            try:
                buf = ctypes.create_string_buffer(mbi.RegionSize)
                bytes_read = c_size_t(0)
                if ReadProcessMemory(h_process, mbi.BaseAddress, buf, mbi.RegionSize, byref(bytes_read)):
                    data = buf.raw[:bytes_read.value]
                    for pat, desc in patterns:
                        for m in pat.finditer(data):
                            found_count += 1
                            key = m.group(1).decode("ascii")
                            if found_count <= 3:  # 只打印前 3 个
                                print(f"    candidate #{found_count} @ 0x{mbi.BaseAddress + m.start():x} ({desc})")
                            if validate_key(key):
                                print(f"  🔍 V4 x'<hex>' 格式密钥 @ 0x{mbi.BaseAddress + m.start():x}")
                                return key
            except Exception:
                pass

        checked += 1
        if checked % 500 == 0:
            print(f"    已扫描 {checked} 个内存区域，发现 {found_count} 个候选...")

        address += mbi.RegionSize
        # 防止死循环（某些情况下 RegionSize 可能为 0）
        if mbi.RegionSize == 0:
            address += 0x1000

    print(f"    扫描完成: {checked} 个区域, {found_count} 个候选")
    return None


def extract_key_v4_entropy_scan(pm):
    """
    全内存扫描 32 字节高熵数据块（AES 密钥特征）。
    """
    import ctypes, ctypes.wintypes
    from ctypes import byref, POINTER, c_size_t

    class MEMORY_BASIC_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("BaseAddress", ctypes.c_void_p),
            ("AllocationBase", ctypes.c_void_p),
            ("AllocationProtect", ctypes.c_ulong),
            ("RegionSize", ctypes.c_size_t),
            ("State", ctypes.c_ulong),
            ("Protect", ctypes.c_ulong),
            ("Type", ctypes.c_ulong),
        ]

    MEM_COMMIT = 0x1000
    PAGE_READWRITE = 0x04
    PAGE_EXECUTE_READWRITE = 0x40

    kernel32 = ctypes.windll.kernel32
    h_process = ctypes.c_void_p(pm.process_handle)
    VirtualQueryEx = kernel32.VirtualQueryEx
    ReadProcessMemory = kernel32.ReadProcessMemory
    VirtualQueryEx.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(MEMORY_BASIC_INFORMATION), ctypes.c_size_t]
    ReadProcessMemory.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(c_size_t)]

    address = 0x00010000
    max_addr = 0x0007FFFF_FFFFFFFF
    checked = tested = 0

    while address < max_addr:
        mbi = MEMORY_BASIC_INFORMATION()
        ret = VirtualQueryEx(h_process, ctypes.c_void_p(address), byref(mbi), ctypes.sizeof(mbi))
        if ret == 0:
            break

        if (mbi.State == MEM_COMMIT and
            mbi.Protect in (PAGE_READWRITE, PAGE_EXECUTE_READWRITE) and
            4096 <= mbi.RegionSize <= 4 * 1024 * 1024):

            try:
                buf = ctypes.create_string_buffer(mbi.RegionSize)
                bytes_read = c_size_t(0)
                if ReadProcessMemory(h_process, mbi.BaseAddress, buf, mbi.RegionSize, byref(bytes_read)):
                    data = buf.raw[:bytes_read.value]
                    checked += 1
                    for i in range(len(data) - 33):
                        block = data[i:i+32]
                        if block[0] in (0, 0xff):
                            continue
                        s = set(block)
                        if len(s) < 10 or len(s) > 28:
                            continue
                        key = block.hex()
                        tested += 1
                        if validate_key(key):
                            print(f"  🔍 熵扫描发现密钥 @ 0x{mbi.BaseAddress + i:x}")
                            return key
            except Exception:
                pass

        address += mbi.RegionSize
        if mbi.RegionSize == 0:
            address += 0x1000

    print(f"    熵扫描完成: {checked} 个区域, {tested} 个候选测试")
    return None
    ReadProcessMemory.restype = ctypes.c_size_t

    address = 0x00000000
    max_addr = 0x7FFFFFFF_FFFF
    checked = 0

    while address < max_addr:
        mbi = MEMORY_BASIC_INFORMATION()
        if VirtualQueryEx(h_process, ctypes.c_void_p(address), byref(mbi), ctypes.sizeof(mbi)) == 0:
            break

        if (mbi.State == MEM_COMMIT and
            mbi.Protect in (PAGE_READWRITE, PAGE_EXECUTE_READWRITE) and
            4096 <= mbi.RegionSize <= 4 * 1024 * 1024):  # 4KB ~ 4MB

            try:
                buf = ctypes.create_string_buffer(mbi.RegionSize)
                bytes_read = c_size_t(0)
                if ReadProcessMemory(h_process, mbi.BaseAddress, buf, mbi.RegionSize, byref(bytes_read)):
                    data = buf.raw[:bytes_read.value]
                    checked += 1

                    # 滑动窗口搜索 32 字节
                    if len(data) >= 32:
                        for i in range(len(data) - 32):
                            block = data[i:i+32]
                            # AES 密钥特征：非全 0/全 F，有一定的熵值
                            if block[0] == 0 or block[0] == 0xff:
                                continue
                            s = set(block)
                            if len(s) < 8 or len(s) > 30:
                                continue
                            # 尝试作为密钥
                            key = block.hex()
                            if validate_key(key):
                                print(f"  🔍 熵扫描发现密钥 @ 0x{mbi.BaseAddress + i:x}")
                                return key
            except Exception:
                pass

        address += mbi.RegionSize

    print(f"    扫描了 {checked} 个内存区域，未发现密钥")
    return None


# ---------------------- 策略 3: 备选模式搜索 ----------------------

def extract_key_via_public_key_pattern(pm, module_base, module_size):
    """在 -----BEGIN PUBLIC KEY----- 附近搜索密钥"""
    pattern = b"-----BEGIN PUBLIC KEY-----"
    chunk_size = 1024 * 1024
    scan_limit = min(module_size, 100 * 1024 * 1024)  # 只搜 100MB

    for offset in range(0, scan_limit, chunk_size):
        to_read = min(chunk_size, scan_limit - offset)
        try:
            data = pm.read_bytes(module_base + offset, to_read)
        except Exception:
            continue

        pos = data.find(pattern)
        if pos < 0:
            continue

        # 在公钥附近搜索 hex 密钥
        start = max(0, pos - 2000)
        end = min(len(data), pos + 2000)
        nearby = data[start:end]
        for m in re.finditer(rb'[0-9a-fA-F]{64}', nearby):
            key = m.group().decode("ascii")
            if validate_key(key):
                print(f"  🔍 公钥特征定位成功 (偏移 0x{offset + start + m.start():x})")
                return key

    return None


# ---------------------- 统一密钥提取入口 ----------------------

def scan_process_memory_global(pm, pattern, scan_size=200 * 1024 * 1024):
    """在整个进程地址空间中搜索模式"""
    # 尝试在常用的地址范围搜索
    ranges = [
        (0x00000000, min(scan_size, 0x7FFFFFFF)),
    ]
    for start, size in ranges:
        chunk = 1024 * 1024
        for offset in range(0, size, chunk):
            try:
                data = pm.read_bytes(start + offset, min(chunk, size - offset))
                pos = data.find(pattern)
                if pos >= 0:
                    return start + offset + pos
            except Exception:
                continue
    return None


def read_key_from_memory(pm):
    """多策略提取密钥：V4 → V3 特征码 → hex 搜索 → 公钥附近 → 手动输入"""
    try:
        module = find_wechat_module(pm)
        module_base, module_size = module_info(pm, module)
        module_name = module.name.split("\\")[-1]
        print(f"  📦 模块: {module_name} @ 0x{module_base:x}, 大小: {module_size // 1024 // 1024}MB")
    except Exception as e:
        print(f"  ⚠ {e}，将尝试全进程内存扫描")
        module_base, module_size = 0x00000000, 200 * 1024 * 1024
        module_name = "unknown"

    # 检测是否微信 4.x
    v4 = is_wechat_v4(pm, module_base)

    # 如果是 4.x，优先使用 4.x 专用策略
    if v4 is not False:  # True 或 None（不确定时也试一下）
        print("\n  📌 检测到微信 4.x（Radium 架构），使用 4.x 专用提取方法")
        key = extract_key_v4(pm, module_base, module_size)
        if key:
            # 4.x 的密钥需要做兼容性验证 — 因为数据库文件还没找到
            return key

    # 策略 1: V3 特征码扫描（3.x MicroMsg.db 模式）
    print("\n  🔍 策略1: 特征码扫描(MicroMsg.db)...")
    key = extract_key_via_signature(pm, module_base, module_size)
    if key:
        return key

    # 策略 2: 全局搜索特征码（模块未知时备用）
    if module_base == 0:
        print("  🔍 策略1b: 全局特征码扫描...")
        p = scan_process_memory_global(pm, b'\\Msg\\MicroMsg.db')
        if p:
            print(f"  全局找到特征码 @ 0x{p:x}")
            fake_base = p - (p % (1024 * 1024))
            key = extract_key_via_signature(pm, fake_base, 200 * 1024 * 1024)
            if key:
                return key

    # 策略 3: Hex 字符串搜索
    print("\n  🔍 策略2: 搜索 64 位 hex 密钥...")
    key = extract_key_via_hex_search(pm, module_base, module_size)
    if key:
        return key

    # 策略 4: 公钥附近搜索
    print("\n  🔍 策略3: 公钥特征搜索...")
    key = extract_key_via_public_key_pattern(pm, module_base, module_size)
    if key:
        return key

    # 全部失败
    print("\n  ❌ 所有自动提取策略均失败")
    return None


def is_valid_hex_key(s):
    """检查是否为有效的 64 位 hex 密钥"""
    if not s or len(s) != 64:
        return False
    try:
        int(s, 16)
        return True
    except ValueError:
        return False


# 缓存数据库路径和临时副本避免重复复制
_VALIDATE_DB_CACHE = None
_VALIDATE_DB_COPY = None

def validate_key(key):
    """通过尝试解密数据库来验证密钥（同时尝试 3.x 和 4.x 数据库）
    缓存数据库路径和临时副本，避免重复复制。"""
    global _VALIDATE_DB_CACHE, _VALIDATE_DB_COPY
    if not key or len(key) != 64:
        return False

    key_bytes = bytes.fromhex(key)

    # 粗略过滤：不是全 0 或全 F，有足够的随机性
    if key_bytes == b'\x00' * 32 or key_bytes == b'\xff' * 32:
        return False
    if len(set(key_bytes)) < 4:
        return False

    # 缓存数据库路径和副本
    if _VALIDATE_DB_CACHE is None:
        _VALIDATE_DB_CACHE = find_wechat_db()
        if not _VALIDATE_DB_CACHE:
            _VALIDATE_DB_CACHE = find_wechat_db_v4(silent=True)

    if not _VALIDATE_DB_CACHE:
        return True  # 没找到数据库，暂时接受

    # 创建临时副本（只做一次）
    if _VALIDATE_DB_COPY is None:
        import tempfile, shutil
        try:
            tmp_fd, tmp_path = tempfile.mkstemp(suffix=".db")
            os.close(tmp_fd)
            shutil.copy2(_VALIDATE_DB_CACHE, tmp_path)
            _VALIDATE_DB_COPY = tmp_path
        except Exception:
            return False

    try:
        conn = sqlite3.connect(_VALIDATE_DB_COPY, timeout=1)
        for compat in [3, 4]:
            try:
                conn.execute(f"PRAGMA key = \"x'{key.hex()}'\"")
                conn.execute(f"PRAGMA cipher_compatibility = {compat}")
                conn.execute("SELECT count(*) FROM sqlite_master")
                conn.close()
                return True
            except Exception:
                continue
        conn.close()
    except Exception:
        pass
    return False


def test_decrypt_db(db_path, key):
    """快速测试密钥是否能解密数据库（尝试多种参数）"""
    for compat in [3, 4]:
        try:
            conn = sqlite3.connect(db_path)
            conn.execute(f"PRAGMA key = \"x'{key.hex()}'\"")
            conn.execute(f"PRAGMA cipher_compatibility = {compat}")
            cursor = conn.execute("SELECT count(*) FROM sqlite_master")
            cursor.fetchone()
            conn.close()
            return True
        except Exception:
            try:
                conn.close()
            except Exception:
                pass
    return False


# ========================================================================
#  第二步：查找数据库文件
# ========================================================================

def find_wechat_db():
    """自动查找微信 MSG.db 文件位置（3.x）"""
    docs_path = os.path.join(
        os.environ.get("USERPROFILE", "C:"), "Documents", "WeChat Files"
    )
    if not os.path.exists(docs_path):
        return None

    for item in os.listdir(docs_path):
        msg_db = os.path.join(docs_path, item, "Msg", "MSG.db")
        if os.path.exists(msg_db):
            print(f"  📁 找到数据库: {msg_db}")
            return msg_db

    # 搜索子目录更深入
    for item in os.listdir(docs_path):
        for root, dirs, files in os.walk(os.path.join(docs_path, item)):
            if "MSG.db" in files:
                path = os.path.join(root, "MSG.db")
                print(f"  📁 找到数据库: {path}")
                return path
            if root.count(os.sep) > 6:
                break

    return None


def find_wechat_db_v4(silent=False):
    """查找微信 4.x 数据库文件（applet.db）"""
    base = os.path.join(
        os.environ.get("USERPROFILE", "C:"),
        "AppData", "Roaming", "Tencent", "xwechat",
        "radium", "users"
    )
    if not os.path.exists(base):
        return None

    candidates = []
    for user_dir in os.listdir(base):
        applet_db = os.path.join(base, user_dir, "applet", "data", "8", "applet.db")
        if os.path.exists(applet_db):
            candidates.append(applet_db)

    if not candidates:
        return None

    # 按文件大小排序，取最大的
    candidates.sort(key=os.path.getsize, reverse=True)
    largest = candidates[0]
    if not silent:
        print(f"  📁 找到 V4 数据库: {largest} ({os.path.getsize(largest) // 1024}KB)")
        if len(candidates) > 1:
            print(f"  📁 还有 {len(candidates) - 1} 个其他用户数据库")
    return largest


# ========================================================================
#  第三步：解密并打开数据库
# ========================================================================

def open_decrypted_db(db_path, key):
    """用密钥打开解密后的数据库"""
    conn = sqlite3.connect(db_path)

    for compat in [3, 4, 2, 1]:
        try:
            conn = sqlite3.connect(db_path)
            conn.execute(f"PRAGMA key = \"x'{key.hex()}'\"")
            conn.execute(f"PRAGMA cipher_compatibility = {compat}")
            conn.execute("SELECT count(*) FROM sqlite_master")
            return conn
        except Exception:
            try:
                conn.close()
            except Exception:
                pass

    # 最后尝试：用默认参数（cipher 4 的默认值）
    try:
        conn = sqlite3.connect(db_path)
        conn.execute(f"PRAGMA key = \"x'{key.hex()}'\"")
        conn.execute("PRAGMA kdf_iter = 4000")
        conn.execute("PRAGMA cipher_hmac_algorithm = HMAC_SHA1")
        conn.execute("PRAGMA cipher_kdf_algorithm = PBKDF2_HMAC_SHA1")
        conn.execute("SELECT count(*) FROM sqlite_master")
        return conn
    except Exception:
        pass

    raise Exception("无法解密数据库，密钥可能不正确或 SQLCipher 参数不匹配")


# ========================================================================
#  第四步：导出聊天记录
# ========================================================================

def get_contacts(conn, keyword=None):
    """获取联系人列表，可选按关键词过滤"""
    try:
        cursor = conn.execute("""
            SELECT usrName, nickname, remark,
                   coalesce(remark, nickname, usrName) as display
            FROM Contact
            ORDER BY display
        """)
        contacts = []
        for row in cursor.fetchall():
            display = (row[2] or row[1] or row[0]).strip()
            if keyword and keyword.lower() not in display.lower():
                continue
            contacts.append({
                "wxid": row[0],
                "display": display,
            })
        return contacts
    except Exception as e:
        # 调试：列出所有表
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = [r[0] for r in cursor.fetchall()]
        print(f"  ⚠ Contact 表访问失败: {e}")
        print(f"  数据库中的表: {tables}")

        # 尝试备选表名
        for tbl in tables:
            if "contact" in tbl.lower():
                try:
                    cursor = conn.execute(f"SELECT * FROM [{tbl}] LIMIT 5")
                    cols = [d[0] for d in cursor.description]
                    print(f"  表 [{tbl}] 的列: {cols}")
                except Exception:
                    pass
        raise


def get_messages(conn, wxid, limit=10000):
    """获取某个联系人的聊天记录"""
    try:
        cursor = conn.execute("""
            SELECT CreateTime, StrContent, Type, IsSender
            FROM MSG
            WHERE StrTalker=? AND Type IN (1, 3, 34, 47, 49)
            ORDER BY CreateTime ASC
            LIMIT ?
        """, (wxid, limit))

        messages = []
        for row in cursor.fetchall():
            timestamp, content, msg_type, is_sender = row
            text = parse_msg_content(content or "", msg_type)
            if text:
                messages.append({
                    "time": timestamp,
                    "content": text,
                    "is_sender": is_sender,
                })
        return messages
    except Exception as e:
        print(f"  读取消息失败: {e}")
        return []


def parse_msg_content(content, msg_type):
    """解析不同类型的消息内容"""
    if msg_type == 1:      # 文本
        return content

    elif msg_type == 3:    # 图片
        # 尝试提取图片文件名
        m = re.search(r'<img\s+.*?aeskey="([^"]+)"', content, re.I)
        if m:
            return f"[图片] aeskey={m.group(1)[:8]}..."
        return "[图片]"

    elif msg_type == 34:   # 语音
        return "[语音]"

    elif msg_type == 47:   # 表情
        m = re.search(r'<emoji\s+.*?md5="([^"]+)"', content, re.I)
        if m:
            return f"[表情] {m.group(1)[:8]}..."
        return "[表情]"

    elif msg_type == 49:   # 引用/链接/红包等
        # 提取标题
        title_m = re.search(r'<title>([^<]+)', content)
        if title_m:
            return f"[分享] {title_m.group(1).strip()}"
        # 提取链接
        url_m = re.search(r'<url>([^<]+)', content)
        if url_m:
            return f"[链接] {url_m.group(1).strip()}"
        return "[链接/分享]"

    elif msg_type == 10000:  # 系统消息
        return None

    else:
        return f"[类型{msg_type}消息]"


# ========================================================================
#  导出函数
# ========================================================================

def export_to_txt(messages, output_path, contact_name):
    """导出为 TXT 格式"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"聊天记录导出 - {contact_name}\n")
        f.write(f"导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"共 {len(messages)} 条消息\n")
        f.write("=" * 60 + "\n\n")

        for msg in messages:
            t = datetime.fromtimestamp(msg["time"]).strftime("%Y-%m-%d %H:%M:%S")
            sender = "我" if msg["is_sender"] else contact_name
            f.write(f"[{t}] {sender}: {msg['content']}\n")

    return True


def export_to_pdf(messages, output_path, contact_name):
    """导出为 PDF 格式（含中文支持）"""
    if FPDF is None:
        return False

    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=20)

    # 标题
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, f"Chat: {contact_name}", ln=True)
    pdf.set_font("Helvetica", "", 8)
    pdf.cell(
        0, 5,
        f"Exported: {datetime.now().strftime('%Y-%m-%d %H:%M')}  |  "
        f"{len(messages)} messages",
        ln=True
    )
    pdf.ln(5)

    # 尝试加载中文字体
    chinese_fonts = [
        ("C:/Windows/Fonts/msyh.ttc",  "微软雅黑"),
        ("C:/Windows/Fonts/msyhbd.ttc", "微软雅黑粗体"),
        ("C:/Windows/Fonts/simhei.ttf", "黑体"),
        ("C:/Windows/Fonts/simsun.ttc", "宋体"),
        ("C:/Windows/Fonts/yahei.ttf",  "雅黑"),
        ("C:/Windows/Fonts/msjhl.ttc",  "微软雅黑Light"),
    ]

    font_loaded = False
    for font_path, font_name in chinese_fonts:
        if os.path.exists(font_path):
            try:
                pdf.add_font("zh", "", font_path, uni=True)
                font_loaded = True
                break
            except Exception:
                continue

    for msg in messages:
        t = datetime.fromtimestamp(msg["time"]).strftime("%m-%d %H:%M")
        sender = "我" if msg["is_sender"] else contact_name
        text = f"[{t}] {sender}: {msg['content']}"

        if font_loaded:
            pdf.set_font("zh", "", 9)
            pdf.multi_cell(0, 5.5, text)
        else:
            # 备用：只输出 ASCII
            pdf.set_font("Courier", "", 9)
            ascii_text = text.encode("ascii", errors="replace").decode("ascii")
            pdf.multi_cell(0, 5, ascii_text)

    pdf.output(output_path)
    return True


# ========================================================================
#  主流程
# ========================================================================

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="微信聊天记录导出工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python wechat_exporter.py                          # 导出所有联系人的聊天记录
  python wechat_exporter.py --contact 张三           # 只导出"张三"
  python wechat_exporter.py --format pdf             # 只导出 PDF
  python wechat_exporter.py --limit 5000             # 每个联系人最多 5000 条
  python wechat_exporter.py --max-contacts 10        # 只导出前 10 个联系人
  python wechat_exporter.py --output D:\\备份         # 指定输出目录
        """,
    )
    parser.add_argument(
        "--contact", "-c", type=str, default=None,
        help="按姓名/备注过滤联系人（支持模糊匹配）"
    )
    parser.add_argument(
        "--format", "-f", type=str, default="both",
        choices=["txt", "pdf", "both"],
        help="导出格式（默认 both）"
    )
    parser.add_argument(
        "--limit", "-l", type=int, default=MSG_LIMIT_DEFAULT,
        help=f"每个联系人的最大消息数（默认 {MSG_LIMIT_DEFAULT}）"
    )
    parser.add_argument(
        "--output", "-o", type=str, default=None,
        help=f"输出目录（默认: {OUTPUT_DIR}）"
    )
    parser.add_argument(
        "--max-contacts", "-m", type=int, default=MAX_CONTACTS_DEFAULT,
        help="最大联系人导出数，0 为无限制（默认 0）"
    )
    parser.add_argument(
        "--no-pdf", action="store_true",
        help="不导出 PDF（等同于 --format txt）"
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # 输出目录
    output_dir = args.output or OUTPUT_DIR
    os.makedirs(output_dir, exist_ok=True)
    export_format = "txt" if args.no_pdf else args.format

    print("=" * 60)
    print("  微信聊天记录导出工具")
    print("=" * 60)
    print(f"  输出目录: {output_dir}")
    if args.contact:
        print(f"  联系人过滤: {args.contact}")
    print(f"  格式: {export_format}")
    print()

    # ---- 第一步：提取密钥 ----
    print("【第一步】提取微信数据库密钥")
    print("-" * 40)
    pm, _ = get_wechat_process()

    key_hex = read_key_from_memory(pm)
    if not key_hex:
        print()
        print("  ⚠ 自动提取失败，需要手动输入密钥")
        print("  (参考: 可用 Cheat Engine 或其他内存查看工具搜索 64 位 hex 字符串)")
        key_hex = input("  请输入 64 位 hex 密钥: ").strip()
        if not is_valid_hex_key(key_hex):
            print("  ❌ 无效的密钥格式（需要 64 位十六进制字符串）")
            return

    key = bytes.fromhex(key_hex)
    print(f"  ✅ 密钥: {key_hex[:8]}...{key_hex[-8:]}")

    # ---- 第二步：查找数据库 ----
    print()
    print("【第二步】查找微信数据库")
    print("-" * 40)

    # 先找 3.x 数据库，再找 4.x 数据库
    db_path = find_wechat_db()
    is_v4 = False
    if not db_path:
        db_path = find_wechat_db_v4()
        if db_path:
            is_v4 = True

    if not db_path:
        print("  ❌ 未找到微信数据库")
        print("  请确认:")
        print("  1. 微信已登录")
        print("  2. 聊天记录已同步")
        print("  3. 检查 Documents/WeChat Files/ 或 AppData/Roaming/Tencent/xwechat/ 目录是否存在")
        return

    # ---- 第三步：解密数据库 ----
    print()
    print("【第三步】解密数据库")
    print("-" * 40)
    conn = open_decrypted_db(db_path, key)
    print("  ✅ 数据库解密成功")

    # 如果是 4.x，先看一下表结构
    if is_v4:
        print()
        print("【3.x → 4.x 适配】检查数据库表结构")
        print("-" * 40)
        cursor = conn.execute(
            "SELECT name, type FROM sqlite_master WHERE type IN ('table','view') ORDER BY type, name"
        )
        tables = cursor.fetchall()
        print(f"  数据库中的表/视图 ({len(tables)} 个):")
        for name, tbl_type in tables:
            # 读取每个表的前 3 行列名
            try:
                c2 = conn.execute(f"SELECT * FROM [{name}] LIMIT 1")
                cols = [d[0] for d in c2.description]
                print(f"    📊 {name:30s}  ({', '.join(cols[:8])}{'...' if len(cols) > 8 else ''})")
            except Exception:
                print(f"    📊 {name}  (无法读取)")
        print()
        print("  ⚠ [4.x] 数据库已解密，但导出逻辑尚未适配 4.x 的表结构")
        print("  后续工作：分析上述表结构 → 找到聊天记录和联系人表 → 改写 query")
        conn.close()
        return

    # ---- 第四步：获取联系人（3.x） ----
    print(f"  ✅ 共 {len(contacts)} 个联系人" +
          (f" (关键词: {args.contact})" if args.contact else ""))

    if not contacts:
        print("  ⚠ 没有找到联系人")
        return

    # ---- 第五步：导出 ----
    print()
    print("【第五步】开始导出聊天记录")
    print("-" * 40)

    exported = 0
    max_contacts = args.max_contacts or len(contacts)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for idx, contact in enumerate(contacts):
        if exported >= max_contacts:
            print(f"\n  ⚠ 已达到最大导出数限制 ({max_contacts})")
            break

        wxid = contact["wxid"]
        name = contact["display"]

        # 跳过公众号/服务号
        if wxid.startswith("gh_") or wxid.startswith("weixin"):
            continue

        # 安全文件名
        safe = re.sub(r'[\\/:*?"<>|]', "_", name).strip()
        safe = safe[:80] or f"contact_{wxid[-8:]}"

        # 获取消息
        messages = get_messages(conn, wxid, limit=args.limit)

        status_msg = f"  [{idx+1}/{len(contacts)}] {name}"
        if not messages:
            print(f"{status_msg}  无消息")
            continue

        print(f"{status_msg}  {len(messages)} 条消息", end="", flush=True)

        # 导出 TXT
        txt_ok = pdf_ok = False
        if export_format in ("txt", "both"):
            txt_path = os.path.join(output_dir, f"{safe}.txt")
            txt_ok = export_to_txt(messages, txt_path, name)

        # 导出 PDF
        if export_format in ("pdf", "both"):
            pdf_path = os.path.join(output_dir, f"{safe}.pdf")
            pdf_ok = export_to_pdf(messages, pdf_path, name)

        # 显示结果
        if export_format == "both":
            print(f"  TXT={'✅' if txt_ok else '❌'} PDF={'✅' if pdf_ok else '❌'}")
        else:
            print(f"  ✅")

        exported += 1

    conn.close()

    # ---- 完成 ----
    print()
    print("=" * 60)
    print(f"  ✅ 导出完成！共导出 {exported} 个联系人")
    print(f"  📁 文件位置: {os.path.abspath(output_dir)}")
    print(f"  🕐 导出时间: {now_str}")
    print("=" * 60)


if __name__ == "__main__":
    main()
