"""
阶段 5：导出 TXT / Markdown
"""
import os, datetime

type_map = {
    1: "文本", 3: "图片", 6: "文件", 19: "合并转发", 33: "链接",
    36: "语音", 47: "表情", 49: "转发", 51: "视频",
    53: "接龙", 57: "聊天卡片", 62: "拍一拍",
    2000: "转账", 2001: "红包"
}

def get_display_name(wxid, nickname_map=None):
    if nickname_map and wxid in nickname_map:
        return nickname_map[wxid]
    return wxid

def timestamp_to_str(ts):
    """Convert Unix timestamp to readable string"""
    if ts:
        try:
            return str(datetime.datetime.fromtimestamp(int(ts)))
        except:
            pass
    return ''

def export_txt(session_name, messages, output_dir, nickname_map=None):
    """Export session to TXT"""
    path = os.path.join(output_dir, f"{session_name[:30]}.txt")
    me = nickname_map.get('__me__', '我') if nickname_map else '我'

    with open(path, 'w', encoding='utf-8') as f:
        f.write(f"【{session_name}】\n\n")
        for m in messages:
            ts = timestamp_to_str(m.get('timestamp', 0))
            sender = get_display_name(m.get('sender', ''), nickname_map)
            content = m.get('content', '')
            mt = m.get('type', 0)
            if mt and mt != 1:
                content = f"[{type_map.get(mt, str(mt))}] {content}"
            f.write(f"[{ts}] {sender}: {content}\n")

    return path

def export_markdown(session_name, messages, output_dir, nickname_map=None):
    """Export session to Markdown"""
    path = os.path.join(output_dir, f"{session_name[:30]}.md")

    with open(path, 'w', encoding='utf-8') as f:
        f.write(f"# 会话：{session_name}\n\n")
        for m in messages:
            ts = timestamp_to_str(m.get('timestamp', 0))
            sender = get_display_name(m.get('sender', ''), nickname_map)
            content = m.get('content', '')
            mt = m.get('type', 0)
            if mt and mt != 1:
                content = f"[{type_map.get(mt, str(mt))}] {content}"
            f.write(f"- **{sender}** [{ts}]: {content}\n")

    return path
