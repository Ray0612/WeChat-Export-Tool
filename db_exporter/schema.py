"""
阶段 3+4：表结构分析和消息提取
用法:
    from db_exporter.schema import MessageDB
    db = MessageDB('message_0.db', key_hex='...')
    sessions = db.get_sessions()  # 按会话聚合
    msgs = db.get_messages('wxid_...')  # 单个会话消息
"""
import sqlite3, os, json, datetime
from collections import defaultdict

type_map = {
    1: "文本", 3: "图片", 6: "文件", 19: "合并转发", 33: "链接",
    36: "语音", 47: "表情", 49: "转发", 51: "视频",
    53: "接龙", 57: "聊天卡片", 62: "拍一拍",
    2000: "转账", 2001: "红包"
}

class MessageDB:
    def __init__(self, db_path, key_hex=None, key_str=None):
        self.db_path = db_path
        self.conn = None

        if key_hex:
            self.conn = sqlite3.connect(db_path)
            self.conn.execute(f"PRAGMA key = x'{key_hex}'")
            self.conn.execute("PRAGMA cipher_page_size = 4096")
            self._verify()
        elif key_str:
            self.conn = sqlite3.connect(db_path)
            self.conn.execute(f"PRAGMA key = '{key_str}'")
            self.conn.execute("PRAGMA cipher_page_size = 4096")
            self._verify()

    def _verify(self):
        """Verify the connection works"""
        try:
            cursor = self.conn.execute("SELECT count(*) FROM sqlite_master")
            self.connected = True
            self.table_count = cursor.fetchone()[0]
        except:
            self.connected = False
            raise ValueError("解密失败：密钥不匹配或数据库格式不正确")

    def get_tables(self):
        """List all tables"""
        cursor = self.conn.execute("SELECT name, type FROM sqlite_master ORDER BY type, name")
        return cursor.fetchall()

    def get_table_info(self, table_name):
        """Get column info for a table"""
        cursor = self.conn.execute(f"PRAGMA table_info({table_name})")
        return cursor.fetchall()

    def get_sessions(self):
        """按会话聚合消息"""
        # 先探测表结构
        tables = self.get_tables()
        msg_table = None
        for name, ttype in tables:
            if 'message' in name.lower() and ttype == 'table':
                msg_table = name
                break

        if not msg_table:
            raise ValueError("未找到消息表")

        # 获取列名
        cols = [col[1] for col in self.get_table_info(msg_table)]
        print(f"消息表: {msg_table}, 列: {cols}")

        # 尝试通用查询
        query = f"SELECT * FROM {msg_table} ORDER BY CreateTime"
        cursor = self.conn.execute(query)
        rows = cursor.fetchall()

        # 按会话聚合 (chatroom -> messages)
        sessions = defaultdict(list)
        for row in rows:
            msg = dict(zip(cols, row))
            session = self._get_session_key(msg)
            sessions[session].append(msg)

        return dict(sessions)

    def _get_session_key(self, msg):
        """Determine which session a message belongs to"""
        for key in ['ChatroomName', 'StrTalker', 'TalkerId', 'FromUser', 'ToUser']:
            if key in msg and msg[key]:
                val = msg[key]
                if val and val != '0' and len(str(val)) > 2:
                    return str(val)
        return '未知会话'

    def get_messages(self, session_name, sessions_dict=None):
        """Get messages for a specific session, sorted by time"""
        if sessions_dict is None:
            sessions_dict = self.get_sessions()
        msgs = sessions_dict.get(session_name, [])
        # 排序
        msgs.sort(key=lambda m: (
            m.get('CreateTime', 0) or m.get('Sequence', 0) or 0
        ))
        return msgs

    def normalize_message(self, msg):
        """Convert raw DB row to standard output format"""
        content = msg.get('StrContent', '') or msg.get('Content', '') or ''
        mtype = msg.get('Type', 0)
        timestamp = msg.get('CreateTime', 0)
        sender = msg.get('FromUser', '') or msg.get('StrTalker', '')

        return {
            'sender': sender,
            'content': content,
            'type': mtype,
            'type_txt': type_map.get(mtype, f"未知({mtype})"),
            'timestamp': timestamp,
            'date': str(datetime.datetime.fromtimestamp(timestamp)) if timestamp else '',
        }

    def close(self):
        if self.conn:
            self.conn.close()
