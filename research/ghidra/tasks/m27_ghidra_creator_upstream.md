# M27 — Creator Trace Upstream (Ghidra Task)

分析 FUN_185b91d80 (RVA 0x5b91d80)，找 0x2d8 MessageNode Creator。

## Task 1: 分析 FUN_185b91d80 内部

在 Ghidra 中打开 FUN_185b91d80，回答：
- 函数大小？
- 参数数量？
- 返回值类型？
- 内部是否有 `0x2d8`、`0x2e8`、`0x2f0` 常量？
- 是否有 `operator new`/`malloc`/`FUN_xxx(size)` 调用？

## Task 2: 搜索分配行为

看内部是否调用了内存分配函数，特别是大小为 728(0x2d8)、744(0x2e8)、752(0x2f0) 的。

## Task 3: 搜索字段写入

如果发现 `ptr = alloc(0x2d8)`，继续看后面是否写入 `+0x120`(receiver) 或 `+0x268`(content_ptr)。

## Task 4: 如果仍是中转

如果 FUN_185b91d80 只是中转，找它的调用者（只追第一层）。

## 停止条件

一旦发现 `alloc(0x2d8)` + 字段写入，立即停止汇报。
