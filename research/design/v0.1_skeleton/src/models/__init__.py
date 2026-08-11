"""
微信聊天记录数据模型。
V0.1 仅包含紧凑结构可提取的字段。
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Message:
    """
    微信聊天消息。

    V0.1 保证字段（紧凑结构直接提取）:
        sequence, content, session_tag, user_id

    可选增强字段（需额外扫描）:
        receiver, timestamp, chatroom_id, chatroom_name
    """
    sequence: int              # 同会话内序号，逐条+1
    content: str               # 消息文本（UTF-8/ASCII）
    session_tag: str           # 会话标识（9e 96 xx 的 hex 值）
    user_id: str = ""          # 用户标识（6a 22 5e xx 的 hex 值）

    # 可选增强字段
    receiver: str = ""         # TODO: 从记录区 0x73 提取
    timestamp: int = 0         # TODO: 从 ProtoBuf field4 提取
    chatroom_id: str = ""      # TODO: 从记录区 0x76 提取
    chatroom_name: str = ""    # TODO: 从记录区 0x77 提取


@dataclass
class Session:
    """
    消息会话。
    """
    session_tag: str           # 紧凑结构中的会话标识
    name: str = ""             # 会话显示名
    messages: list = field(default_factory=list)    # 消息列表（按 sequence 排序）
    message_count: int = 0     # 消息总数

    @property
    def first_sequence(self) -> int:
        return self.messages[0].sequence if self.messages else 0

    @property
    def last_sequence(self) -> int:
        return self.messages[-1].sequence if self.messages else 0


@dataclass
class ExportResult:
    """
    导出结果汇总。
    """
    export_time: str                    # 导出时间
    wechat_version: str                 # 微信版本号
    data_source: str                    # 数据来源
    sessions: list[Session]             # 导出的会话列表
    total_messages: int = 0
    failed_parses: int = 0
    cache_pages_found: int = 0
    warnings: list[str] = field(default_factory=list)
