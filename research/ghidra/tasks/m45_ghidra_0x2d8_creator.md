# M45 — Find 0x2d8 Creator (Ghidra Task)

## Task 1: FUN_181482400

在 Ghidra 中打开 FUN_181482400。分析它从 0x2d8 源结构拷贝了哪些字段。该函数在:
```
GetMessageListBySvrIds → memcpy from 0x2d8 source
```
确认是否拷贝了 content/receiver/msgid/cursor。

## Task 2: R14 (begin/end) 来源

在 FUN_1816f3b30 中，R14 = *(node+0x30)，R15 = *(node+0x38)。找到 node 的来源——它是从参数传入的，还是从某处读出的？

## Task 3: 搜索 0x2d8 分配

Search → Program Text 搜:
- 0x2d8
- 728
- new + 0x2d8 (附近)

寻找 `malloc(0x2d8)` 或 `new MessageNode[size]` 的位置。

## Task 4: 判断创建时机

根据来源判断 0x2d8 创建于：
- A. 网络响应解析时
- B. 数据库读取时
- C. 缓存重建时
- D. 其他

## 输出

完整链路：
```
Creator → 0x2d8 MessageNode → FUN_1816f3b30 → f3510(0x2f0) → GetPagedMessages
```
