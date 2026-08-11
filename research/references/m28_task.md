# M28 — Node Business Object (Ghidra Task)

## Task 1

FUN_1816f3b30 遍历链表时，记录循环终止条件（while node != head? sentinel?）和 head 的来源。

## Task 2

FUN_181771eb0 调用 FUN_1816f3b30 时传入了 `param_1 + 8`。分析 param_1 是什么对象（ChatSession? Conversation? HistoryManager?）。

## Task 3

在 FUN_1816f3b30 中计算 `count = (end - begin) / 0x2d8`，看一次加载多少条消息（30? 几百?）。

## Task 4

两次调用 FUN_1816c2a20 的原因——是同一批消息两种处理，还是不同类型消息？

## 输出

一句话：node 代表什么业务对象？
