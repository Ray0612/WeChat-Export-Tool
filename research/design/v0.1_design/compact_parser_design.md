# CompactParser 设计

## 职责

接收 34 字节的紧凑结构原始数据，解析为 Message 对象。

## 已知结构

```
偏移  长度  内容                   说明
+0    7     1b 02 05 09 01 01 04   前缀（固定标记）
+7    var   消息内容                ASCII / UTF-8 文本
+?    1     04                     分隔符
+?    2     sequence               序号（小端序 uint16）
+?    3     9e 96 XX               session_tag
+?    8     地址                   堆指针
+?    4     6a 22 5e XX            user_id
+?    2     81 be                  尾部标记
─────────────────────────────────
总计: 34 字节
```

## 接口

```python
COMPACT_PREFIX = b'\x1b\x02\x05\x09\x01\x01\x04'
ENTRY_SIZE = 34


class CompactParser:
    """
    紧凑结构解析器。
    输入：34 字节原始数据
    输出：Message 对象
    """
    
    @staticmethod
    def validate(data: bytes) -> bool:
        """
        验证数据是否合法的紧凑结构。
        检查：前缀匹配 + 34 字节长度
        """
        return len(data) == ENTRY_SIZE and data[:7] == COMPACT_PREFIX
    
    @staticmethod
    def extract_content(data: bytes) -> str:
        """
        提取消息内容。
        从偏移 +7 开始读取，直到遇到 0x04 分隔符。
        """
    
    @staticmethod
    def extract_sequence(data: bytes) -> int:
        """
        提取序列号。
        从 content 结束后的 0x04 后面 2 字节，小端序。
        """
    
    @staticmethod
    def extract_session_tag(data: bytes) -> str:
        """
        提取会话标识。
        搜索 9e 96 xx 模式，返回 hex 值。
        """
    
    @staticmethod
    def extract_user_id(data: bytes) -> str:
        """
        提取用户标识。
        搜索 6a 22 5e xx，返回 hex 值。
        """
    
    def parse_one(self, data: bytes) -> Message | None:
        """
        解析单条消息。
        返回 None 表示解析失败。
        """
    
    def parse_batch(self, data_list: list[bytes]) -> list[Message]:
        """
        批量解析多条消息。
        自动过滤无效条目。
        """
```

## 解析流程

```
parse_one(data):
  1. validate(data) → False 则返回 None
  2. extract_content(data) → content
  3. extract_sequence(data) → sequence
  4. extract_session_tag(data) → session_tag
  5. extract_user_id(data) → user_id
  6. 构建 Message(content, sequence, session_tag, user_id)
```

## 边界情况

| 情况 | 处理 |
|------|------|
| 前缀不匹配 | validate 返回 False，跳过 |
| 内容为空 | content 设为空字符串 |
| 中文内容 | UTF-8 解码，失败则用 ASCII 降级 |
| session_tag 找不到 | 设为 "unknown" |

## 验证方法

```python
# 已知正确的消息（EXPECTED 数据从实验获得）:
assert CompactParser.extract_sequence(known_msg) == 341
assert CompactParser.extract_content(known_msg) == "MSG_001"
```
