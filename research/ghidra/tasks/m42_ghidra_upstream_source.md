# M42 — GetPagedMessages Upstream Source (Ghidra Task)

分析 FUN_1816ff6b0 (GetPagedMessages) 内部调用链，找到最上游的数据获取函数。

## 背景

已知参数：
- arg0 = MessageList Manager
- arg1 = GlobalContext  
- arg2 = PagingContext { +0x000=receiver, +0x028=cursor, +0x030=counter }
- arg3 = arg2 + 0x20

已确认 GetPagedMessages 内部经过：
```
FUN_1816ff6b0
→ 构建查询参数 (FUN_1816fa3f0, FUN_1816fcc60)
→ FUN_1816c2a20 (过滤遍历)
→ FUN_1816c2b30 (处理)
```

但**数据从哪里来**仍未知。

## Task 1

在 Ghidra 中打开 FUN_1816ff6b0，追踪 cursor(+0x28)、receiver(+0x00) 的流向。
这些字段最终被传递到哪个函数？追踪参数的传递路径。

## Task 2

重点分析 `FUN_1816fa3f0` 和 `FUN_1816fcc60`（构建搜索参数的函数）。

它们构建的查询条件被传给谁？最终的读取函数是什么？

## Task 3

寻找函数内部是否有以下特征：
- 哈希表查找 (FNV-1a hash pattern)
- B树/索引查找
- 映射文件访问
- 数据库游标操作

## 输出

```
=== Cursor 传递路径 ===
arg2+0x28 → ??? → ??? → ???

=== 数据获取函数 ===
[函数地址] — [从XXX读取数据]

=== 判断 ===
A. 直接访问历史层
B. 访问内存索引
C. 访问缓存管理器
D. 访问 IPC 服务
```
