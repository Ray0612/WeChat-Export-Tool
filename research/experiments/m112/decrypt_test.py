# -*- coding: utf-8 -*-
"""
尝试用 key_info_data 解密 message_0.db
SQLCipher: AES-256-CBC, PBKDF2-HMAC-SHA1 (64000 iter), page=4096
"""
import hashlib, hmac, struct, os
from Crypto.Cipher import AES

DB_PATH = 'D:/储存信息/xwechat_files/wxid_caccoealsdbj12_e8c8/db_storage/message/message_0.db'

def read_first_page(path):
    with open(path, 'rb') as f:
        return f.read(4096)

def derive_sqlcipher_key(password, salt=b''):
    """Derive 64-byte SQLCipher key: first 32 = enc key, second 32 = HMAC key"""
    return hashlib.pbkdf2_hmac('sha1', password, salt, 64000, dkLen=64)

def sqlcipher_iv(hmac_key, page_num):
    """SQLCipher IV for page N: HMAC(hmac_key, page_num)[:16]"""
    return hmac.new(hmac_key, struct.pack('>I', page_num) + b'\x00' * 12, hashlib.sha1).digest()[:16]

def try_decrypt(name, passphrase, salt=b'', page=1):
    """Try decrypt page N of message_0.db with given passphrase and salt"""
    try:
        full_key = derive_sqlcipher_key(passphrase, salt)
        enc_key = full_key[:32]
        hmac_key = full_key[32:64]

        with open(DB_PATH, 'rb') as f:
            f.seek((page - 1) * 4096)
            page_data = f.read(4096)

        iv = sqlcipher_iv(hmac_key, page)
        cipher = AES.new(enc_key, AES.MODE_CBC, iv=iv)
        decrypted = cipher.decrypt(page_data)

        if decrypted[:16] == b'SQLite format 3\x00':
            print(f'  ✅ {name}: SUCCESS!')
            print(f'     Header: {decrypted[:20]}')
            return True
        elif any(32 <= b < 127 for b in decrypted[:32]) and b'SQLite' not in decrypted[:64]:
            # Might be partially correct
            return False
        return False
    except Exception as e:
        print(f'  ❌ {name}: {e}')
        return False

first_page = read_first_page(DB_PATH)
print(f'message_0.db: {os.path.getsize(DB_PATH)} bytes')
print(f'Page 1 header: {first_page[:16].hex()}')
print()

# ── key_info_data ──
key_info_data = bytes.fromhex(
    '0aa801000bb51739050000010000000000b0468bb634a652e74c623d4b2a6a2000'
    '00006eb001aa1e57b69370d0718d0f53e0fd67218df5ca9332e86459665dacf4'
    '4fe9545379761da12d34d5648c45a7583ceecef8df7ae8950da60a5607d8ba58'
    '6f0bb993a5b49260eeebbbe833575555784625872134f7c89129f76eafd5dbe3'
    '05e84cc150ebb737d27cb9f11ea2cc6671065dfdea10ced40b72bd0638deec42'
    'c4227fd41940d8ee4ab010e80f18bd96a9d106'
)

print('=== 1. key_info_data as passphrase ===')
passwords = [
    (key_info_data, ''),
    (key_info_data, b'salt'),
    (key_info_data, b'wxid_caccoealsdbj12'),
    (key_info_data[:32], b''),
    (key_info_data[16:48], b''),
    (key_info_data[-32:], b''),
]
for pw, salt in passwords:
    name = f'pw={pw[:16].hex()}..., salt={salt[:8].hex() if salt else "empty"}'
    if try_decrypt(name, pw, salt):
        break

print()
print('=== 2. wxid-based keys ===')
passwords2 = [
    (b'wxid_caccoealsdbj12', b''),
    (b'wxid_caccoealsdbj12', b'salt'),
    (hashlib.md5(b'wxid_caccoealsdbj12').digest(), b''),
    (hashlib.sha256(b'wxid_caccoealsdbj12').digest(), b''),
]
for pw, salt in passwords2:
    name = f'wxid-derived: {pw[:16].hex()}..., salt={salt[:8].hex() if salt else "empty"}'
    if try_decrypt(name, pw, salt):
        break

print()
print('=== 3. Hash of key_info_data ===')
hashes = [
    hashlib.sha256(key_info_data).digest(),
    hashlib.sha256(key_info_data + b'wxid_caccoealsdbj12').digest(),
    hashlib.md5(key_info_data).digest(),
]
for h in hashes:
    name = f'SHA256={h[:16].hex()}...'
    if try_decrypt(name, h):
        break

print()
print('All approaches exhausted.')
print('Key derivation not found through simple methods.')
print('Need to hook sqlite3_key_v2 at runtime.')
