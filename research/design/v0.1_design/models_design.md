# V0.1 数据模型设计

## Message

```python
@dataclass
class Message:
    """
    微信聊天消息。
    V0.1 只保证 compact 结构中的字段。
    """
    sequence: int           # 同会话内序号，逐条+1（来源：紧凑结构偏移+15）
    content: str            # 消息文本（来源：紧凑结构偏移+7，UTF-8/ASCII）
    session_tag: str        # 会话标识（来源：紧凑结构 `9e 96 xx` 的 hex 值）
    user_id: str            # 用户标识（来源：紧凑结构 `6a 22 5e` 的 hex 值）
    
    # V0.1 可选增强字段（从记录区关联获取）
    receiver: str = ""      # 接收者 wxid（来源：记录区 0x73 标记）
    timestamp: int = 0      # 时间戳（来源：后续从 ProtoBuf 提取）
    chatroom_id: str = ""   # 群聊 ID（来源：记录区 0x76 标记）
    chatroom_name: str = "" # 群聊名称（来源：记录区 0x77 标记）
```

## Session

```python
@dataclass
class Session:
    """
    消息会话。
    V0.1 基于 session_tag 自动聚类。
    """
    session_tag: str        # 紧凑结构中的 `9e 96 xx` 标识
    name: str               # 会话显示名（默认 "session_{tag}"，可关联后更新）
    messages: list[Message] # 该会话中的消息列表（按 sequence 排序）
    message_count: int = 0  # 消息总数
    
    @property
    def first_sequence(self) -> int:
        return self.messages[0].sequence if self.messages else 0
    
    @property
    def last_sequence(self) -> int:
        return self.messages[-1].sequence if self.messages else 0
```

## ExportResult

```python
@dataclass
class ExportResult:
    """
    导出结果汇总。
    记录导出过程中的关键信息。
    """
    export_time: str                # 导出时间
    wechat_version: str             # 微信版本号
    data_source: str                # 数据来源（"memory_scan_v0.1"）
    
    sessions: list[Session]         # 导出的会话列表
    total_messages: int = 0         # 总消息数
    failed_parses: int = 0          # 解析失败数
    cache_pages_found: int = 0      # 找到的缓存页数
    
    warnings: list[str] = None      # 警告信息
```

## V0.1 字段填充矩阵

| Message 字段 | 紧凑结构 | 记录区 | ProtoBuf | V0.1 实现 |
|-------------|----------|--------|----------|-----------|
| sequence | ✅ 直接 | - | - | ✅ 直接提取 |
| content | ✅ 直接 | - | - | ✅ 直接提取 |
| session_tag | ✅ 直接 | - | - | ✅ 直接提取 |
| user_id | ✅ 直接 | - | - | ✅ 直接提取 |
| receiver | - | ✅ 0x73 | ✅ field2 | ⚠️ 可选 |
| timestamp | - | - | ✅ field4 | ❌ 暂无 |
| chatroom_id | - | ✅ 0x76 | - | ⚠️ 可选 |
| chatroom_name | - | ✅ 0x77 | - | ⚠️ 可选 |
