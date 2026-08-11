# -*- coding: utf-8 -*-
"""微信聊天记录本地导出工具 v1.2.0"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os, sys, threading, time, datetime, json, ctypes, shutil, re

if getattr(sys, 'frozen', False):
    BASE = os.path.dirname(sys.executable)
else:
    BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, 'scripts'))
sys.path.insert(0, os.path.join(BASE, 'exporters'))
if sys.stdout: sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ROOT = BASE
OUT = os.path.join(os.environ.get('USERPROFILE', BASE), 'Desktop', 'wx_export')
KEY_FILE = os.path.join(OUT, 'key.txt')
os.makedirs(OUT, exist_ok=True)
# 启动时尝试加载已有密钥
_LOADED_KEY = ''
for _key_path_candidate in [
        KEY_FILE,  # Desktop/wx_export/key.txt
        os.path.join(os.environ.get('USERPROFILE', 'C:'), 'Desktop', 'wechat_export', 'WeChat', 'key.txt'),  # 默认工作目录
    ]:
    if os.path.exists(_key_path_candidate):
        try:
            with open(_key_path_candidate) as _f:
                _k = _f.read().strip()
                if len(_k) == 64:
                    _LOADED_KEY = _k
                    break
        except: pass

from wcdb_server import WCDBClient
# 顶层 import 确保 PyInstaller 打包这些依赖
import fpdf, openpyxl, PIL

# 日志系统
from logger import init as log_init, info as log_info, error as log_error, except_hook
sys.excepthook = except_hook


def clean_wxid(wxid):
    """清理 wxid: wxid_xxx_xxxx → wxid_xxx"""
    parts = wxid.split('_')
    if len(parts) >= 3:
        return '_'.join(parts[:2])
    return wxid


def find_xwechat_dirs():
    """扫描常见位置找 xwechat_files 目录"""
    candidates = [
        os.path.join(os.environ.get('USERPROFILE', 'C:'), 'Documents', 'xwechat_files'),
        os.path.join(os.environ.get('USERPROFILE', 'C:'), 'Documents', 'WeChat Files'),
    ]
    # 扫描所有盘符根目录
    for letter in 'CDEFGH':
        for sub in ['xwechat_files', 'WeChat Files', 'wxxinxi\\xwechat_files', '储存信息\\xwechat_files']:
            p = f'{letter}:\\{sub}'
            if os.path.isdir(p):
                candidates.append(p)
    for d in candidates:
        if os.path.isdir(d):
            for entry in os.listdir(d):
                if entry.startswith('wxid_') and os.path.isdir(os.path.join(d, entry)):
                    return d
    return ''


class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("微信聊天记录本地导出工具 v1.2.0")
        self.root.geometry("1100x750")
        self._set_icon()
        self.key = _LOADED_KEY or None
        self.wcdb = None
        self.sessions = []
        log_init(OUT)
        log_info("启动", "工具启动")
        self.setup_ui()
        self.show_home()

    def _set_icon(self):
        self._ico = ''
        try:
            for p in [os.path.join(BASE, 'gui', 'icon.ico'), os.path.join(BASE, 'icon.ico')]:
                if os.path.exists(p):
                    self._ico = p
                    self.root.iconbitmap(p)
                    break
        except:
            pass

    def setup_ui(self):
        m = tk.Menu(self.root)
        self.root.config(menu=m)
        fm = tk.Menu(m, tearoff=0)
        fm.add_command(label="获取密钥", command=self.do_getkey)
        fm.add_command(label="连接数据库", command=self.do_connect)
        fm.add_separator()
        fm.add_command(label="退出", command=self.root.quit)
        m.add_cascade(label="操作", menu=fm)

    def clear(self):
        for w in self.root.winfo_children():
            if isinstance(w, tk.Menu): continue
            w.destroy()

    def log(self, msg):
        log_info("GUI", str(msg)[:200])
        try:
            self.status.config(text=str(msg)[:80])
            self.root.update()
        except:
            pass

    def show_home(self):
        self.clear()
        f = ttk.Frame(self.root, padding=40)
        f.pack(fill=tk.BOTH, expand=True)
        ttk.Label(f, text="微信聊天记录本地导出工具", font=("", 20)).pack()
        ttk.Label(f, text="v1.2.0", font=("", 10)).pack(pady=(0, 20))

        dir_f = ttk.LabelFrame(f, text="微信数据目录", padding=10)
        dir_f.pack(fill=tk.X, pady=10)
        pf = ttk.Frame(dir_f)
        pf.pack(fill=tk.X)
        detected = find_xwechat_dirs()
        self.dir_var = tk.StringVar(value=detected)
        ttk.Entry(pf, textvariable=self.dir_var, width=60).pack(side=tk.LEFT, padx=5)
        ttk.Button(pf, text="浏览", command=lambda: self.dir_var.set(filedialog.askdirectory() or self.dir_var.get())).pack(side=tk.LEFT, padx=2)
        if detected:
            ttk.Label(pf, text="✅ 已自动检测", foreground='green').pack(side=tk.LEFT)

        out_f = ttk.LabelFrame(f, text="导出工作目录", padding=10)
        out_f.pack(fill=tk.X, pady=10)
        opf = ttk.Frame(out_f)
        opf.pack(fill=tk.X)
        default_out = os.path.join(os.environ.get('USERPROFILE', 'C:'), 'Desktop', 'wechat_export')
        self.out_dir_var = tk.StringVar(value=default_out)
        ttk.Entry(opf, textvariable=self.out_dir_var, width=60).pack(side=tk.LEFT, padx=5)
        ttk.Button(opf, text="浏览", command=lambda: (self.out_dir_var.set(filedialog.askdirectory() or self.out_dir_var.get()), self._setup_out_dir())).pack(side=tk.LEFT, padx=2)
        self.out_dir_label = ttk.Label(out_f, text="", foreground='green')
        self.out_dir_label.pack(anchor=tk.W, padx=5)

        key_f = ttk.LabelFrame(f, text="数据库密钥", padding=10)
        key_f.pack(fill=tk.X, pady=10)
        kpf = ttk.Frame(key_f); kpf.pack(fill=tk.X)
        ttk.Label(kpf, text="密钥:").pack(side=tk.LEFT)
        self.key_input_var = tk.StringVar(value='')
        self.key_input_var.trace('w', lambda *_: (self.b2.config(state='normal') if re.match(r'^[0-9a-fA-F]{64}$', self.key_input_var.get().strip()) else self.b2.config(state='disabled')))
        self.key_input_entry = ttk.Entry(kpf, textvariable=self.key_input_var, width=56, show='*')
        self.key_input_entry.pack(side=tk.LEFT, padx=5)
        ttk.Button(kpf, text="显示", command=self._toggle_key_show).pack(side=tk.LEFT, padx=2)
        ttk.Label(key_f, text="点击「获取密钥」自动捕获，或直接粘贴已有64位密钥", font=("", 8), foreground='gray').pack(anchor=tk.W)

        bf = ttk.Frame(f)
        bf.pack(pady=10)
        self.b1 = ttk.Button(bf, text="🔑 获取密钥", command=self.do_getkey, width=20)
        self.b1.pack(pady=3)
        self.b2 = ttk.Button(bf, text="🗄️ 连接数据库", command=self.do_connect, width=20, state='disabled')
        self.b2.pack(pady=3)
        self.b3 = ttk.Button(bf, text="📤 浏览会话", command=self.show_sessions, width=20, state='disabled')
        self.b3.pack(pady=3)

        self.status = ttk.Label(f, text="就绪", foreground='gray')
        self.status.pack(pady=10)
        self.key_label = ttk.Label(f, text="", foreground='green')
        self.key_label.pack()

        # 自动填充已有密钥
        if _LOADED_KEY and len(_LOADED_KEY) == 64:
            self.key_input_var.set(_LOADED_KEY)
            self.key_label.config(text=f"✅ 已加载保存的密钥")
            self.b2.config(state='normal')

    def _setup_out_dir(self):
        base = self.out_dir_var.get().strip()
        if not base:
            messagebox.showerror("错误", "请先选择导出工作目录"); return
        wechat_dir = os.path.join(base, 'WeChat')
        try:
            os.makedirs(wechat_dir, exist_ok=True)
            global OUT, KEY_FILE, _LOADED_KEY
            OUT = wechat_dir
            KEY_FILE = os.path.join(OUT, 'key.txt')
            self.out_dir_label.config(text=f"✅ {wechat_dir}")
            self.log(f"导出目录: {wechat_dir}")
            # 尝试在新目录加载已有密钥
            if os.path.exists(KEY_FILE):
                with open(KEY_FILE) as _f:
                    _LOADED_KEY = _f.read().strip()
                if _LOADED_KEY and len(_LOADED_KEY) == 64 and not self.key_input_var.get():
                    self.key_input_var.set(_LOADED_KEY)
                    self.key = _LOADED_KEY
                    self.key_label.config(text=f"✅ 已加载保存的密钥")
                    self.b2.config(state='normal')
        except Exception as e:
            self.log(f"创建目录失败: {e}")
            messagebox.showerror("错误", f"无法创建目录:\n{wechat_dir}\n{e}")

    def _toggle_key_show(self):
        if self.key_input_entry.cget('show') == '*':
            self.key_input_entry.config(show='')
        else:
            self.key_input_entry.config(show='*')

    def _find_node(self):
        node = os.path.join(ROOT, 'runtime', 'node.exe')
        if os.path.exists(node):
            return node
        return shutil.which('node') or shutil.which('node.exe')

    def do_getkey(self):
        threading.Thread(target=self._getkey, daemon=True).start()

    def _getkey(self):
        self.log("[*] 先关闭微信")
        if not messagebox.askokcancel("准备", "1. 关闭微信电脑端（右键系统托盘 → 退出）\n2. 点确定后等待\n3. 看到「等待微信启动」后打开微信\n4. 微信启动过程中自动捕获密钥"):
            return

        node_exe = self._find_node()
        key_js = os.path.join(ROOT, 'scripts', 'get_key.js')
        if not node_exe or not os.path.exists(key_js):
            messagebox.showerror("错误", f"找不到运行时: node={node_exe}, js={key_js}")
            self.log("[-] 失败")
            return

        status_file = os.path.join(OUT, 'key_status.txt')
        if os.path.exists(status_file): os.remove(status_file)
        if os.path.exists(KEY_FILE): os.remove(KEY_FILE)

        self.log("[*] 提权运行...")
        ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", node_exe, f'"{key_js}"', None, 1)
        if ret <= 32:
            self.log(f"[-] ShellExecuteW 失败, 返回值={ret}")
            import subprocess
            try:
                r = subprocess.run([node_exe, key_js], capture_output=True, text=True, timeout=10)
                self.log(f"[-] 非提权运行输出: {(r.stdout + r.stderr)[:150]}")
            except Exception as e2:
                self.log(f"[-] 直接运行也失败: {e2}")
            messagebox.showerror("提权失败", f"ShellExecuteW 返回 {ret}\n请手动以管理员身份运行:\n  {node_exe} \"{key_js}\"")
            return

        self.log("[*] 等待...")
        status_map = {
            'started': '脚本已启动', 'dll_found': '找到 wx_key.dll', 'dll_loaded': 'DLL 加载成功',
            'dll_not_found': '找不到 wx_key.dll', 'waiting_close': '等待微信关闭...',
            'timeout_close': '关微信超时', 'waiting_start': '等待微信启动... (请打开微信)',
            'timeout_start': '等微信启动超时', 'injecting': '正在注入 Hook...',
            'hook_ok': 'Hook 注入成功, 等登录捕获 key...', 'hook_failed': 'Hook 注入失败',
            'polling': '等待登录中捕获 key...', 'timeout_poll': '获取超时', 'captured': '✅ 已捕获!',
        }
        for i in range(150):
            if os.path.exists(KEY_FILE):
                with open(KEY_FILE) as f:
                    k = f.read().strip()
                if len(k) == 64:
                    self.key = k
                    self.key_input_var.set(k)
                    self.key_label.config(text=f"✅ Key: {k[:16]}...")
                    self.b2.config(state='normal')
                    self.log("✅ 成功!")
                    return
            if os.path.exists(status_file):
                try:
                    st = open(status_file).read().strip()
                    self.log(f"[*] {status_map.get(st.split(':')[0], st)}")
                except: pass
            time.sleep(1)
        self.log("[-] 获取失败")

    def do_connect(self):
        # 优先从输入框取密钥
        manual_key = self.key_input_var.get().strip()
        if manual_key and len(manual_key) == 64:
            self.key = manual_key
        elif self.key and len(self.key) == 64:
            pass
        elif os.path.exists(KEY_FILE):
            with open(KEY_FILE) as f: self.key = f.read().strip()
        if not self.key or len(self.key) != 64:
            messagebox.showerror("错误", "密钥无效，请先获取密钥或手动粘贴64位密钥"); return
        threading.Thread(target=self._connect, daemon=True).start()

    def _connect(self):
        self.log("[*] 启动 WCDB 服务...")
        try:
            with open(KEY_FILE, 'w') as f: f.write(self.key)
            data_dir = self.dir_var.get().strip() or ''
            self.wcdb = WCDBClient()
            self.wcdb.start(self.key, data_dir)
            self.sessions = self.wcdb.get_sessions()
            self.b3.config(state='normal')
            self.log(f"✅ {len(self.sessions)} 个会话")
            messagebox.showinfo("成功", f"已连接, {len(self.sessions)} 个会话")
        except Exception as e:
            self.log(f"❌ {e}")

    def show_sessions(self):
        if not self.sessions: return
        self.clear()

        # 搜索栏
        search_frame = ttk.Frame(self.root)
        search_frame.pack(fill=tk.X, padx=10, pady=(10, 0))
        ttk.Label(search_frame, text="🔍", font=("", 12)).pack(side=tk.LEFT, padx=(0, 5))
        search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=search_var, width=50)
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        search_entry.focus()

        # 顶栏
        top = ttk.Frame(self.root)
        top.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(top, text=f"会话 ({len(self.sessions)} 个)", font=("", 14)).pack(side=tk.LEFT)
        ttk.Button(top, text="返回", command=self.show_home).pack(side=tk.RIGHT)

        cols = ('name', 'summary', 'time', 'wxid')
        tree = ttk.Treeview(self.root, columns=cols, show='headings', height=25)
        tree.heading('name', text='会话'); tree.heading('summary', text='最后消息')
        tree.heading('time', text='时间'); tree.heading('wxid', text='')
        tree.column('name', width=200); tree.column('summary', width=250)
        tree.column('time', width=130); tree.column('wxid', width=0, stretch=False)
        sb = ttk.Scrollbar(self.root, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        # 预加载昵称
        all_users = [s.get('username', '') for s in self.sessions if s.get('username', '')
                     and not s.get('username', '').startswith('brand')]
        nick_map = {}
        if all_users and self.wcdb:
            try: nick_map = self.wcdb.get_display_names(all_users[:500])
            except: pass

        # 准备所有行数据 (用于搜索过滤)
        all_rows = []
        for s in self.sessions:
            name = s.get('username', '?')
            display = nick_map.get(name, name)
            summary = s.get('summary', '')
            last_ts = s.get('last_timestamp', s.get('sort_timestamp', ''))
            if isinstance(last_ts, str) and last_ts.isdigit():
                try: last_ts = datetime.datetime.fromtimestamp(int(last_ts)).strftime('%m-%d %H:%M')
                except: pass
            all_rows.append((str(display)[:35], summary[:25], str(last_ts)[:16], name))

        def populate(keyword=''):
            tree.delete(*tree.get_children())
            kw = keyword.lower().strip()
            for vals in all_rows:
                if kw:
                    # 匹配显示名、wxid、摘要
                    if kw not in vals[0].lower() and kw not in vals[3].lower() and kw not in vals[1].lower():
                        continue
                tree.insert('', tk.END, values=vals)

        populate()

        def on_search(*args):
            populate(search_var.get())

        search_var.trace('w', on_search)
        search_entry.bind('<KeyRelease>', lambda e: on_search())

        btn_frame = ttk.Frame(self.root)
        btn_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Button(btn_frame, text="📄 查看消息", command=lambda: self.show_chat_from_tree(tree)).pack(side=tk.LEFT, padx=2)

        def ondouble(e):
            try: self.show_chat_from_tree(tree)
            except Exception as ex: messagebox.showerror("错误", str(ex))
        tree.bind('<Double-1>', ondouble)
        tree.bind('<Return>', lambda e: ondouble(e))

    def show_chat_from_tree(self, tree):
        sel = tree.selection()
        if sel:
            v = tree.item(sel[0])['values']
            wxid = str(v[3]) if len(v) >= 4 else str(v[0])
            self.show_chat(wxid)

    def show_chat(self, wxid):
        if not self.wcdb: return
        try:
            total = self.wcdb.get_count(wxid)
        except: total = 0

        win = tk.Toplevel(self.root)
        win.title(f"{wxid} ({total})"); win.geometry("900x650")
        if self._ico: win.iconbitmap(self._ico)

        # 从数据目录检测自己的 wxid
        MY = ''
        data_dir = self.dir_var.get() if hasattr(self, 'dir_var') else ''
        if data_dir and os.path.isdir(data_dir):
            for d in os.listdir(data_dir):
                if d.startswith('wxid_') and os.path.isdir(os.path.join(data_dir, d)):
                    MY = clean_wxid(d)
                    break

        top = ttk.Frame(win); top.pack(fill=tk.X, padx=5, pady=2)
        spin_max = max(total, 200)
        spin = ttk.Spinbox(top, from_=50, to=spin_max, increment=50, width=8)
        spin.set(min(200, total)); spin.pack(side=tk.LEFT)
        label_info = ttk.Label(top, text=f"共 {total} 条")
        label_info.pack(side=tk.RIGHT)

        txt = tk.Text(win, wrap=tk.WORD, font=("微软雅黑", 10))
        scr = ttk.Scrollbar(win, command=txt.yview)
        txt.configure(yscrollcommand=scr.set)
        txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5,0), pady=5)
        scr.pack(side=tk.RIGHT, fill=tk.Y, pady=5)
        txt.config(state=tk.DISABLED)

        def do_load():
            try: limit = int(spin.get())
            except: limit = 200
            try:
                rows = self.wcdb.get_messages(wxid, limit, 0)
            except Exception as e:
                label_info.config(text=f"错误: {e}")
                return
            senders = list(set(m.get('sender_username','') for m in rows if m.get('sender_username','')))
            if wxid not in senders: senders.append(wxid)
            nm = {}
            if senders:
                try: nm = self.wcdb.get_display_names(senders)
                except: pass
            rows.sort(key=lambda m: int(m.get('create_time','0') or '0'))
            txt.config(state=tk.NORMAL)
            txt.delete(1.0, tk.END)
            count = 0
            type_icons = {3:'[图片]',34:'[语音]',43:'[视频]',47:'[表情]',42:'[名片]',48:'[位置]',49:'[链接/卡片]',50:'[通话]',10000:'[系统通知]'}
            for m in rows:
                lt = int(m.get('local_type',0))
                c = m.get('message_content','') or ''
                ts = m.get('create_time','')
                sr = m.get('sender_username','')
                if ts.isdigit():
                    ts = datetime.datetime.fromtimestamp(int(ts)).strftime('%m-%d %H:%M')
                name = nm.get(sr, sr)
                if sr == MY: name = '我'
                if lt in (1, 244813135921):
                    txt.insert(tk.END, f"{name}  {ts}\n  {str(c)[:200]}\n\n")
                    count += 1
                else:
                    icon = type_icons.get(lt, f'[类型{lt}]')
                    txt.insert(tk.END, f"{name}  {ts}\n  {icon}\n\n")
            txt.see(tk.END)
            txt.config(state=tk.DISABLED)
            title = nm.get(wxid, wxid)
            win.title(f"{title} ({len(rows)}/{total})")
            label_info.config(text=f"{len(rows)} 条消息")

        ttk.Button(top, text="加载", command=do_load).pack(side=tk.LEFT, padx=2)

        def do_export(fmt):
            if not os.path.isdir(OUT):
                messagebox.showerror("错误", "请先在首页设置导出工作目录（选择文件夹 → 确认并创建）"); return
            try: limit = int(spin.get())
            except: limit = 200

            # 新建进度窗口
            prog = tk.Toplevel(win)
            prog.title("导出中..."); prog.geometry("400x150")
            if self._ico: prog.iconbitmap(self._ico)
            ttk.Label(prog, text="正在导出...", font=("", 12)).pack(pady=(20, 10))
            bar = ttk.Progressbar(prog, mode='indeterminate', length=300)
            bar.pack(pady=5); bar.start()
            status_lbl = ttk.Label(prog, text="初始化...")
            status_lbl.pack(pady=5)
            prog.update()

            def gui_done(msg):
                """在主线程执行 GUI 操作"""
                self.root.after(0, lambda: prog.destroy())
                self.root.after(100, lambda: messagebox.showinfo("完成", msg))

            def gui_error(msg):
                self.root.after(0, lambda: prog.destroy())
                self.root.after(100, lambda: messagebox.showerror("错误", msg))

            def export_task():
                try:
                    log_info("导出", f"格式={fmt}, 限制={limit}")
                    rows = self.wcdb.get_messages(wxid, limit, 0)
                    log_info("导出", f"获取消息 {len(rows)} 条")
                except Exception as e:
                    log_error("导出", f"获取消息失败: {e}")
                    gui_error(f"获取消息失败\n{e}"); return
                if not rows:
                    gui_done("该会话没有消息数据"); return

                if any(int(m.get('local_type',0)) in (3, 47) for m in rows):
                    try:
                        from media_resolver import MediaResolver
                        data_dir = self.dir_var.get().strip() if hasattr(self, 'dir_var') else ''
                        resolver = MediaResolver(self.wcdb, OUT, 0, '', data_dir,
                                                 log_func=lambda m: log_info("图片", m))
                        rows = resolver.resolve_images(rows, wxid, try_native=True)
                    except Exception as e:
                        log_error("导出", f"图片解析失败: {e}")

                senders = list(set(m.get('sender_username','') for m in rows if m.get('sender_username','')))
                if wxid not in senders: senders.append(wxid)
                nm = {}
                if senders:
                    try: nm = self.wcdb.get_display_names(senders)
                    except: pass

                # 预处理
                export_rows = []
                for m in rows:
                    m = dict(m)
                    sr = m.get('sender_username', '')
                    im = 1 if sr and MY and clean_wxid(sr) == MY else 0
                    display = '我' if im else nm.get(sr, sr)
                    m['is_mine'] = im; m['sender_display'] = display
                    raw_ts = m.get('create_time', '')
                    if raw_ts and str(raw_ts).isdigit():
                        try: m['time_str'] = datetime.datetime.fromtimestamp(int(raw_ts)).strftime('%Y-%m-%d %H:%M:%S')
                        except: m['time_str'] = str(raw_ts)
                    else: m['time_str'] = str(raw_ts)
                    m['sender_username'] = display
                    export_rows.append(m)

                # 导出文件
                ext_map = {'html': 'html', 'pdf': 'pdf', 'txt': 'txt', 'json': 'json', 'csv': 'csv', 'excel': 'xlsx'}
                file_ext = ext_map.get(fmt, fmt)
                title = nm.get(wxid, wxid)
                safe_name = ''.join(c for c in title if c.isalnum() or c in ' _-').strip() or wxid
                ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')

                # HTML 特殊处理: 创建文件夹 + 图片子目录
                if fmt == 'html':
                    folder_name = f'{safe_name}的聊天记录-HTML文件'
                    html_dir = os.path.join(OUT, folder_name)
                    img_dir = os.path.join(html_dir, '图片')
                    os.makedirs(img_dir, exist_ok=True)
                    path = os.path.join(html_dir, 'index.html')
                else:
                    filename = f'{safe_name}_{ts}.{file_ext}'
                    path = os.path.join(OUT, filename)
                    os.makedirs(OUT, exist_ok=True)
                self.log(f"导出到: {path}")

                try:
                    if fmt == 'txt':
                        with open(path, 'w', encoding='utf-8') as f:
                            for m in export_rows:
                                c = m.get('message_content','') or ''
                                t = m.get('time_str', '')
                                lt = int(m.get('local_type',0))
                                name = m.get('sender_display', '?')
                                if lt in (1, 244813135921):
                                    f.write(f"[{t}] {name}\n{c}\n\n")
                                elif lt == 3:
                                    f.write(f"[{t}] {name}\n[图片]\n\n")
                                else:
                                    f.write(f"[{t}] {name}\n[类型{lt}]\n\n")
                    elif fmt == 'json':
                        clean_rows = []
                        for m in export_rows:
                            cm = {k: v for k, v in m.items() if not callable(v)}
                            clean_rows.append(cm)
                        with open(path, 'w', encoding='utf-8') as f:
                            json.dump(clean_rows, f, ensure_ascii=False, indent=2, default=str)
                    elif fmt == 'html':
                        import html_exporter
                        html_exporter.export(export_rows, path, '我', title, img_dir=img_dir)
                    elif fmt == 'pdf':
                        import pdf_exporter
                        pdf_exporter.export(export_rows, path, '我', title)
                    elif fmt == 'csv':
                        import csv_exporter
                        csv_exporter.export(export_rows, path, '我', title)
                    elif fmt == 'excel':
                        import excel_exporter
                        excel_exporter.export(export_rows, path, '我', title)
                    log_info("导出", f"完成: {path}")
                    gui_done(f"已导出 {len(rows)} 条\n{path}")
                except Exception as e:
                    log_error("导出", f"写入失败: {e}")
                    gui_error(str(e))

            threading.Thread(target=export_task, daemon=True).start()

        fmt_var = tk.StringVar(value='html')
        fmt_menu = ttk.Combobox(top, textvariable=fmt_var, state='readonly', width=10,
                                values=['HTML','PDF','TXT','JSON','CSV','Excel'])
        fmt_menu.pack(side=tk.LEFT, padx=2)
        ttk.Button(top, text="导出", command=lambda: do_export(fmt_var.get().lower())).pack(side=tk.LEFT)
        do_load()

    def run(self):
        self.root.mainloop()


if __name__ == '__main__':
    App().run()
