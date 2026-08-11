# -*- coding: utf-8 -*-
"""从微信消息中提取图片 MD5 和 AES Key"""
import re


def parse_image_info(msg: dict) -> dict:
    """返回 {md5, aeskey, dat_name, alt_md5}
    md5 = 来自 packed_info_data (用于找 .dat 文件)
    alt_md5 = 来自 XML 的 md5 属性 (备选)
    aeskey = 来自 XML 的 aeskey 属性 (用于 V4 解密)
    """
    result = {'md5': '', 'aeskey': '', 'dat_name': '', 'alt_md5': ''}
    content = msg.get('message_content', '') or ''
    packed = msg.get('packed_info_data', '') or ''

    # 1. 优先从 packed_info_data 提取 md5 (这是 .dat 文件名)
    if packed:
        md5 = _binary_extract_md5(packed)
        if md5:
            result['md5'] = md5
            result['dat_name'] = md5 + '.dat'

    # 2. 从 XML 提取 aeskey + alt_md5
    if content:
        info = _xml_extract(content)
        result['aeskey'] = info.get('aeskey', '')
        if info.get('md5'):
            result['alt_md5'] = info['md5']
        # 如果 packed 没拿到 dat_name, 从 xml 拿
        if not result['dat_name'] and info.get('dat_name'):
            result['dat_name'] = info['dat_name']

    return result


def _xml_extract(content: str) -> dict:
    r = {'md5': '', 'aeskey': '', 'dat_name': ''}
    m = re.search(r'aeskey\s*=\s*["\']([a-fA-F0-9]{32})["\']', content)
    if m: r['aeskey'] = m.group(1).lower()
    m = re.search(r'<img[^>]*\smd5\s*=\s*["\']([a-fA-F0-9]{32})["\']', content)
    if m: r['md5'] = m.group(1).lower()
    # 如果有 md5，dat_name = md5 + .dat
    if r['md5']: r['dat_name'] = r['md5'] + '.dat'
    return r


def _binary_extract_md5(packed) -> str:
    if isinstance(packed, str):
        try: data = bytes.fromhex(packed)
        except: return ''
    else:
        data = packed
    if not isinstance(data, (bytes, bytearray)):
        return ''
    s = ''.join(chr(b) if 32 <= b <= 126 else ' ' for b in data)
    m = re.search(r'([a-fA-F0-9]{32})', s)
    if m: return m.group(1).lower()
    return ''
