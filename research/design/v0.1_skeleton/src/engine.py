"""
ExporterEngine — 导出引擎。
"""
from datetime import datetime
from src.models import ExportResult, Session


class ExporterEngine:
    """导出引擎主控类。"""

    def __init__(self, reader, scanner, parser, exporters: list):
        self.reader = reader
        self.scanner = scanner
        self.parser = parser
        self.exporters = exporters

    def run(self, output_dir: str) -> ExportResult:
        result = ExportResult(
            export_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            wechat_version='4.1.10.29',
            data_source='0x2d8_struct',
            sessions=[],
        )

        # 1. Open reader
        if not self.reader.open():
            result.warnings.append("无法连接到 Weixin.exe")
            return result
        if self.reader.info:
            result.data_source = f"0x2d8_struct(pid={self.reader.info.pid})"

        # 2. Scan
        pages = self.scanner.find_candidate_pages()
        result.cache_pages_found = len(pages)
        if not pages:
            result.warnings.append("未找到消息结构体，请先打开一个聊天窗口")
            self.reader.close()
            return result

        # 3. Parse
        all_messages = []
        for page_addr, entries in pages:
            for entry in entries:
                msg = self.parser.parse_one(entry)
                if msg:
                    all_messages.append(msg)
                else:
                    result.failed_parses += 1

        result.total_messages = len(all_messages)

        # 4. Cluster by session_tag
        session_map = {}
        for msg in all_messages:
            tag = msg.session_tag
            if tag not in session_map:
                session_map[tag] = Session(
                    session_tag=tag,
                    name=tag[:40],
                )
            session_map[tag].messages.append(msg)

        for sess in session_map.values():
            sess.messages.sort(key=lambda m: m.sequence)
            sess.message_count = len(sess.messages)
        result.sessions = sorted(
            session_map.values(),
            key=lambda s: s.session_tag,
        )

        # 5. Export
        for exporter in self.exporters:
            try:
                path = exporter.export(result, output_dir)
                print(f"  [export] {path}")
            except Exception as e:
                result.warnings.append(
                    f"导出失败 ({exporter.__class__.__name__}): {e}"
                )

        self.reader.close()
        return result
