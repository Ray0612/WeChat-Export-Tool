# M52 — 历史层核心抓取指导

## 目标
找到管理全部历史消息的容器（MessageStore / Conversation / MessageList），不再纠结 Creator 或 0x2d8 临时结构。

## 核心思路
不再追 Creator，而是追 GetMessageListBySvrIds 的 SvrId 集合来源。

## 步骤

### 1. 明确现有链路
```
Caller1 → GetPagedMessages → FUN_1816c2a20 (0x2d8 遍历) → MessageNode
```
这条链路只暴露翻页缓存，不包含完整历史。

### 2. 聚焦 SvrId 集合
- GetMessageListBySvrIds 每次调用都传入 SvrIds
- SvrIds 的来源很可能是 Conversation / MessageStore / HistoryCache
- 找到 SvrIds 的持有者 = 找到历史层

### 3. 动态分析
- Hook FUN_1816f3b30 入参 SvrIds
- 追踪 SvrIds 所在内存结构的拥有者
- 观察容器大小（1000+ 条则可能是历史层）
- 验证是否包含 seq / msgsource / receiver

### 4. 不建议的方向
- Hook WeChatAppEx.exe / Chromium
- 继续追 Creator 的触发条件
- 追踪 0x2d8 分配逻辑

### 5. 输出目标
- 找到 MessageStore / ChatSession 全量节点
- 每个节点包含：receiver / content / seq / msgsource
- 为导出器提供全量历史快照
