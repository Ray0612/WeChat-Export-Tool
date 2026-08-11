# M24 — GetMessageListBySvrIds Upstream Analysis (Ghidra Task)

在 Ghidra 中分析 FUN_1816f3b30 (GetMessageListBySvrIds) 的上游调用链。

## Task 1: 找调用者

对 FUN_1816f3b30 (DLL 0x016f3b30) 做 References → Show References to Address，列出所有 CALL 类型的引用：

```
Caller A: FUN_1816xxxxx (DLL 0x????)
Caller B: FUN_1816xxxxx (DLL 0x????)
...
```

## Task 2: 分析 FUN_1835c4db0

这是目前已知的上游调用者。分析：

1. 搜字符串：msgid, svrid, message, receiver, chatroom, wxid, history, load, list
2. 参数数量：几个参数？输入/输出？
3. 调用链：是否直接调 FUN_1816f3b30？还是有中间层？

## Task 3: 判断 GetMessageListBySvrIds 的真实定位

三选一：
- A. 数据库查询接口（出现 svrid 数组，返回消息列表）
- B. 内存缓存接口（访问缓存容器）
- C. 同步接口（出现网络对象）

## Task 4: 找 MessageNode 容器

FUN_1816f3b30 返回前，消息结果放在哪？找 begin/end、vector、容器相关操作。

## 输出格式

```
=== 调用者列表 ===
Caller1: FUN_1816xxxxx
Caller2: FUN_1835c4db0
...

=== FUN_1835c4db0 分析 ===
参数: N 个
字符串: [列表]
调用链: [直接/间接]
定位判断: [A/B/C]

=== 容器位置 ===
[如有发现]
```
