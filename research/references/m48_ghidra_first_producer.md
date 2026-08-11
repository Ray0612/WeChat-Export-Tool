# M48 — Find the First 0x2d8 Producer (Ghidra Task)

## 目标

找到第一次创建 0x2d8 MessageNodeArray 的函数。

## 已确认的 Consumer 链（不要重复分析）

这些全部是消费者，不需要再看：
```
FUN_1816ef670 — Getter
FUN_1835c4db0 — Dispatcher
FUN_1816f3510 — Cache
FUN_1816c2a20 — Filter
GetPagedMessages — Consumer
```

## Task 1: 从 FUN_1835c4db0 反向追踪

在 Ghidra 中打开 FUN_1835c4db0，找到 `local_198` 和 `begin/end` 指针的来源。这个对象从哪里来？是参数传入的，还是从某个全局/成员变量读出的？

## Task 2: 全局搜索 0x2d8 分配

Search → Program Text 搜以下模式（不限于 Weixin.dll，也可搜 WeChatWin.dll）：
- `imul ?, ?, 0x2d8`
- `lea ?, [?, ?*0x2d8]`
- `0x5b0` (0x2d8 × 2)
- `0x8a8` (0x2d8 × 3)
- `0x5b00` (0x2d8 × 20)
- `0x8a18` (0x2d8 × 30)
- `memcpy` 附近有 `0x2d8`

## Task 3: 追踪 FUN_18680e0fc 的大块分配

FUN_18680e0fc 是通用分配器。搜所有调用它且 size 接近 0x2d8 倍数的位置。

## Task 4: 找首次写入 receiver/content 的函数

搜对 +0x120、+0x268、+0x288 偏移的写入操作。第一个写入这些偏移的函数就是 MessageNode 初始化函数。

## 输出

```
First Producer: FUN_XXXXXXXX (DLL偏移 0xXXXXXXXX)
分配方式: [imul批量 / new / malloc]
字段写入: [+0x120/receiver, +0x268/content] [确认写入]
```
