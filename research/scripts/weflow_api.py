"""WeFlow HTTP API 客户端"""
import json, os, http.client, time, subprocess

class WeFlowAPI:
    """通过 WeFlow HTTP API 读取数据"""

    def __init__(self):
        self.port = 5031
        self.token = ''
        self._ensure_api_enabled()

    def _ensure_api_enabled(self):
        """确保 WeFlow 配置开启了 HTTP API"""
        config_path = os.path.join(os.environ.get('USERPROFILE', ''),
                                   'AppData', 'Roaming', 'weflow', 'WeFlow-config.json')
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
                changed = False
                if not cfg.get('httpApiEnabled'):
                    cfg['httpApiEnabled'] = True
                    changed = True
                if not cfg.get('httpApiToken'):
                    cfg['httpApiToken'] = 'wechat-export-tool'
                    changed = True
                if changed:
                    with open(config_path, 'w', encoding='utf-8') as f:
                        json.dump(cfg, f, indent=2, ensure_ascii=False)
                self.token = cfg.get('httpApiToken', 'wechat-export-tool')
            except: pass

    def _request(self, method, path, body=None):
        """发请求到 WeFlow API"""
        c = http.client.HTTPConnection('127.0.0.1', self.port, timeout=30)
        headers = {'Content-Type': 'application/json'}
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'
        c.request(method, path, body=json.dumps(body) if body else None, headers=headers)
        r = c.getresponse()
        d = r.read().decode('utf-8')
        c.close()
        return json.loads(d) if d else {}

    def health(self):
        try:
            c = http.client.HTTPConnection('127.0.0.1', self.port, timeout=3)
            c.request('GET', '/api/v1/health')
            r = c.getresponse()
            return r.status == 200
        except:
            return False

    def start_weflow(self):
        """启动 WeFlow（如果没运行）"""
        import subprocess, psutil
        for proc in psutil.process_iter(['pid', 'name']):
            if proc.info['name'] == 'WeFlow.exe':
                return True  # 已运行
        # 尝试启动
        weflow = r'C:\Users\OK\AppData\Local\Programs\WeFlow\WeFlow.exe'
        if os.path.exists(weflow):
            subprocess.Popen([weflow], shell=True)
            time.sleep(5)
            return True
        return False

    def get_sessions(self):
        return self._request('GET', '/api/v1/sessions').get('data', [])

    def get_messages(self, session_id, limit=200, offset=0):
        return self._request('GET', f'/api/v1/sessions/{session_id}/messages?limit={limit}&offset={offset}').get('data', [])

    def get_contacts(self):
        return self._request('GET', '/api/v1/contacts').get('data', [])
