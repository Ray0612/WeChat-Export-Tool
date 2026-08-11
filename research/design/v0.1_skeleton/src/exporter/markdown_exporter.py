"""
MarkdownExporter — Markdown 格式导出器。
"""
import os
from datetime import datetime
from src.models import ExportResult


class MarkdownExporter:
    """Markdown 格式导出器。"""

    def export(self, result: ExportResult, output_dir: str) -> str:
        filename = f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        path = os.path.join(output_dir, filename)

        with open(path, 'w', encoding='utf-8') as f:
            f.write("# 微信聊天记录导出\n\n")
            f.write(f"- 导出时间: {result.export_time}\n")
            f.write(f"- 微信版本: {result.wechat_version}\n")
            f.write(f"- 数据来源: {result.data_source}\n")
            f.write(f"- 总消息数: {result.total_messages}\n\n")

            for sess in result.sessions:
                display_name = sess.name or sess.session_tag
                f.write("---\n\n")
                f.write(f"## 会话: {display_name}\n")
                f.write(f"消息数: {sess.message_count}\n\n")

                for m in sess.messages:
                    receiver = f" [{m.receiver}]" if m.receiver else ""
                    f.write(f"**[{m.sequence}]{receiver}** {m.content}\n\n")

            if result.warnings:
                f.write("\n---\n### 警告\n")
                for w in result.warnings:
                    f.write(f"- {w}\n")

        return path
