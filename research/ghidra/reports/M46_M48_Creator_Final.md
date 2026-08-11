# M46–M48: 0x2d8 MessageNode Creator 最终报告

## 核心发现

**FUN_181bc3b00 (DLL +0x01bc3b00) 就是 0x2d8 MessageNode 的 Creator。**

## 定位过程

1. 之前搜 0x2d8 结果太多（大量 LEA RBP+0x2d8 栈操作），无法定位
2. 在 Ghidra 中用 Search → For Scalars → Specific Scalar 输入 728 (十进制)
3. 过滤出 MOV ECX, 0x2d8 后跟 CALL 的模式
4. 在 FUN_181bc3b00 中找到 6 处 FUN_18680e0fc(0x2d8) 堆分配

## Creator: FUN_181bc3b00

地址: 0x181bc3b00 | DLL 偏移: +0x01bc3b00

每个消息节点创建流程:
1. `MOV ECX, 0x2d8; CALL FUN_18680e0fc` — 堆分配 0x2d8
2. `FUN_183c0fd10(buf, param2, param3)` — 基础初始化 (vtable + 默认值)
   - 写 vtable 指针 (+0x000, +0x010, +0x030, +0x068, +0x0c0, +0x130, +0x138)
   - 清零区域 (+0x198~+0x1e8)
   - SSO 字符串初始化 (+0x1f0, +0x210, +0x230)
   - FUN_183c10390 — 从参数写入数据
   - 链表哨兵节点 ×3 (alloc 0x20)
3. `FUN_1868970d0` — memcpy 从源数据填充
4. `FUN_180264ea0` — 插入消息容器

## 0x2d8 Scalar 搜索结果

| 模式 | 结果数 | 结论 |
|------|--------|------|
| MOV ECX, 0x2d8 + CALL | 6 处 | Creator 确认 ✅ |
| LEA [RBP+0x2d8] | 大量 | 栈操作 ❌ |
| SUB/ADD RSP, 0x2d8 | 少量 | 栈空间预留 ❌ |

## Creator 定位全过程

M15: GetPagedMessages Call Tree (28 子函数)
M23: 发现 0x2d8 步长循环, 开始找 Creator
M24-25: 向上游追踪至 FUN_181771eb0, FUN_185b91d80
M27-28: 确认 Creator 不在浅层调用链
M42-45: 确认 0x2d8→0x2f0 拷贝, 字段布局
M46: 多轮 Scalar 搜索, 结果过多
M46A: 分析 FUN_1816ef670 (Getter)
M47: 分析 FUN_185b91d80 (Dispatcher)
M48: 定向搜 MOV ECX, 0x2d8 → 找到 FUN_181bc3b00 ✅

## 注释

之前一直搜不到 0x2d8 的堆分配是因为:
- 开发板主要关注 1816 核心代码段, 实际分配在 181bc 段
- scalar 搜索结果包含大量栈操作, 没有过滤 MOV ECX + CALL 模式
