"""
阶段 2b：从配置文件中提取 UIN 等密钥派生参数
"""
import os, struct, re

def search_uin(config_dir):
    """搜索配置目录中的 UIN 值"""
    findings = []

    for root, dirs, files in os.walk(config_dir):
        for fname in files:
            path = os.path.join(root, fname)
            if fname.endswith('.crc'):
                continue
            try:
                data = open(path, 'rb').read()
            except:
                continue

            # 方法 1：搜索字符串 "uin" 附近的值
            text = data.decode('utf-8', errors='replace')
            for m in re.finditer(r'[Uu][Ii][Nn]\s*[:=]\s*(\d{4,15})', text):
                findings.append(('uin_string', m.group(1), path))

            # 方法 2：搜索 32-bit 整数范围在 UIN 区间的
            for i in range(0, len(data)-4, 4):
                val = struct.unpack('<I', data[i:i+4])[0]
                if 100000 < val < 999999999:
                    # Check if "uin" is nearby
                    nearby = data[max(0,i-16):i+16].lower()
                    if b'uin' in nearby:
                        findings.append(('uin_int32', str(val), path))

            # 方法 3：搜索可能的 wxid + 数字组合
            for m in re.finditer(rb'wxid_[a-zA-Z0-9_]+', data):
                findings.append(('wxid', m.group().decode(), path))

    return findings

def search_key_candidates(config_dir):
    """在配置文件中搜索所有可能的密钥派生材料"""
    results = {'wxsid': [], 'wxuin': [], 'wxid': [], 'device': []}

    for root, dirs, files in os.walk(config_dir):
        for fname in files:
            path = os.path.join(root, fname)
            try:
                data = open(path, 'rb').read()
            except:
                continue

            text = data.decode('utf-8', errors='replace')

            for key, patterns in [('wxsid', [r'wxsid[\s:="\']+([a-zA-Z0-9]+)']),
                                   ('wxuin', [r'wxuin[\s:="\']+(\d+)']),
                                   ('wxid', [r'wxid_[a-zA-Z0-9_]+']),
                                   ('device', [r'device[\s:="\']+([a-zA-Z0-9_\-]+)'])]:
                for pat in patterns:
                    for m in re.finditer(pat, text, re.IGNORECASE):
                        results[key].append((m.group(1), path))

    return results

def extract_uin_from_login(data):
    """从 login_config 或 login_configv2 中提取 UIN"""
    # 这些文件通常是 protobuf 格式，尝试定位 UIN
    # UIN 在 protobuf 中通常以 varint 编码
    uins = set()
    i = 0
    while i < len(data) - 8:
        # Varint 解码
        if data[i] & 0x80 == 0:
            val = data[i]
            # UIN 通常在 1000000 ~ 999999999 范围
            if 1000000 < val < 999999999:
                uins.add(val)
            i += 1
        else:
            # Multi-byte varint
            val = 0
            shift = 0
            while i < len(data) and data[i] & 0x80:
                val |= (data[i] & 0x7f) << shift
                shift += 7
                i += 1
            if i < len(data):
                val |= data[i] << shift
                i += 1
            if 1000000 < val < 999999999:
                uins.add(val)
    return sorted(uins)
