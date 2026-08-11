# -*- coding: utf-8 -*-
""".dat 图片解密 — V3 XOR / V4 AES+XOR"""
import struct
from Crypto.Cipher import AES

V1_MAGIC = bytes([0x07, 0x08, 0x56, 0x31, 0x08, 0x07])
V2_MAGIC = bytes([0x07, 0x08, 0x56, 0x32, 0x08, 0x07])


def decrypt_dat(filepath: str, xor_key: int = 0, aes_key: str = "") -> tuple:
    """解密 .dat 文件 → 返回 (ext, bytes)
    1. 检测 magic bytes (大部分 .dat 根本没加密)
    2. V4: AES-128-ECB + XOR
    3. V3: 纯 XOR (默认 key=0)
    """
    with open(filepath, 'rb') as f:
        data = f.read()
    if len(data) < 4:
        raise ValueError("文件太小")

    ext = _detect_ext(data)
    if ext:
        return (ext, data)

    version = _get_version(data)
    results = []

    if version == 2 and len(aes_key) >= 16:
        try:
            key_bytes = aes_key.encode('ascii', errors='replace')[:16].ljust(16, b'\x00')
            results.append(_decrypt_v4(data, xor_key, key_bytes))
        except Exception:
            pass

    if version != 2:
        results.append(_xor(data, xor_key))

    # 4. 检测结果
    for dec in results:
        dec = _unwrap_wxgf(dec)
        ext = _detect_ext(dec)
        if ext:
            return (ext, dec)

    raise ValueError("无法识别图片格式")


def _get_version(data: bytes) -> int:
    if len(data) < 6: return 0
    if data[:6] == V1_MAGIC: return 1
    if data[:6] == V2_MAGIC: return 2
    return 0


def _detect_ext(data: bytes) -> str:
    if len(data) < 12: return ""
    if data[0] == 0xFF and data[1] == 0xD8 and data[2] == 0xFF: return 'jpg'
    if data[0] == 0x89 and data[1] == 0x50 and data[2] == 0x4E and data[3] == 0x47: return 'png'
    if data[0] == 0x47 and data[1] == 0x49 and data[2] == 0x46: return 'gif'
    if (data[0] == 0x52 and data[1] == 0x49 and data[2] == 0x46 and data[3] == 0x46
            and data[8] == 0x57 and data[9] == 0x45 and data[10] == 0x42 and data[11] == 0x50): return 'webp'
    if data[0] == 0x42 and data[1] == 0x4D: return 'bmp'
    return ""


def _xor(data: bytes, key: int) -> bytes:
    return bytes(b ^ key for b in data)


def _decrypt_v4(data: bytes, xor_key: int, key_bytes: bytes) -> bytes:
    if len(data) < 15: raise ValueError("V4 文件太小")
    body = data[15:]
    aes_size = struct.unpack_from('<I', data, 6)[0]
    xor_size = struct.unpack_from('<I', data, 10)[0]
    padded_aes = aes_size + (16 - (aes_size % 16 + 16) % 16)
    if padded_aes > len(body): raise ValueError("无效 aes_size")

    aes_block = body[:padded_aes]
    aes_dec = b''
    if len(aes_block) > 0:
        cipher = AES.new(key_bytes, AES.MODE_ECB)
        aes_dec = _remove_pkcs7(cipher.decrypt(aes_block))

    rest = body[padded_aes:]
    raw = rest[:len(rest) - xor_size] if xor_size > 0 else rest
    xor_block = bytes(b ^ xor_key for b in rest[len(rest) - xor_size:]) if xor_size > 0 else b''
    return aes_dec + raw + xor_block


def _remove_pkcs7(data: bytes) -> bytes:
    if len(data) == 0: raise ValueError("空数据")
    pad = data[-1]
    if pad <= 0 or pad > 16 or pad > len(data): raise ValueError("无效 padding")
    return data[:len(data) - pad]


def _unwrap_wxgf(data: bytes) -> bytes:
    if len(data) < 4 or data[:4] != b'WXGF': return data
    for offset in range(16, min(len(data), 1024)):
        if _detect_ext(data[offset:]): return data[offset:]
    return data
