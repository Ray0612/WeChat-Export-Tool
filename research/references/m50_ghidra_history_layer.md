# M50 — Find History Layer (Ghidra Task)

## 目标

找到真正的历史消息存储层（不是 0x2d8/39B 等缓存）。

## Task 1: GetMessageListBySvrIds 的 Caller Tree

对 FUN_1816f3b30 做 References → Show References to Address (CALL 类型)。记录每一层调用者，向上追到 ConversationManager 级别。

```
GetMessageListBySvrIds
  ← ???
    ← ???
      ← ConversationManager?
```

## Task 2: 搜索历史层相关字符串

搜以下字符串附近的函数：
- `SvrId` / `MsgId` / `LocalId`
- `Conversation` / `Session`
- `History` / `MessageList`
- `Repository` / `Storage`

## Task 3: 找长生命周期容器

搜 `std::map` / `unordered_map` / `hash table` 特征。找持有几千上万条消息的容器（不是只持有一页的）。

## Task 4: 追踪 SvrIds 来源

FUN_1816f3b30 的第一个参数通常是 SvrIds 列表。这个列表从哪里来？谁持有它？

## 输出

```
Caller Tree: [3层以上]
History Container: [类型 + 位置]
Message Count: [估计]
```
