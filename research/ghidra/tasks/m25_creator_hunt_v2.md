# M25 — MessageNode Creator Hunt V2 (Ghidra Task)

## 核心问题

谁创建了 0x2d8 MessageNode？

## 已知链路

```
FUN_181771eb0 → FUN_1816f3b30(GetMessageListBySvrIds) → FUN_1816c2a20(步长0x2d8)
```

## Task 1: 上游调用链（向上追 3 层）

从 FUN_1816c2a20 开始，对每个函数做 Show References to Address (CALL 类型)：

```
FUN_1816c2a20
  ← FUN_1816f3b30 (confirmed)
    ← FUN_181771eb0 (confirmed)
      ← ? (需要找)
        ← ? (需要找)
```

每层记录：函数地址、DLL偏移、参数数量。

## Task 2: 搜索 0x2d8 分配

Search → Program Text，搜：
- `0x2d8`
- `728`

看哪些引用出现在 `new`/`malloc`/`HeapAlloc` 附近。

特别关注 `FUN_1816f3b30` 内部是否有 `new(0x2d8)` 或 `malloc(0x2d8)`。

## Task 3: 搜索批量分配

搜 0x2d8 的倍数：
- `0x5b00` (0x2d8 × 20)
- `0x8a18` (0x2d8 × 30)
- `0xb600` (0x2d8 × 40)

## Task 4: 分析 FUN_1816f3b30 返回值

看这个函数 return 什么。是否返回 MessageNode 容器（vector/array）？注意看函数末尾 RAX 的值。

## Task 5: Creator Candidate

如果发现：
1. `new(0x2d8)` 或 `malloc(0x2d8)`
2. 然后写入 `+0x120`(receiver) 或 `+0x268`(content_ptr)

立即记录并停止搜索。

## 输出

```
=== 上游调用链 (3层) ===
FUN_1816c2a20 (0x016c2a20)
  ← FUN_1816f3b30 (0x016f3b30)
    ← FUN_181771eb0 (0x01771eb0)
      ← FUN_??? (0x????)
        ← FUN_??? (0x????)

=== 0x2d8 分配候选 ===
[有/无] new(0x2d8) 在 FUN_???

=== 批量分配 ===
[有/无] count * 0x2d8

=== FUN_1816f3b30 返回值 ===
return: [容器指针 / void / 状态码]

=== Creator Candidate ===
[找到/未找到]
```
