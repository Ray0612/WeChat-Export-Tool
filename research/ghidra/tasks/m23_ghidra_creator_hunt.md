# M23 — MessageNode Creator Hunt (Ghidra Task)

## 目标

在 Weixin.dll 4.1.10.29 中找到**创建或填充 0x2d8 MessageNode 的函数**。

## 背景

- MessageNode = 0x2d8 字节的消息结构体
- 关键字段偏移：+0x120(receiver), +0x268(content_ptr), +0x288(content_ptr2)
- FUN_1816c2a20 内部以步长 0x2d8 遍历数组，但它不是创建者
- 需要找到更上游的构造函数

## Task 1: 搜索 0x2d8 常量

在 Ghidra 中 Search → Program Text，搜索：
- `0x2d8`
- `728`（十进制）

记录所有引用此常量的函数。重点关注附近有 `malloc`/`new`/`HeapAlloc` 的函数。

## Task 2: 搜索结构体字段访问

搜索以下偏移值在**代码中**的出现（不是数据）：
- `0x120` — receiver 字段
- `0x268` — content_ptr 字段
- `0x288` — 备用 content_ptr 字段

记录同时访问 **多个字段** 的函数。例如一个函数中既出现了 `[reg+0x120]` 又出现了 `[reg+0x268]`，这个函数极可能是 FillMessageNode。

## Task 3: 追踪 FUN_1816c2a20 的上游

在 Ghidra 中，对 FUN_1816c2a20（DLL 偏移 0x016c2a20）做 **References → Show References to Address**，查看谁调用了它，并传入了 R14(start) 和 R15(end)。

## 输出格式

```
=== 0x2d8 常量引用 ===
FUN_xxxxxxxx  (DLL 0x????) — [有/无 malloc] [引用位置: +0x???]
...

=== 多字段访问函数 ===
FUN_xxxxxxxx  (DLL 0x????) — 访问了 +0x120, +0x268 [函数大小: ?]
...

=== FUN_1816c2a20 上游 ===
调用者: FUN_xxxxxxxx (DLL 0x????)
...

=== Top 候选 ===
1. FUN_xxxxxxxx — 理由
2. FUN_xxxxxxxx — 理由
3. FUN_xxxxxxxx — 理由
```

## 时间限制

90 分钟。没有明确发现就停止，进入导出器开发。
