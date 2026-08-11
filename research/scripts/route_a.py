# -*- coding: utf-8 -*-
"""
路线 A — WeFlow 原理 Python 实现
流程: 关微信 → 注入 hook → 开微信登录 → 自动捕获 key → 解密数据库 → 导出
"""
import ctypes, json, os, sys, time, subprocess
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ROOT = r'C:\Users\OK\Desktop\wechat_v4_export_research'
WX_KEY = r'C:\Users\OK\AppData\Local\Programs\WeFlow\resources\resources\key\win32\x64\wx_key.dll'
WCDB_DIR = r'C:\Users\OK\AppData\Local\Programs\WeFlow\resources\resources\wcdb\win32\x64'
OUT = r'C:\Users\OK\Desktop\wx_export'
os.makedirs(OUT, exist_ok=True)

# ═══════════════════════════════════════
# 第一步: 提取 Key (仿 WeFlow)
# ═══════════════════════════════════════

def extract_key():
    """等待微信启动 → 注入 hook → 捕获 key"""
    print('[1] 请确保微信已关闭')
    input('   按 Enter 开始监控微信启动...\n')

    dll = ctypes.CDLL(WX_KEY)
    dll.InitializeHook.argtypes = [ctypes.c_uint32]
    dll.InitializeHook.restype = ctypes.c_bool
    dll.PollKeyData.argtypes = [ctypes.c_char_p, ctypes.c_int]
    dll.PollKeyData.restype = ctypes.c_bool
    dll.CleanupHook.argtypes = []
    dll.CleanupHook.restype = ctypes.c_bool
    dll.GetLastErrorMsg.restype = ctypes.c_char_p

    print('[2] 请打开微信并登录，正在监听...\n')
    while True:
        pid = None
        try:
            r = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq Weixin.exe', '/FO', 'CSV', '/NH'],
                             capture_output=True, text=True, timeout=5)
            for line in r.stdout.strip().split('\n'):
                if 'Weixin.exe' in line:
                    pid = int(line.split('","')[1].strip('"'))
                    break
        except: pass

        if pid:
            print(f'  检测到微信 PID: {pid}，注入 hook...')
            if dll.InitializeHook(pid):
                print('  [+] hook 注入成功，捕获 key...')
                buf = ctypes.create_string_buffer(128)
                t0 = time.time()
                while time.time() - t0 < 60:
                    if dll.PollKeyData(buf, 128):
                        key = buf.value.decode('ascii')
                        if len(key) == 64:
                            print(f'\n  ✅ Key: {key}')
                            dll.CleanupHook()
                            return key
                    time.sleep(0.1)
                print('  [-] 未捕获到 key（可能 hook 晚了）')
                dll.CleanupHook()
            else:
                err = dll.GetLastErrorMsg()
                print(f'  [-] hook 失败: {err.decode("utf-8","replace") if err else "未知"}')
        time.sleep(1)

# ═══════════════════════════════════════
# 第二步: 解密数据库 (仿 WeFlow WCDB API)
# ═══════════════════════════════════════

class WCDB:
    def __init__(self):
        cwd = os.getcwd()
        os.chdir(WCDB_DIR)
        self.api = ctypes.CDLL(os.path.join(WCDB_DIR, 'wcdb_api.dll'))
        os.chdir(cwd)
        self._bind()
        self.handle = ctypes.c_int64(0)

    def _bind(self):
        self.api.wcdb_init.restype = ctypes.c_int32
        self.api.wcdb_open_account.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.POINTER(ctypes.c_int64)]
        self.api.wcdb_open_account.restype = ctypes.c_int32
        self.api.wcdb_close_account.argtypes = [ctypes.c_int64]
        self.api.wcdb_close_account.restype = ctypes.c_int32
        self.api.wcdb_get_sessions.argtypes = [ctypes.c_int64, ctypes.POINTER(ctypes.c_void_p)]
        self.api.wcdb_get_sessions.restype = ctypes.c_int32
        self.api.wcdb_get_messages.argtypes = [ctypes.c_int64, ctypes.c_char_p, ctypes.c_int32, ctypes.c_int32, ctypes.POINTER(ctypes.c_void_p)]
        self.api.wcdb_get_messages.restype = ctypes.c_int32
        self.api.wcdb_free_string.argtypes = [ctypes.c_void_p]

    def init(self):
        return self.api.wcdb_init() == 0

    def open(self, path, key):
        r = self.api.wcdb_open_account(path.encode('utf-8'), key.encode('ascii'), ctypes.byref(self.handle))
        return r == 0

    def _read_json(self, out):
        js = ctypes.cast(out, ctypes.c_char_p).value
        self.api.wcdb_free_string(out)
        return json.loads(js.decode('utf-8')) if js else None

    def get_sessions(self):
        out = ctypes.c_void_p(0)
        if self.api.wcdb_get_sessions(self.handle, ctypes.byref(out)) != 0: return None
        return self._read_json(out)

    def get_messages(self, username, limit=500, offset=0):
        out = ctypes.c_void_p(0)
        if self.api.wcdb_get_messages(self.handle, username.encode('utf-8'), limit, offset, ctypes.byref(out)) != 0: return None
        return self._read_json(out)

    def close(self):
        if self.handle.value:
            self.api.wcdb_close_account(self.handle)

# ═══════════════════════════════════════
# 主流程
# ═══════════════════════════════════════

def main():
    if not ctypes.windll.shell32.IsUserAnAdmin():
        print('需要管理员权限!')
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, f'"{__file__}"', None, 1)
        return

    # 1. 提取 key
    key = extract_key()
    if not key:
        input('\n失败，按 Enter 退出')
        return

    # 2. 解密数据库
    print('\n[3] 初始化 WCDB...')
    db = WCDB()
    if not db.init():
        print('[-] WCDB 初始化失败')
        return

    session_db = None
    for root, dirs, files in os.walk(r'D:\储存信息\xwechat_files\wxid_caccoealsdbj12_e8c8\db_storage'):
        if 'session.db' in files and 'wal' not in root:
            session_db = os.path.join(root, 'session.db')
            break

    if not session_db:
        print('[-] 找不到 session.db')
        return

    print(f'[4] 打开数据库...')
    if not db.open(session_db, key):
        print('[-] 数据库打开失败')
        return
    print('  ✅ 数据库解密成功')

    # 3. 获取会话列表
    print('\n[5] 会话列表:')
    sessions = db.get_sessions() or []
    for s in sessions[:30]:
        name = s.get('username', '?')
        cnt = s.get('messageCount', s.get('count', 0))
        print(f'  {str(name)[:30]:30s} {cnt} 条')
    print(f'  共 {len(sessions)} 个会话')

    # 4. 导出第一个会话
    if sessions:
        first = sessions[0]
        name = first.get('username', '')
        print(f'\n[6] 导出: {name}')
        msgs = db.get_messages(name, 200, 0)
        if msgs:
            print(f'  共 {len(msgs)} 条')
            path = os.path.join(OUT, f'export_{int(time.time())}.json')
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(msgs, f, ensure_ascii=False, indent=2)
            print(f'  已保存: {path}')
            for m in msgs[:5]:
                print(f'  [{m.get("createTime","")}] {str(m.get("msgContent",""))[:60]}')

    db.close()
    print('\n✅ 完成!')

if __name__ == '__main__':
    main()
