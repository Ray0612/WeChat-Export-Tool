"""
JsonExporter — JSON 格式导出器。
"""
import json
import os
from datetime import datetime
from src.models import ExportResult, Session


class JsonExporter:
    """JSON 格式导出器。"""

    def __init__(self, pretty: bool = True, include_raw: bool = False):
        self.pretty = pretty
        self.include_raw = include_raw

    def export(self, result: ExportResult, output_dir: str) -> str:
        filename = f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        path = os.path.join(output_dir, filename)
        data = self._to_dict(result)
        with open(path, 'w', encoding='utf-8') as f:
            if self.pretty:
                json.dump(data, f, ensure_ascii=False, indent=2)
            else:
                json.dump(data, f, ensure_ascii=False)
        return path

    @staticmethod
    def _to_dict(result: ExportResult) -> dict:
        sessions_dict = []
        for sess in result.sessions:
            msgs = []
            for m in sess.messages:
                d = {
                    'sequence': m.sequence,
                    'content': m.content,
                    'session_tag': m.session_tag,
                }
                if m.receiver:
                    d['receiver'] = m.receiver
                if m.timestamp:
                    d['timestamp'] = m.timestamp
                if m.chatroom_id:
                    d['chatroom_id'] = m.chatroom_id
                if m.chatroom_name:
                    d['chatroom_name'] = m.chatroom_name
                msgs.append(d)
            sessions_dict.append({
                'session_tag': sess.session_tag,
                'name': sess.name,
                'message_count': sess.message_count,
                'messages': msgs,
            })

        return {
            'export_time': result.export_time,
            'wechat_version': result.wechat_version,
            'data_source': result.data_source,
            'total_messages': result.total_messages,
            'cache_pages_found': result.cache_pages_found,
            'failed_parses': result.failed_parses,
            'sessions': sessions_dict,
            'warnings': result.warnings,
        }
