# M15 — GetPagedMessages Call Tree Analysis (Ghidra Task)

## 目标

在 Ghidra 中分析 `FUN_1816ff6b0`（GetPagedMessages），找到其内部调用的所有子函数，识别真正处理消息数据的函数。

## 背景

- 函数地址：`FUN_1816ff6b0`（DLL 偏移 `0x016ff6b0`）
- 已知该函数接收 PagingContext（arg2），返回 GlobalContext（arg1）
- 函数内部通过副作用将消息数据写入内部缓存
- 需要找到实际处理消息的子函数

## 操作步骤

### Step 1: 打开函数

在 Ghidra CodeBrowser 中：
1. 导航到 `FUN_1816ff6b0`
2. 按 **`G`** → 输入 `1816ff6b0` → 回车
3. 函数应该已自动分析完成

### Step 2: 建立 Call Tree

在函数上 **右键** → **References** → **Show Calling Functions**（看谁调了它）
或者更重要的：在函数体内找所有 CALL 指令。

手动方式：滚动浏览函数反汇编，寻找 `CALL` 指令。Ghidra 会把 CALL 目标标注为 `FUN_1816XXXXX` 或 `FUN_1847XXXXX`。

### Step 3: 输出格式

按这个格式记录：

```
FUN_1816ff6b0 (GetPagedMessages)
├── FUN_1816XXXXX
│   ├── FUN_1847XXXXX
│   └── FUN_1816XXXXX
├── FUN_1816XXXXX
├── FUN_1847XXXXX
└── FUN_1816XXXXX
```

### Step 4: 重点关注

在浏览函数体时，特别标记这些特征：

| 特征 | 标记 | 说明 |
|------|------|------|
| 循环结构 | `[LOOP]` | 出现 LOOP/JE/JNE 往回跳转 |
| 大函数 | `[LARGE]` | 子函数本身 > 100 字节 |
| 字符串操作 | `[STR]` | 调用 strlen/strcpy/memcpy 等 |
| 容器操作 | `[VECTOR]` | 涉及 vector/push_back/size 等 |
| 内存分配 | `[ALLOC]` | 调用 operator new / malloc / HeapAlloc |
| 频繁调用 | `[HOT]` | 被 GetPagedMessages 多次调用 |
| 条件调用 | `[COND]` | 在条件分支内被调用 |
| 循环内调用 | `[LOOP_CALL]` | CALL 指令位于循环中 |

### Step 5: 优先排序

按以下优先级标记候选函数：

1. **P0**: 循环内被反复调用的子函数（最可能是逐条消息处理）
2. **P1**: 涉及字符串/ProtoBuf 操作的子函数
3. **P2**: 涉及容器操作（vector/array）的子函数
4. **P3**: 大函数（> 500 字节）

### Step 6: 输出文件

完成后提交 `m15_call_tree.md`，包含：

```
# GetPagedMessages Call Tree

## 函数总览
函数大小: XXX 字节
内部 CALL 总数: XX 个
子函数数量: XX 个

## Call Tree
[嵌套列表]

## Candidate 函数 (Top 5)

### 1. FUN_1816XXXXX [LOOP_CALL] [LARGE]
- 调用位置: 0x1816XXXXX
- 在循环内: 是
- 被调用次数: ~30次/页
- 特征: ...

### 2. ...

## 分析建议
[推荐优先 Hook 验证的候选函数]
```

## 已知参考

旧版（4.1.9.56）GetPagedMessages 的 Ghidra 分析显示：
- 函数大小约 0x3000 字节
- 有 3 个调用者（Caller1/Caller2/Caller3）
- 内部包含对 "GetPagedMessages has messages:" 字符串的引用
- 参数通过寄存器传递（rcx/r8/r9/stack）
