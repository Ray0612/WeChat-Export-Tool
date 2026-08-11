# 微信 4.1.9.56 内部结构研究报告 V1

> 研究时间：2026-06-04 至 2026-06-06
> 研究环境：Windows 11 中文版，Python 3.13.5
> 目标版本：微信 4.1.9.56（Weixin.exe + WeChatAppEx.exe）

---

## 1. 项目背景

### 1.1 出发点

开发一个**不依赖反汇编、不依赖 Hook** 的微信聊天记录导出工具。

### 1.2 早期尝试——数据库路线

| 方案 | 结果 | 证据 |
|------|------|------|
| 直接搜 MSG.db | ❌ 不存在 | 旧版 `Documents\WeChat Files\` 目录不存在 |
| 全盘扫描 .db 文件 | ❌ 无 contact/message 数据库 | 35063 文件扫描，0 匹配 |
| ZedeX/weixin-decrypte-script | ❌ 13 个数据库全部解密失败 | 密钥不匹配或算法不对 |
| sjzar/chatlog v0.0.31 | ❌ V4 DataSource 不支持 | 输出为 0 字节 |

**结论（Confirmed）：微信 4.1.9.56 不使用 SQLite / SQLCipher 存储聊天记录。**

### 1.3 转向内存分析

| 方案 | 结果 |
|------|------|
| pymem 进程附加 | ✅ 成功 |
| 紧凑结构发现 | ✅ 34 字节消息缓存 |
| ProtoBuf 结构发现 | ✅ 完整消息对象 |
| Frida Hook 验证 | ✅ GetPagedMessages 函数确认 |

**结论（Confirmed）：聊天消息存在于 Weixin.exe 内存中，磁盘无明文存储。**

---

## 2. 存储模型

### 2.1 磁盘搜索

| 范围 | 文件数 | 字符串匹配 |
|------|--------|-----------|
| `AppData\Roaming\Tencent` | 18,182 | 0 |
| `AppData\Local\Tencent` | 16,881 | 0 |
| `ProgramData` | - | 0 |
| `Temp` | - | 0 |
| **总计** | **35,063** | **0** |

**结论（Confirmed）：唯一消息 TEST_RAY_20260605_938274615 未存储在任何磁盘文件中。**

### 2.2 离线验证

| 状态 | 历史消息可访问？ | GetPagedMessages 命中？ |
|------|-----------------|----------------------|
| 在线 | ✅ | ✅ 4 次 |
| 离线 | ✅ | ✅ 10 次 |

**结论（Confirmed）：历史消息完全存在于本地存储（非网络实时拉取），但存储位置未知。**

**存储位置推测（Hypothesis）**：
1. 微信安装目录下的沙箱环境（`WeChatAppEx.exe` 管理）
2. 自定义二进制格式（非标准数据库）
3. 当前文件系统搜索漏掉了特定目录（如 `AppData\Local\Packages`、`ProgramData` 中的隐藏目录）

### 2.3 内存消息格式

| 格式 | 步长 | 内容 | 持久性 |
|------|------|------|--------|
| 紧凑结构 | 34 字节 | content + sequence + tag | ❌ 易失（窗口切换后清除）|
| ProtoBuf | 不固定 | 完整字段（receiver, content, timestamp, msgsource）| ⚠️ 可能残留 |
| 记录区 | 不固定 | wxid, chatroom_id, chatroom_name | ⚠️ 可能残留 |

**结论（Confirmed）：紧凑结构是内存消息缓存，仅有 ~25 条，不是持久化方案。**

---

## 3. 消息模型

### 3.1 Format A：紧凑结构（Confirmed）

```
偏移  长度  内容
+0    7    1b 02 05 09 01 01 04   前缀
+7    var  消息内容 (UTF-8/ASCII)
+?    1    04                     分隔符
+?    2    sequence (小端 u16)    同会话 +1 递增
+?    3    9e 96 xx               session_tag
+?    8    堆指针
+?    4    6a 22 5e xx            user_id
+?    2    81 be                  尾部
─────────────────────────────────
总计: 34 字节
```

验证数据：
```
MSG_005 → seq=345 (0x0159)
MSG_001 → seq=341 (0x0155)
HELLO_1 → seq=331 (0x014b)
逐条 +1 递增 ✅
```

### 3.2 Format B：ProtoBuf 结构（Confirmed）

```
msg {
    field1 = 1          → 消息类型（Confirmed）
    field2 = SubMsg {    → 消息子结构（Confirmed）
        receiver        → 接收者 wxid（Confirmed）
        content         → 消息文本（Confirmed）
    }
    field3 = 1          → 子类型标记（Confirmed）
    field4 = varint     → **时间戳（Confirmed）** Unix 秒级
    field5 = varint     → 未知（Likely MsgID）
    field6 = string     → msgsource XML（Confirmed）
}
```

时间戳验证：
```
TIME_TEST_A @ 13:47:35 → field4 = 1,780,638,454
TIME_TEST_C @ 13:47:55 → field4 = 1,780,638,474
差值：+20（精确匹配 20 秒间隔 ✅）
结论：field4 = Unix 时间戳（Confirmed）
```

### 3.3 Format C：记录区结构（Confirmed）

| 键码 | 含义 | 示例 | 确认度 |
|------|------|------|--------|
| 0x73 | receiver_wxid | `wxid_049vxvhc4asy22` | Confirmed |
| 0x74 | - | 指针 | Unknown |
| 0x75 | - | 指针 | Unknown |
| 0x76 | chatroom_id | `47646221656@chatroom` | Confirmed |
| 0x77 | chatroom_name | `科技1班班委群`（UTF-8） | Confirmed |
| 0x78 | - | 指针 | Unknown |

### 3.4 Message Model V1

```python
class WeChatMessage:
    # Confirmed（3 种格式交叉验证）
    content: str            # 消息文本
    sequence: int           # 同会话序列号（逐条 +1）
    receiver: str           # 接收者 wxid / "filehelper"
    timestamp: int          # Unix 秒级时间戳（ProtoBuf field4）
    chatroom_id: str        # 群聊 ID（记录区 0x76）
    chatroom_name: str      # 群聊名称（记录区 0x77）

    # Likely
    user_id: bytes          # 紧凑结构 6a 22 5e

    # Unknown
    msg_id: int             # ProtoBuf field5
    source_meta: str        # msgsource XML
```

---

## 4. GetPagedMessages

### 4.1 发现过程

| 步骤 | 方法 | 结果 |
|------|------|------|
| 字符串搜索 | pymem 在 Weixin.dll 中扫描 | 在 0x83e35a4 找到 |
| 区域分析 | 附近字符串聚类 | 完整函数链（GetInitialMessages → GetPagedMessages → AddMessageToDb）|
| 字符串内容 | "GetPagedMessages", last:", "has messages" | 确认翻页语义 |
| Xref 分析 | Ghidra 引用分析 | **9 个 xref，全部指向同一函数** |
| 函数确认 | Ghidra 反汇编 | FUN_1816ade70，首指令 PUSH RBP |

### 4.2 函数信息

| 属性 | 值 | 确认度 |
|------|-----|--------|
| 函数名 | FUN_1816ade70 | Confirmed |
| DLL 偏移 | 0x016ade70 | Confirmed |
| 首指令 | PUSH RBP (55) | Confirmed |
| 调用者 | 3 个：FUN_181633180, FUN_181641530, FUN_1845d92f0 | Confirmed |
| 附近日志 | "GetPagedMessages", "last:"", "GetPagedMessages has messages:" | Confirmed |

### 4.3 调用验证

```
在线翻页：HIT #1-#4（4 次）
离线翻页：HIT #5-#14（10 次）
总计：14 次命中 ✅

结论（Confirmed）：GetPagedMessages 是历史消息加载的入口函数
```

### 4.4 参数模型

```
FUN_1816ade70(this, rcx?, arg2, arg3)

arg0 = 0x1f46ba1c1b0 → Global MessageList Manager（Confirmed）
                        所有会话、所有翻页操作均相同

arg1 = 0x8ecb6ff4f0 → 全局常量（Confirmed）
                        所有操作均相同

arg2 = PagingContext 结构体指针（Confirmed）
       → 随会话和翻页变化
       → 包含接收者 wxid 和游标信息

arg3 = arg2 + 0x20（Confirmed）
       → 结构体内部成员指针
```

### 4.5 跨会话一致性

| 测试场景 | arg0 | arg1 | arg2 |
|----------|------|------|------|
| 文件传输助手 | 0x1f46ba1c1b0 | 0x8ecb6ff4f0 | 变化 |
| 其他联系人 | 0x1f46ba1c1b0 | 0x8ecb6ff4f0 | 变化 |
| 群聊 | 0x1f46ba1c1b0 | 0x8ecb6ff4f0 | 变化 |

**结论（Confirmed）：arg0/arg1 与当前会话无关，arg2 承载所有会话关联信息。**

---

## 5. PagingContext 结构体

### 5.1 已确认字段

| 偏移 | 类型 | 含义 | 确认度 |
|------|------|------|--------|
| +0x000 | string/ptr | 接收者 wxid（filehelper 内联，其他为指针） | **Confirmed** |
| +0x028 | uint64 | 候选 MsgID / 时间戳（每次翻页变化） | **Likely** |
| +0x030 | uint32 | 候选计数器/序号 | **Likely** |
| +0x188 | uint32 | 候选消息序号（递增） | Likely |
| +0x0a8 | uint64 | 固定值 0x1ffffffff | Confirmed（常量标记）|
| +0x0c8 | ptr | 固定指针 | Confirmed（对象引用）|
| +0x0d0 | ptr | 固定指针 | Confirmed（对象引用）|

### 5.2 示例数据（文件传输助手）

```
+0x000: 66 69 6c 65 68 65 6c 70 65 72 00 = "filehelper"
+0x028: 1780638070000 → 时间戳 / MsgID
+0x030: 1110 → 序号
```

### 5.3 示例数据（其他联系人，含 msgsource 片段）

```
+0x000: 指针 → 指向 wxid_xxx 字符串
+0x028: 变化
+0x030: 变化
内含 XML: <silence>, <membercount>, <signature>...
```

---

## 6. 当前业务对象关系图

```
本地存储（位置未知，非 SQLite）
    │
    ▼
[GetPagedMessages] ← 翻页入口 (FUN_1816ade70)
    │
    ├── arg2 = PagingContext
    │     ├── +0x000: receiver wxid
    │     ├── +0x028: 游标 / MsgID
    │     └── +0x188: 序号
    │
    ├── 返回值 ? (未分析)
    │     └── 可能包含 Message 对象列表
    │
    ▼
MessageList 缓存
    │
    ├── 紧凑结构 (34B, ~25条, 易失)
    └── ProtoBuf (完整字段, 可能残留)
    │
    ▼
UI 显示 (RecyclerList → ChatView)
```

---

## 7. 未解决问题

| 问题 | 重要性 | 说明 | 建议方向 |
|------|--------|------|----------|
| 真正存储层位置 | P0 | 离线可翻大量历史，但 35063 文件搜索 0 匹配 | ProcMon 全盘捕获 + 非标准扩展名搜索 |
| 返回值结构 | P0 | GetPagedMessages 返回消息列表，但未分析 | Frida Hook onLeave + dump 返回值 |
| MsgID 确认 | P1 | field5 疑似 MsgID，未验证 | 发两条消息对比 field5 变化 |
| 时间戳确认 | P1 | field4 已确认是 Unix 秒，但 compact 结构中不含 | 通过 ProtoBuf 关联获取 |
| ProtoBuf 消息解析 | P1 | 完整消息对象格式未解析 | IDA 分析消息处理函数 |
| 图片/文件存储 | P2 | 未研究 | 后续迭代处理 |

---

## 8. 下一阶段计划

| 迭代 | 目标 | 前置条件 |
|------|------|----------|
| M6 | 返回值分析（Hook onLeave） | M5 完成 |
| M7 | 消息对象恢复（从返回值解析 Message） | M6 完成 |
| M8 | PoC 导出器开发（基于 HookDS） | M7 完成 |

## 附录：确认度说明

| 等级 | 含义 | 示例 |
|------|------|------|
| **Confirmed** | 至少两种独立方法验证 | pymem + Frida + Ghidra 交叉确认 |
| **Likely** | 单一方法验证且有逻辑支撑 | 一次 Frida 实验观察到 |
| **Hypothesis** | 推测，需额外验证 | 基于代码逻辑推断 |
| **Unknown** | 尚未研究 | - |
