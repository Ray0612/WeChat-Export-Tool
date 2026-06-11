"""WCDB 服务客户端 - 自动检测路径"""
import subprocess, json, os, socket, time, http.client

def _script_dir():
    return os.path.dirname(os.path.abspath(__file__))

class WCDBClient:
    def __init__(self):
        self.proc = None
        self.port = None

    def start(self, key, data_dir='', timeout=45):
        # 查找资源路径（相对脚本位置）
        base = os.path.dirname(_script_dir())
        server = os.path.join(_script_dir(), 'wcdb_server.js')

        # 尝试 Electron, 回退 Node.js
        candidates = [
            os.path.join(base, 'electron', 'electron.exe'),
            os.path.join(base, 'runtime', 'node.exe'),
        ]
        electron = ''
        for c in candidates:
            if os.path.exists(c): electron = c; break

        if not electron:
            raise RuntimeError('Electron/Node.js 运行时未找到')

        # 找端口
        s = socket.socket()
        s.bind(('127.0.0.1', 0))
        self.port = s.getsockname()[1]
        s.close()

        # 启动
        args = [electron, server, key, str(self.port)]
        if data_dir:
            args.append(data_dir)

        self.proc = subprocess.Popen(
            args, cwd=_script_dir(),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )

        for i in range(timeout):
            if self.proc.poll() is not None:
                out = self.proc.stdout.read(500).decode('utf-8', errors='replace').strip() if self.proc.stdout else ''
                raise RuntimeError(f'WCDB 服务异常退出: {out[:200]}')
            try:
                c = http.client.HTTPConnection('127.0.0.1', self.port, timeout=2)
                c.request('GET', '/ping')
                r = c.getresponse()
                if r.read().decode() == 'pong':
                    return True
            except: pass
            time.sleep(1)
        raise RuntimeError('WCDB 启动超时')

    def _get(self, path):
        c = http.client.HTTPConnection('127.0.0.1', self.port, timeout=120)
        c.request('GET', '/' + path)
        r = c.getresponse()
        d = r.read().decode('utf-8')
        c.close()
        return d

    def get_sessions(self):
        return json.loads(self._get('sessions'))
    def get_messages(self, wxid, limit=500, offset=0):
        return json.loads(self._get(f'messages/{wxid}/{limit}/{offset}'))
    def get_count(self, wxid):
        return int(self._get(f'count/{wxid}'))
    def get_display_names(self, wxids):
        import http.client as hc
        c = hc.HTTPConnection('127.0.0.1', self.port, timeout=30)
        c.request('POST', '/displaynames', json.dumps(wxids), {'Content-Type': 'application/json'})
        r = c.getresponse()
        d = r.read().decode('utf-8')
        c.close()
        return json.loads(d)

    def stop(self):
        if self.proc:
            try: self.proc.terminate()
            except: pass
            self.proc = None
