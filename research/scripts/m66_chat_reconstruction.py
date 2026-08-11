"""
M66 — Chat Reconstruction
输出可读聊天记录，不是 JSON dump
"""
import json
from datetime import datetime
from collections import defaultdict

type_map = {
    1: "文字", 6: "文件", 19: "转发记录", 33: "链接",
    36: "语音", 47: "表情", 49: "转发", 51: "视频",
    53: "接龙", 57: "聊天卡片", 62: "拍一拍",
    2000: "转账", 2001: "红包"
}

# 禁止从这些 type 的 content 中推断 sender
NO_INFERRED_SENDER_TYPES = {19, 57, 33, 53, 62, 2000, 2001, 49, 51}

with open(r'C:\Users\OK\Desktop\wechat_v4_export\m65_by_conversation.json', encoding='utf-8') as f:
    raw = json.load(f)

# 按会话处理
all_sessions = []

for session_name, session in raw.items():
    msgs = session.get('messages', [])

    chat_msgs = []
    for m in msgs:
        msg_type = m.get('type', 0)

        # 只有明确有发送者的才加入
        sender = m.get('wxid', '')
        if not sender and msg_type not in NO_INFERRED_SENDER_TYPES:
            sender = m.get('inferred_sender', '')

        if not sender:
            continue  # 没有发送者，跳过

        content = m.get('content', '')
        ts = m.get('timestamp', 0)

        # 对于 type=19，content 里是多行转发内容，只保留第一行作为概要
        if msg_type in NO_INFERRED_SENDER_TYPES:
            first_line = content.split('\n')[0][:60]
            content = f"[{type_map.get(msg_type, msg_type)}] {first_line}"

        chat_msgs.append({
            'sender': sender,
            'content': content,
            'timestamp': ts,
            'type': msg_type,
            'type_txt': type_map.get(msg_type, str(msg_type)),
            'date': m.get('date', '')
        })

    if chat_msgs:
        chat_msgs.sort(key=lambda x: x['timestamp'] if x['timestamp'] else 0)
        all_sessions.append((session_name, chat_msgs))

# 输出 chat.md
with open(r'C:\Users\OK\Desktop\wechat_v4_export\m66_chat.md', 'w', encoding='utf-8') as f:
    total_chat_msgs = 0

    for session_name, msgs in sorted(all_sessions, key=lambda x: len(x[1]), reverse=True):
        f.write(f"\n---\n")
        f.write(f"# {session_name}\n\n")

        current_date = None
        for m in msgs:
            msg_date = m['date'][:10] if m['date'] else ''
            msg_time = m['date'][11:16] if m['date'] else ''

            # 日期分隔
            if msg_date and msg_date != current_date:
                f.write(f"\n**{msg_date}**\n\n")
                current_date = msg_date

            sender = m['sender']
            content = m['content']
            f.write(f"{sender} ({msg_time}):\n")
            f.write(f"> {content}\n\n")
            total_chat_msgs += 1

    f.write(f"\n---\n共 {total_chat_msgs} 条消息，{len(all_sessions)} 个会话\n")

with open(r'C:\Users\OK\Desktop\wechat_v4_export\m66_chat_stats.txt', 'w', encoding='utf-8') as f:
    f.write(f"会话重建结果\n{'='*40}\n")
    f.write(f"总消息数: {sum(len(m) for _, m in all_sessions)}\n")
    f.write(f"总会话数: {len(all_sessions)}\n\n")
    for name, msgs in sorted(all_sessions, key=lambda x: len(x[1]), reverse=True):
        f.write(f"  {name}: {len(msgs)} 条\n")

print(f"输出: m66_chat.md + m66_chat_stats.txt")
print(f"会话: {len(all_sessions)}, 消息: {sum(len(m) for _, m in all_sessions)}")
