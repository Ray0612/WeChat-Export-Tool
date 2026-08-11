# M28 — Container Owner Analysis (Ghidra Task)

## 背景

FUN_1816f3b30 (GetMessageListBySvrIds) 内部：
```
RSI = node
R13 = RSI + 0x30
R14 = *(RSI + 0x30)  → start 指针 (传给 FUN_1816c2a20)
R15 = *(RSI + 0x38)  → end 指针
FUN_1816c2a20 用 [R14, R15) 以步长 0x2d8 遍历
```

## 任务

### Task 1: 分析 RSI 对象结构

看 RSI+0x00 到 +0x80 附近各有什么字段。特别是：
- +0x30: start 指针
- +0x38: end 指针
- +0x20, +0x28, +0x40 等偏移

### Task 2: 找 RSI 来源

RSI 在 FUN_1816f3b30 中是怎么获得的？是参数传入？还是从某个结构体读出来的？

### Task 3: 判断容器类型

RSI 代表什么？
- MessageContainer
- ChatSession
- ConversationCache
- QueryResult

## 输出

一句话回答：MessageNode 数组归谁所有。

例如：
```
RSI = param_2 (传入的容器对象)
R14 = RSI->begin (offset +0x30)
R15 = RSI->end   (offset +0x38)
```

或：
```
RSI = *(this + 0x50)  (会话缓存对象)
R14 = RSI->messageArray (offset +0x30)
```
