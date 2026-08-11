"""WCDB 服务客户端 - 自动检测路径"""
import subprocess, json, os, socket, time, http.client, shutil

def _script_dir():
    return os.path.dirname(os.path.abspath(__file__))

class WCDBClient:
    def __init__(self):
        self.proc = None
        self.port = None

    def _find_runtime(self, base):
        candidates = [
            os.path.join(base, 'electron', 'electron.exe'),
            os.path.join(base, 'runtime', 'node.exe'),
            os.path.join(base, 'APP', 'WeChatExport', 'electron', 'electron.exe'),
            os.path.join(base, 'APP', 'WeChatExport', 'runtime', 'node.exe'),
        ]
        for c in candidates:
            if os.path.exists(c): return c
        return shutil.which('node') or shutil.which('node.exe') or ''

    def start(self, key, data_dir='', timeout=45):
        base = os.path.dirname(_script_dir())
        server = os.path.join(_script_dir(), 'wcdb_server.js')
        runtime = self._find_runtime(base)
        if not runtime:
            raise RuntimeError('Electron/Node.js 运行时未找到')

        s = socket.socket()
        s.bind(('127.0.0.1', 0))
        self.port = s.getsockname()[1]
        s.close()

        args = [runtime, server, key, str(self.port)]
        if data_dir:
            args.append(data_dir)

        self.proc = subprocess.Popen(
            args, cwd=_script_dir(),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )

        for i in range(timeout):
            if self.proc.poll() is not None:
                out = ''
                try: out = self.proc.stdout.read(1000).decode('utf-8', errors='replace').strip() if self.proc.stdout else '(无输出)'
                except: out = '(读取失败)'
                raise RuntimeError(f'WCDB 服务异常退出:\n{out[:500]}')
            try:
                c = http.client.HTTPConnection('127.0.0.1', self.port, timeout=2)
                c.request('GET', '/ping')
                r = c.getresponse()
                if r.read().decode() == 'pong':
                    return True
            except: pass
            time.sleep(1)
        out = ''
        try: out = '\n' + self.proc.stdout.read(1000).decode('utf-8', errors='replace').strip() if self.proc.stdout else ''
        except: pass
        raise RuntimeError(f'WCDB 启动超时{out}')

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

    # v1.2: 媒体 API
    def scan_media(self, session_id, media_type=1, begin=0, end=4102444800, limit=200, offset=0):
        return json.loads(self._get(f'scan_media/{session_id}/{media_type}/{begin}/{end}/{limit}/{offset}'))

    def resolve_image(self, md5):
        return json.loads(self._get(f'resolve_image/{md5}'))

    def resolve_image_batch(self, requests):
        import http.client as hc
        c = hc.HTTPConnection('127.0.0.1', self.port, timeout=60)
        c.request('POST', '/resolve_image_batch', json.dumps(requests), {'Content-Type': 'application/json'})
        r = c.getresponse(); d = r.read().decode('utf-8'); c.close()
        return json.loads(d)

    def stop(self):
        if self.proc:
            try: self.proc.terminate()
            except: pass
            self.proc = None
