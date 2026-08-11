# M7.5 — MessageList Manager Exploration V1

> 实验时间：2026-06-06
> 方法：Frida Hook onEnter，dump arg0 (MessageList Manager) 的 0x1000 字节 + QWord 指针遍历
> 实验覆盖：同一会话翻页 + 切换联系人

---

## 核心发现

### 1. arg0 在同一会话内完全不变

同一会话内 5 次 GetPagedMessages 调用，arg0 的 4096 字节 **0 差异**。

### 2. 切换会话后仅有 28-31 字节变化

| 区域 | 变化量 | 含义 |
|------|--------|------|
| +0xb68~0xb73 | 两个 8 字节指针 | Session 连接对象 |
| +0xf50~0xf57 | 8 字节指针 → `0xffffffffffffffff` | 指针清零/替换 |
| +0xf6f~0xf7d | 指针 + 编码数据 | Session Key 变化 |
| +0xfef~0xffc | 标志位 | 会话状态 |

### 3. arg0 不包含消息列表

遍历前 64 个 QWord（前 0x200 字节）也未发现：
- ❌ 消息文本
- ❌ wxid 字符串
- ❌ @chatroom 标识
- ❌ ProtoBuf 特征
- ❌ 紧凑结构前缀 `1b 02 05 09`

arg0 内部主要是：0、1、7、8、0xFFFFFFFF 等常量和几个指针。

### 4. arg0 包含数据库 Schema 引用

在偏移 +0xf90 附近发现 SQL 字符串：
```
"create_time" "INTEGER"
"status"      "INTEGER"
```

这些是数据库表定义片段，说明 arg0 引用了**离线存储的数据库 schema**，
但不存储消息数据本身。

### 5. 发现 Session Key 编码数据

在 +0xe10 附近有一段 ~247 字节的 base64-like 编码数据，长度随会话切换变化。
解码后为二进制数据，非纯文本。可能是 Session ID 或连接参数的编码。

---

## 结论

**arg0 (MessageList Manager) 不是消息列表缓存。** 它是一个会话/配置管理器，包含：
- 会话连接对象（指针）
- 数据库 schema 引用
- Session 编码数据
- 状态标志

但**不存储消息数据**。

---

## 当前已知数据流模型（更新版）

```
物理 PageUp 翻页
    ↓
GetPagedMessages (FUN_1816ade70)
    ├── arg0 = Manager (会话配置, 翻页不变, 切换会话微变)
    ├── arg1 = GlobalContext (返回 retval, +0x000/+0x008 更新)
    │     ├── +0x000 → PTR0: Page Context (页面元数据 + 消息计数)
    │     └── +0x008 → PTR8: Rendering Buffer (Qt 纹理缓存)
    ├── arg2 = PagingContext (wxid, cursor, counter)
    └── retval = arg1 (确认)
    ↓
[副作用] 消息数据写入内部存储 (位置未知)
    ↓
UI 从内部存储读取 → 渲染 → 显示
```

## 消息数据可能位置（重新评估）

| 位置 | 探索状态 | 结论 |
|------|---------|------|
| arg0 (Manager) | ✅ M7.5 | ❌ 不包含 |
| arg1 (GlobalContext) | ✅ M7 | ❌ 不包含 |
| arg2 (PagingContext) | ✅ M5 | ❌ 元数据 |
| retval | ✅ M6 | ❌ = arg1 |
| **紧凑结构 (34B)** | ✅ M1 | **✅ 有 content+sequence，但仅 ~25 条易失** |
| **离线存储** | 🟡 未定位 | 离线翻页证实存在，但 35063 文件 0 匹配 |
| **GetPagedMessages 堆内部分配** | 🟡 未探索 | Ghidra 分析函数内部消息处理 |

## 下一步建议

| 优先级 | 方向 | 说明 |
|--------|------|------|
| **P0** | **GetPagedMessages 内部 Hook** | 在函数内部找处理消息的子函数，Hook 分配消息对象的点 |
| **P0** | **紧凑结构扫描导出器** | 虽然有限制(~25条/易失)，但这是目前唯一已知可提取消息内容的方式 |
| **P1** | **离线存储全盘扫描** | 搜索非标准扩展名、ProcMon 捕获完整文件系统访问 |
| **P2** | **GetInitialMessages Hook** | 另一个入口函数，可能在初始化时返回消息列表 |
