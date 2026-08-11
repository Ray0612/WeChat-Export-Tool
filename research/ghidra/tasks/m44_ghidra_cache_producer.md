# M44 — Find Cache Producer (Ghidra Task)

分析 FUN_1816f3510 的调用者，找到缓存节点的创建位置。

## Task 1: f3510 是 insert 还是 lookup？

看函数内部是否有写入哈希表的操作（链表插入、key-value 写入），还是只有读取。通过 Frida 验证也可：冷启动时 0 调用，翻页时增长 → 说明是 insert。

## Task 2: 所有调用者分类

在 Ghidra 中对 FUN_1816f3510 做 References → Show References to Address，分类：

- **写入者**：调用后 f3510 内部执行插入/分配
- **读取者**：调用后只查询不写入

地址列表：

```
Caller 1: FUN_1816f3b30 (GetMessageListBySvrIds) — 已知
Caller 2: ??? 
...
```

## Task 3: 找 0x2f0 Producer

从已知的 0x2f0 分配点（M23 已确认: MOV ECX, 0x2f0; CALL operator_new）向上追踪。看哪个函数传入 0x2f0 并接收返回值，然后写入数据。

## Task 4: 向上追一层

找到 Producer 后，找它的调用者。目标是：

```
Data Source → Producer → f3510 → GetPagedMessages → UI
```

## 输出

```
f3510 角色: [insert/lookup/both]
写入者: [函数列表]
Producer: [函数地址] — alloc 0x2f0 + write data
完整链路: [DataSource] → [Producer] → f3510 → GetPagedMessages
```
