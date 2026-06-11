# -*- coding: utf-8 -*-
"""微信导出工具 v1.0 — Python + Electron + WCDB"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os, sys, threading, time, datetime, json, ctypes, shutil

if getattr(sys, 'frozen', False):
    BASE = os.path.dirname(sys.executable)
else:
    BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, 'scripts'))
if sys.stdout: sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ROOT = BASE
OUT = os.path.join(os.environ.get('USERPROFILE', BASE), 'Desktop', 'wx_export')
KEY_FILE = os.path.join(OUT, 'key.txt')
os.makedirs(OUT, exist_ok=True)

from wcdb_server import WCDBClient


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
        'D:\\wxxinxi\\xwechat_files',
        'D:\\储存信息\\xwechat_files',
    ]
    for d in candidates:
        if os.path.isdir(d):
            for entry in os.listdir(d):
                if entry.startswith('wxid_') and os.path.isdir(os.path.join(d, entry)):
                    return d
    return ''


class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("微信导出工具 v1.0")
        self.root.geometry("1100x750")
        self._set_icon()
        self.key = None
        self.wcdb = None
        self.sessions = []
        self.setup_ui()
        self.show_home()

    def _set_icon(self):
        try:
            ico = os.path.join(BASE, 'icon.ico')
            if os.path.exists(ico):
                self.root.iconbitmap(ico)
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
        try:
            self.status.config(text=str(msg)[:80])
            self.root.update()
        except:
            pass

    def show_home(self):
        self.clear()
        f = ttk.Frame(self.root, padding=40)
        f.pack(fill=tk.BOTH, expand=True)
        ttk.Label(f, text="微信导出工具", font=("", 20)).pack()
        ttk.Label(f, text="v1.0 — Python + Electron + WCDB", font=("", 10)).pack(pady=(0, 20))

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

        bf = ttk.Frame(f)
        bf.pack(pady=20)
        self.b1 = ttk.Button(bf, text="🔑 获取密钥", command=self.do_getkey, width=20)
        self.b1.pack(pady=5)
        self.b2 = ttk.Button(bf, text="🗄️ 连接数据库", command=self.do_connect, width=20, state='disabled')
        self.b2.pack(pady=5)
        self.b3 = ttk.Button(bf, text="📤 浏览会话", command=self.show_sessions, width=20, state='disabled')
        self.b3.pack(pady=5)

        self.status = ttk.Label(f, text="就绪", foreground='gray')
        self.status.pack(pady=10)
        self.key_label = ttk.Label(f, text="", foreground='green')
        self.key_label.pack()

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
        if not self.key and os.path.exists(KEY_FILE):
            with open(KEY_FILE) as f: self.key = f.read().strip()
        if not self.key: messagebox.showerror("错误", "请先获取密钥"); return
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

        # 从数据目录检测自己的 wxid
        MY = ''
        data_dir = self.dir_var.get() if hasattr(self, 'dir_var') else ''
        if data_dir and os.path.isdir(data_dir):
            for d in os.listdir(data_dir):
                if d.startswith('wxid_') and os.path.isdir(os.path.join(data_dir, d)):
                    MY = clean_wxid(d)
                    break

        top = ttk.Frame(win); top.pack(fill=tk.X, padx=5, pady=2)
        spin = ttk.Spinbox(top, from_=50, to=2000, increment=50, width=6)
        spin.set(200); spin.pack(side=tk.LEFT)
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
            for m in rows:
                lt = int(m.get('local_type',0))
                # v1.0 只显示文字消息 (1=文本, 244813135921=ZSTD压缩文本)
                if lt != 1 and lt != 244813135921: continue
                c = m.get('message_content','') or ''
                ts = m.get('create_time','')
                sr = m.get('sender_username','')
                if ts.isdigit():
                    ts = datetime.datetime.fromtimestamp(int(ts)).strftime('%m-%d %H:%M')
                name = nm.get(sr, sr)
                if sr == MY: name = '我'
                txt.insert(tk.END, f"{name}  {ts}\n  {str(c)[:200]}\n\n")
                count += 1
            txt.see(tk.END)
            txt.config(state=tk.DISABLED)
            title = nm.get(wxid, wxid)
            win.title(f"{title} ({len(rows)}/{total}, 文字{count})")
            label_info.config(text=f"{count} 条文字消息")

        ttk.Button(top, text="加载", command=do_load).pack(side=tk.LEFT, padx=2)

        def do_export(fmt):
            try: limit = int(spin.get())
            except: limit = 200
            try:
                rows = self.wcdb.get_messages(wxid, limit, 0)
            except Exception as e:
                self.log(f"导出失败: {e}")
                messagebox.showerror("错误", f"获取消息失败\n{e}")
                return
            if not rows:
                messagebox.showinfo("提示", "该会话没有消息数据"); return
            # v1.0 只导文字消息
            rows = [m for m in rows if int(m.get('local_type',0)) in (1, 244813135921)]
            senders = list(set(m.get('sender_username','') for m in rows if m.get('sender_username','')))
            if wxid not in senders: senders.append(wxid)
            nm = {}
            if senders:
                try: nm = self.wcdb.get_display_names(senders)
                except: pass
            path = filedialog.asksaveasfilename(
                title="导出聊天记录", defaultextension=f".{fmt}",
                filetypes=[(fmt.upper(), f"*.{fmt}"), ("所有文件", "*.*")]
            )
            if not path: return
            try:
                if fmt == 'txt':
                    with open(path, 'w', encoding='utf-8') as f:
                        for m in rows:
                            c = m.get('message_content','') or ''
                            ts = m.get('create_time','')
                            sr = m.get('sender_username','')
                            name = nm.get(sr, sr)
                            if sr == MY: name = '我'
                            f.write(f"[{ts}] {name}\n{c}\n\n")
                elif fmt == 'json':
                    with open(path, 'w', encoding='utf-8') as f:
                        json.dump(rows, f, ensure_ascii=False, indent=2)
                messagebox.showinfo("完成", f"已导出 {len(rows)} 条\n{path}")
            except Exception as e:
                messagebox.showerror("错误", str(e))

        ttk.Button(top, text="导出TXT", command=lambda: do_export('txt')).pack(side=tk.LEFT, padx=2)
        ttk.Button(top, text="导出JSON", command=lambda: do_export('json')).pack(side=tk.LEFT, padx=2)
        do_load()

    def run(self):
        self.root.mainloop()


if __name__ == '__main__':
    App().run()
