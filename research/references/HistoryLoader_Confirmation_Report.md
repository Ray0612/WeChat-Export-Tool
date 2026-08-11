# HistoryLoader 确认报告 / Hook 可行性评估

## GetPagedMessages 最终结论

### 它是什么？

**日志字符串**，来自微信内部 `MessageList` 模块中的一个函数（或一组函数）。

证据：
- 位于 `.rdata` 段（只读数据，所有 log 字符串的位置）
- 同区域有完整函数链：`GetInitialMessages` → `GetPagedMessages` → `GetPagedMessages has messages`
- 附近有参数名：`, last:`、`, session:`、`, scenes:`、`msgsvrid`、`chat_id`
- 附近有同模块的其他函数：`GetAddSendMessageToDb`、`CoPrepareShowMessage`

### 它不是符号名

GetPagedMessages 是日志输出中的函数名标记（类似 `__FUNCTION__`），不是导出函数名。

### 它是否对应真正的翻页函数？

**高度可能。** 日志格式 `GetPagedMessages` + `, last:` + `has messages:` 表明这是一个调试日志：

```
[ModuleName::GetPagedMessages] session=xxx, last=xxx
[ModuleName::GetPagedMessages] has messages: 20
```

`last` 参数是翻页游标（分页的锚点）。

### Xref 分析结果

| 方法 | 结果 | 原因 |
|------|------|------|
| 搜索绝对地址引用 | 0 处 | x64 使用 RIP-relative |
| 搜索 LEA RIP-relative | 0 处 | 可能使用日志消息表（message table）|
| 同时搜索 5 个相邻字符串 | 全部 0 处 | 同上 |

推测：Weixin.dll 使用**日志消息表机制**（Visual C++ `LOG_MESSAGE_TABLE`），字符串通过索引引用，而非直接地址。完整的 xref 分析需要 IDA/Ghidra。

---

## 模块边界确认

基于同区域的字符串聚类，确认 `MessageList` 模块覆盖：

```
偏移范围: 0x83e3500 - 0x83e3850
模块名: MessageList (或 MessageManager)

函数清单（从日志字符串还原）:
  GetMessageListBySvrIds         → 按服务器 ID 查询
  GetInitialMessages             → 首次加载消息
  GetPagedMessages               → 分页加载历史消息
  GetInitialBrandNotifyMessages  → 服务号消息
  GetPagedBrandNotifyMessages    → 服务号分页
  StartSendMessageSyncStage      → 发送同步
  GetAddSendMessageToDb          → 写入数据库
  CoPrepareShowMessage           → 准备显示
  CheckMessageLiveStatus         → 检查消息状态
  GetAllLiveItem / GetLiveStatus → 直播相关
```

**参数模型（推测）:**

```
GetPagedMessages(
  session_id: string,    // 会话标识
  last_msg_id: uint64,   // 游标（最后一条消息的ID）
  limit: uint32,         // 页大小（默认20?）
  direction: enum        // 翻页方向
) → MessageList
```

---

## 调用链方向

```
用户滚动聊天窗口
    ↓
RecyclerList (检测到滚动到底部/顶部)
    ↓
ChatView (触发加载更多)
    ↓
MessageList.GetPagedMessages(session, last, limit)
    ↓
MsgCache / AppMsg (检查本地缓存)
    ↓
网络同步 (从服务器拉取)
    ↓
返回 Message 列表
    ↓
CompactStruct (34B 每条) 写入本地缓存
    ↓
UI 渲染
```

**GetPagedMessages 属于 MessageList 层**，介于 UI 和网络/缓存之间。

---

## Hook 可行性评估

| 方面 | 评估 |
|------|------|
| 稳定性 | ⭐⭐⭐ 函数名出现在日志中，说明它是实际调用的路径 |
| 有利因素 | 结构稳定（日志字符串 = 代码真实路径） |
| 有利因素 | 参数 `last:` 有助于游标翻页 |
| 有利因素 | 同模块有 `GetAddSendMessageToDb`，可同时拦截持久化 |
| 不利因素 | 需要先定位函数入口（需要 IDA 分析） |
| 不利因素 | 函数可能内联（inline），实际符号可能不同 |

### 三种导出方案对比

| 方案 | 优点 | 缺点 | 推荐度 |
|------|------|------|--------|
| A: Hook GetPagedMessages | 直接拦截翻页、ProtoBuf 格式、不需要解析结构 | 需要 IDA 定位函数地址 | ⭐⭐⭐ |
| B: 扫描紧凑结构 | 不需要逆向、纯读内存、已验证可行 | 只有 ~25 条、需要翻页 | ⭐⭐ |
| C: Hook MessageListToDB | 拦截持久化路径 | 格式未知、可能批量写入 | ⭐ |

**推荐：路径 A + B 结合**
- 用 B 扫描当前可见消息（快速导出已有缓存）
- 用 A hook GetPagedMessages 翻页（深度导出历史）

---

## 下一阶段建议

1. 用 IDA/Ghidra 分析 0x83e3500-0x83e3900 区域的字符串引用
2. 找到 GetPagedMessages 所在函数的实际入口地址
3. 验证参数模型（`session + last + limit`）
4. 如果用方案 A，编写 Frida 脚本 hook 该函数
