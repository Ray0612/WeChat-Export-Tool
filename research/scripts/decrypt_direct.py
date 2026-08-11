# -*- coding: utf-8 -*-
"""
直接用 key 解密 SQLCipher V4 数据库
不依赖 WCDB.dll，纯 Python + pycryptodome
"""
import hashlib, hmac, struct, json, os, time
from Crypto.Cipher import AES

OUT = r'C:\Users\OK\Desktop\wx_export'
os.makedirs(OUT, exist_ok=True)

def decrypt_db(key_hex, db_path):
    """全量解密 SQLCipher V4 数据库 (EchoTrace 算法)"""
    key = bytes.fromhex(key_hex)
    size = os.path.getsize(db_path)
    num = size // 4096
    PAGE_SZ = 4096
    SALT_SZ = 16
    IV_SZ = 16
    HMAC_SZ = 64
    RESERVE = (IV_SZ + HMAC_SZ + 15) // 16 * 16  # 80

    print(f'  {os.path.basename(db_path)} ({size//1024}KB, {num} 页)')

    with open(db_path, 'rb') as f:
        blist = f.read()

    # 数据库全局 salt 来自第一页
    salt = blist[:SALT_SZ]

    # 派生全局密钥
    enc_key = hashlib.pbkdf2_hmac('sha512', key, salt, 256000, dklen=32)
    mac_salt = bytes(b ^ 0x3a for b in salt)
    mac_key = hashlib.pbkdf2_hmac('sha512', enc_key, mac_salt, 2, dklen=32)

    result = bytearray()
    # 第一页: SQLite header + 解密数据(去除salt和reserve)
    page0 = blist[0:PAGE_SZ]
    iv0 = page0[-RESERVE:][:IV_SZ]
    enc0 = page0[SALT_SZ:PAGE_SZ - RESERVE]
    dec0 = AES.new(enc_key, AES.MODE_CBC, iv=iv0).decrypt(enc0)
    result.extend(b'SQLite format 3\x00')
    result.extend(dec0[16:])  # 跳过 salt(前16字节已在 SQLite header 中)

    t0 = time.time()
    for i in range(1, num):  # 从第二页开始
        off = i * PAGE_SZ
        page = blist[off:off + PAGE_SZ]
        if len(page) < PAGE_SZ: break

        iv = page[-RESERVE:][:IV_SZ]
        encrypted = page[SALT_SZ:PAGE_SZ - RESERVE]
        dec = AES.new(enc_key, AES.MODE_CBC, iv=iv).decrypt(encrypted)
        result.extend(dec)

        if (i + 1) % 50 == 0:
            elapsed = time.time() - t0
            print(f'    第 {i+1}/{num} 页 ({elapsed:.1f}s)', end='\r')
    print(f'    完成 ({time.time()-t0:.1f}s)')
    return bytes(result)

def query_db(decrypted_data, sql):
    """对解密后的数据执行 SQL 查询"""
    import sqlite3
    tmp = os.path.join(OUT, '_tmp_decrypted.db')
    with open(tmp, 'wb') as f:
        f.write(decrypted_data)
    conn = sqlite3.connect(tmp)
    cur = conn.cursor()
    cur.execute(sql)
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description]
    conn.close()
    os.remove(tmp)
    return cols, rows

def main():
    key_file = os.path.join(OUT, 'key.txt')
    if not os.path.exists(key_file):
        print('[-] key.txt 不存在，请先获取密钥')
        return
    key = open(key_file).read().strip()
    print(f'[+] Key: {key[:16]}...')
    print()

    # 找 session.db
    base = r'D:\wxxinxi\xwechat_files'
    sdb = None
    for root, dirs, files in os.walk(base):
        if 'session.db' in files and 'wal' not in root:
            sdb = os.path.join(root, 'session.db')
            break
    if not sdb:
        print('[-] 找不到 session.db')
        return

    print('[1] 解密 session.db...')
    data = decrypt_db(key, sdb)

    print('\n[2] 查询会话列表...')
    cols, rows = query_db(data, 'SELECT username, sort_timestamp FROM SessionTable ORDER BY sort_timestamp DESC LIMIT 20')
    print(f'  共 {len(rows)} 个会话:')
    for r in rows[:10]:
        print(f'    {str(r[0])[:35]:35s} {r[1]}')

    print('\n[3] 解密 message_0.db...')
    msg0 = os.path.join(os.path.dirname(sdb), 'message', 'message_0.db')
    if os.path.exists(msg0):
        data0 = decrypt_db(key, msg0)
        cols2, rows2 = query_db(data0, "SELECT name FROM sqlite_master WHERE type='table' LIMIT 10")
        print(f'  表: {[r[0] for r in rows2]}')

    print('\n✅ 解密成功! key 正确可用')

if __name__ == '__main__':
    main()
