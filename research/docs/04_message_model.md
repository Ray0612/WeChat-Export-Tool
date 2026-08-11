# 微信 4.1.9.56 消息对象模型

## 确认状态

### ✅ 完全确认的字段

| 字段 | 类型 | 证据 |
|------|------|------|
| **content** | string | 3 种格式均发现明文消息内容 |
| **sequence** | uint16 | 30 条消息验证，同会话内每条 +1 |
| **receiver** | string | ProtoBuf + 结构化记录区 0x73 |
| **chatroom_id** | string | 结构化记录区 0x76 |
| **chatroom_name** | string | 结构化记录区 0x77（中文 UTF-8）|

### ⚠️ 部分确认的字段

| 字段 | 类型 | 说明 |
|------|------|------|
| **user_id** | ? | 紧凑结构中 `6a 22 5e` 常量，所有消息共有 |
| **session_tag** | ? | 紧凑结构中 `9e 96 40/41`，可能标识会话 |
| **msg_id (field4)** | uint64? | ProtoBuf 中 `20` 标记，但数值不稳定 |

---

## 格式A：紧凑消息结构

在堆内存中找到的消息对象数组。**这是最可靠的消息来源。**

### 结构图

```
偏移  内容                                   说明
+0    1b 02 05 09 01 01 04                   7字节前缀（固定）
+7    48 45 4c 4c 4f 5f 31                   消息内容 (HELLO_1)
+14   04                                      分隔符（固定）
+15   4b 01                                   序列号（小端序 uint16）
+17   9e 96 40 [或 9e 96 41]                  会话标记
+20   8字节指针                               堆地址
+28   6a 22 5e XX                             用户标识
+32   81 be                                   尾部标记
```

### 消息间距

每条消息 **34 字节**（content 到下一个 content）。

### 序列号验证

在同会话（文件传输助手）中，序列号严格递增 1：

| 消息 | 序列号 hex | 序列号 dec | 确认方式 |
|------|-----------|-----------|----------|
| TEST_AAAAA_11111 | 4a 01 | 330 | 直接读取 |
| HELLO_1 | 4b 01 | 331 | 直接读取 |
| HELLO_2 | 4c 01 | 332 | 直接读取 |
| HELLO_3 | 4d 01 | 333 | 直接读取 |
| HELLO_4 | 4e 01 | 334 | 直接读取 |
| HELLO_5 | 4f 01 | 335 | 直接读取 |
| A1-A5 | — | 336-340 | 推断（不在当前内存页） |
| MSG_001 | 55 01 | 341 | 直接读取 |
| MSG_002 | 56 01 | 342 | 直接读取 |
| MSG_003 | 57 01 | 343 | 直接读取 |
| MSG_004 | 58 01 | 344 | 直接读取 |
| MSG_005 | 59 01 | 345 | 直接读取 |
| MSG_006 | 5a 01 | 346 | 直接读取 |
| MSG_007 | 5b 01 | 347 | 直接读取 |
| MSG_008 | 5c 01 | 348 | 直接读取 |
| MSG_009 | 5d 01 | 349 | 直接读取 |
| MSG_010 | 5e 01 | 350 | 直接读取 |

**结论：sequence 是同会话内的连续序号，新消息 = 上一序号 + 1。**

---

## 格式B：ProtoBuf 消息结构

找到的 ProtoBuf 格式消息，字段如下：

```
msg {
    field1 = 1          → 消息类型
    field2 = SubMsg {
        receiver        → 接收者 wxid 或 "filehelper"
        content         → 消息文本
    }
    field3 = 1          → 子类型标记
    field4 = ?          → MsgID？（未验证）
    field5 = ?          → 时间戳 / 其他ID？（未验证）
    field6 = msgsource  → XML 元数据
}
```

### 格式B 中的已知字段与格式A 的对应关系

| 格式B (ProtoBuf) | 格式A (紧凑) | 确认度 |
|-----------------|-------------|--------|
| SubMsg.content | content | ✅ 相同 |
| SubMsg.receiver | — | ✅ 仅 ProtoBuf 有 |
| — | sequence | ✅ 仅紧凑结构有 |
| — | 6a 22 5e | ✅ 仅紧凑结构有 |

**ProtoBuf 和紧凑结构是同一消息对象的不同序列化形式。** ProtoBuf 用于传输/持久化，紧凑结构用于在内存中快速访问（消息列表缓存）。

---

## 格式C：结构化记录区

键值存储区，将消息关联到联系人/群聊信息。

| 键码 | 含义 | 示例值 | 确认度 |
|------|------|--------|--------|
| 0x73 | receiver_wxid | `wxid_049vxvhc4asy22` | ⭐⭐⭐ |
| 0x76 | chatroom_id | `47646221656@chatroom` | ⭐⭐⭐ |
| 0x77 | chatroom_name | `科技1班班委群` | ⭐⭐⭐ |

---

## 最终消息对象模型

```python
class WeChatMessage:
    # 已确认
    content: str          # 消息文本
    sequence: int         # 同会话内序列号
    receiver: str         # 接收者 wxid
    
    # 部分确认
    user_id: bytes        # 紧凑结构中的 6a 22 5e 常量
    session_tag: bytes    # 紧凑结构中的 9e 96 40/41
    
    # ProtoBuf 来源（待验证）
    msg_id: int           # ProtoBuf field4
    timestamp: int        # ProtoBuf field5
    source_meta: str      # ProtoBuf field6 msgsource
    
    # 记录区来源（条件性存在）
    chatroom_id: str      # 群聊时存在
    chatroom_name: str    # 群聊时存在
```

## 消息存储逻辑（推测）

```
用户发送/接收消息
    ↓
创建 ProtoBuf 格式（含完整字段）
    ↓
ProtoBuf → 紧凑结构（34字节/条，倒序排列）
    ↓
关联消息到联系人/群聊（结构化记录区）
    ↓
紧凑结构是"可见消息缓存"——仅保留当前会话可见的消息
翻页加载更多时，旧消息进入独立缓存页
ProtoBuf 格式可能随消息移出可见区域而被回收
```
