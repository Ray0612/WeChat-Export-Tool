# M46A — Analyze FUN_1816ef670 (Ghidra Task)

## 任务

分析 FUN_1816ef670，回答它是 Getter（读取已有数据）还是 Builder（新建数据结构）。

## Task 1: 参数和返回值

记录参数数量和类型，以及返回值。

## Task 2: 内部行为

内部是否有：
- `memcpy` / `new` / `malloc` — 说明是 Builder
- 只读字段不分配 — 说明是 Getter
- 返回值是数组指针还是单个对象

## Task 3: 调用者

列出所有调用 FUN_1816ef670 的函数。有多少函数依赖它返回的 begin/end？

## Task 4: 跨 DLL

检查参数/返回值是否涉及其他 DLL（如 WeChatWin.dll）。

## 输出

```
FUN_1816ef670 结论: [Getter/Builder]
证据: [理由]
调用者: [列表]
```
