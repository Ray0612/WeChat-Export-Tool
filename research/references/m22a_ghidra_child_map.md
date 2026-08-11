# M22A — FUN_1816c2a20 Child Function Mapping (Ghidra Task)

## 目标

在 Ghidra 中打开 FUN_1816c2a20，列出其全部直接调用的子函数，
找到实际创建/处理 0x2d8 MessageNode 的函数。

## 背景

- FUN_1816c2a20 (DLL 偏移 0x016c2a20) 是消息遍历入口
- 其 a1 参数是 Iterator/PagingContext，不是消息结构
- 0x2d8 消息结构体在函数内部被处理
- 需要找到内部创建 MessageNode 的子函数

## 操作步骤

### 在 Ghidra 中

1. 导航到 `FUN_1816c2a20`
2. 浏览反汇编，记录所有 `CALL` 指令

### 输出格式

```
FUN_1816c2a20
├── FUN_181XXXXXX  [call at +0xXXX]  [计数: N]  [LOOP/ALLOC/STR]
├── FUN_181XXXXXX  [call at +0xXXX]  [计数: N]  [LOOP/ALLOC/STR]
└── ...
```

### 特征标记

| 标记 | 含义 | 查找方法 |
|------|------|---------|
| `[LOOP]` | 位于循环体内 | CALL 上方有往回跳转的 JMP/JE/JNE |
| `[ALLOC]` | 可能是内存分配 | 函数名含 new/malloc/HeapAlloc |
| `[STR]` | 字符串操作 | 函数名含 strcpy/memcpy/QString |
| `[SIZE_0x2d8]` | 涉及 0x2d8 常量 | 参数中出现 0x2d8/0x2e0 |
| `[vtable]` | 虚函数调用 | 通过函数指针调用 |
| `[NEXT]` | 类似 Next() 语义 | 函数后跟循环判断 |
| `[多次]` | 被调用多次 | 同一函数被不同位置 CALL |

### 优先分析

1. 循环体内的 CALL（最可能是逐条消息处理）
2. 传递 0x2d8 相关常量的 CALL
3. 参数中包含 wxid/chatroom 字符串的 CALL
4. 函数名含 Copy/Move/Set/Add/Push 的 CALL

## 输出

提交 `m22a_child_map.md`，包含完整的调用图和 Top 3 候选函数。
