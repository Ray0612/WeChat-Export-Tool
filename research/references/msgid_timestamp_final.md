# MsgID / Timestamp 最终验证

## 结论

### ✅ field4 = Timestamp（高置信度）

验证数据：

| 消息 | 发送时间 | field4 值 | 差值 |
|------|----------|-----------|------|
| TIME_TEST_A | 13:47:35 | 1,780,638,454 | - |
| TIME_TEST_B | 13:47:45 | （未读到） | - |
| TIME_TEST_C | 13:47:55 | 1,780,638,474 | +20 |

**field4 在 20 秒间隔内从 1,780,638,454 → 1,780,638,474，差值为 20，精确匹配时间间隔。**

### ❌ field5 = 非时间戳

| 消息 | field5 值 | 说明 |
|------|-----------|------|
| TIME_TEST_A | 3,730,862,404 | 未确认 |
| TIME_TEST_C | 2,715,649,811 | 与 A 不连续，非时间戳 |

---

## Message Model V1（最终版）

```python
class WeChatMessage:
    # ⭐⭐⭐ 完全确认（多种格式交叉验证）
    content: str            # 消息文本
    sequence: int           # 同会话内序列号（逐条+1）
    receiver: str           # 接收者 wxid / "filehelper"
    timestamp: int          # Unix 秒级时间戳（field4）
    
    # ⭐⭐ 较强确认（至少两种证据）
    user_id: bytes          # 紧凑结构常量 6a 22 5e
    session_tag: bytes      # 紧凑结构常量 9e 96 40/41
    
    # ⭐⭐ 条件性确认（仅对群聊/特定消息存在）
    chatroom_id: str        # 群聊 ID（来自记录区 0x76）
    chatroom_name: str      # 群聊名称（来自记录区 0x77）
    
    # ⭐ 低置信度/待验证
    msg_id: int?            # field5（可能是服务器 MsgID，未验证模式）
    source_meta: str        # msgsource XML（格式B field6）
```

## 已确认字段之间的关联

```
content + timestamp + sequence + receiver
    ↓                    ↓
"HELLO_1"  +  1780638470  +  331  +  "filehelper"
```

**四次实验验证了 7 个字段，达到 Message Model V1 完成标准。**
