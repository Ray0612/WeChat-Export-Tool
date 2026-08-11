# M24.5 — Message Manager Validation (Ghidra Task)

分析 FUN_181771eb0 → GetMessageListBySvrIds → 0x2d8 MessageNode 的链路。

## Task 1: 分析 FUN_181771eb0 的 param_1

重点看 `param_1 + 0x48` 指向什么对象。记录：
- 对象大小
- 是否有 vtable
- 是否包含字符串：message, msg, history, chat, conversation, svrid

## Task 2: 分析 GetMessageListBySvrIds 的调用参数

调用形式：
```
FUN_1816f3b30(local_68, &local_d8, param_1 + 8, &local_178)
```
确定哪个是查询条件，哪个是输出容器。特别关注 local_d8 和 local_178。

## Task 3: 确认查询语义

GetMessageListBySvrIds 究竟是：
- A. 根据多个 svrid 查询消息
- B. 根据 cursor 查询消息  
- C. 根据会话查询消息

## Task 4: 找结果容器

看 GetMessageListBySvrIds 返回后结果保存在哪。是 vector/list/自定义容器？记录 begin/end/count。

## 输出

如果确认链路 `FUN_181771eb0 → GetMessageListBySvrIds → MessageNode Container`，则停止逆向，进入导出器开发。
