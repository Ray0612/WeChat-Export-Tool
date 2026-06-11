"""
阶段 2：密钥尝试模块
支持多种策略尝试解密 message_0.db

用法:
    from db_exporter.unlock import try_keys
    result = try_keys('message_0.db')
    if result['success']:
        print(f"Key found: {result['key']}")
"""
import hashlib, os, json
from hashlib import pbkdf2_hmac
from Crypto.Cipher import AES
import struct, datetime

# SQLCipher 3.x default config
SQLCIPHER3 = {
    'kdf_algorithm': 'sha1',
    'kdf_iter': 64000,
    'key_length': 32,
    'page_size': 4096,
}

def _derive_keys(password, salt):
    """PBKDF2-HMAC-SHA1 as used by DeriveKeyPbkdf2HmacSha1 (confirmed)"""
    dk = pbkdf2_hmac('sha1', password, salt, SQLCIPHER3['kdf_iter'],
                     dklen=SQLCIPHER3['key_length'] * 2)
    return dk[:32], dk[32:]  # enc_key, hmac_key

def _try_key(db_first_page, password, salt):
    """Try a password/key against the first page of message_0.db"""
    for cfg_salt in [salt, b'']:
        enc_key, hmac_key = _derive_keys(password, cfg_salt)
        # SQLCipher 3: IV = HMAC(page_number, hmac_key)[:16]
        iv = hashlib.pbkdf2_hmac('sha1', struct.pack('>I', 1), hmac_key, 1, 16)
        try:
            cipher = AES.new(enc_key, AES.MODE_CBC, iv)
            decrypted = cipher.decrypt(db_first_page[:4096])
            if decrypted[:15] == b'SQLite format 3':
                return {
                    'success': True,
                    'password': password if isinstance(password, str) else password.hex(),
                    'enc_key': enc_key.hex(),
                    'salt': cfg_salt.hex() if cfg_salt else '(none)',
                }
        except:
            pass
    return {'success': False}

def try_key(db_path, password):
    """Try a single password/key against the database"""
    with open(db_path, 'rb') as f:
        first_page = f.read(4096)
    return _try_key(first_page, password, first_page[:16])

def try_keys(db_path, candidate_keys):
    """Try multiple candidate keys"""
    with open(db_path, 'rb') as f:
        first_page = f.read(4096)

    for key in candidate_keys:
        if isinstance(key, str):
            # Try as hex string
            try:
                key_bytes = bytes.fromhex(key)
            except:
                key_bytes = key.encode('utf-8')
        else:
            key_bytes = key

        result = _try_key(first_page, key_bytes, first_page[:16])
        if result['success']:
            return result

    return {'success': False}

# Common candidate derivation strategies
def derive_from_uin(db_path, uin):
    """Derive key from UIN (as in WeChat 3.x)"""
    uin_bytes = str(uin).encode('utf-8')
    # Try various salt combinations
    for salt_prefix in [b'', b'salt', b'wechat', b'message']:
        result = try_key(db_path, uin_bytes + salt_prefix)
        if result['success']:
            return result
    return {'success': False}

def derive_from_wxid(db_path, wxid):
    """Try deriving from wxid (the account ID)"""
    wxid_bytes = wxid.encode('utf-8')
    for suffix in [b'', b'_key', b'_db', b'_encrypt']:
        result = try_key(db_path, wxid_bytes + suffix)
        if result['success']:
            return result
    return {'success': False}
