# M7 — Global Context Differential Analysis V1

> 实验时间：2026-06-06
> 方法：Frida Hook onEnter/onLeave，dump arg1 (Global Context) 的 0x000~0x400 范围，逐字节 diff
> 实验覆盖：30 次 GetPagedMessages 调用（10 次同一会话 + 10 次联系人 + 10 次群聊）

---

## 核心发现

### 1. arg1 中仅 3 个偏移发生变化

在 0x000~0x400 (1024 字节) 范围内，每次 GetPagedMessages 调用**只有 3 个 8 字节段发生变化**：

| 偏移 | before | after | 模式 |
|------|--------|-------|------|
| +0x000 | 0xaaaaaaaaaaaaaaaa | 新指针 | 每次翻页变化 |
| +0x008 | 0xaaaaaaaaaaaaaaaa | 新指针 | 每次翻页变化 |
| +0x010 | 0xaaaaaaaaaaaaaaaa | 新指针 | = +0x008（完全相同） |

其他 0x400-24=1000 字节 **完全不变**。

### 2. 0xaaaaaaaaaaaaaa 是哨兵值

before 状态为 `0xaa...aa`（MSVC debug heap poison），说明：
- GetPagedMessages **执行前**这 3 个字段处于"未初始化/已释放"状态
- **执行后**被填入真实指针
- 这是函数通过**副作用**更新 arg1 的直接证据

### 3. +0x008 == +0x010（恒等）

所有 30 次调用中，+0x008 和 +0x010 始终指向同一地址。可能是一对 begin/end 迭代器指向同一对象，或是指针+引用计数。

### 4. 指针跨会话变化无规律

```
+0x000 指针变化（30 次调用）：
#1   0x1f43595eaa0
#2   0x1f43ebe45e0  ← 新地址
#3   0x1f47f912380  ← 新地址
#4   0x1f43ebe45e0  ← 复用 #2
#5   0x1f480d57540  ← 新地址
...  （无复用规律，重复分配/释放）
```

---

## 指针内容分析

### PTR0 (arg1+0x000) — Page Context Object

Dump 512 bytes 发现这是一个**页面上下文结构体**：

| 偏移 | 值 | 含义 |
|------|-----|------|
| +0x00 | 0x7fff2110eb88 | **固定**（vtable 指针） |
| +0x08 | 0 | **固定** |
| +0x0c | 3 / 47 / 49 | **变化** — 当前页消息数/位置 |
| +0x10 | 0xff345ca4... | **变化** — 内部指针 |

PTR0 不包含消息内容，是 GetPagedMessages 用于管理分页状态的**元数据对象**。

### PTR8 (arg1+0x008) — 渲染缓冲区

Dump 512 bytes，行为符合 **Qt 渲染缓存**：

| 命中 | 特征 | 解释 |
|------|------|------|
| #1 | 随机字节（477 non-zero） | 旧渲染数据 |
| #2 | 84 non-zero，大部分 0 | 页面缓存命中，无需重渲染 |
| #3 | 487 non-zero，结构连续 | 新渲染数据 |
| #4 | 84 non-zero，大部分 0 | 页面缓存命中 |
| #5 | `0xff313131ff313131` | **"111" 文本渲染**（ASCII 0x31="1"） |

PTR8 是 **Qt 文本渲染/纹理缓存**，不包含消息数据。

---

## 完整数据流模型（更新版）

```
翻页 (PageUp)
    ↓
GetPagedMessages (FUN_1816ade70)
    ├── arg0 = MessageList Manager (不变)
    ├── arg1 = Global Context (返回 retval, +0x000/+0x008 被更新)
    │     ├── +0x000 → PTR0: Page Context Object (页面元数据)
    │     └── +0x008 → PTR8: Rendering Buffer (UI 渲染)
    ├── arg2 = PagingContext (receiver, cursor, counter 被更新)
    └── retval = arg1 (确认)
    ↓
[副作用] 消息数据写入内部存储（位置未知）
    ↓
UI 从内部存储读取 → 渲染 → 显示
```

**关键洞察：消息数据本身不在 arg1 的三个指针中。** GetPagedMessages 将这些指针用于页面管理和 UI 渲染，实际的消息数据存储在其他地方。

---

## 消息数据的可能位置

| 位置 | 证据 | 可能性 |
|------|------|--------|
| **arg0 (MessageList Manager)** | 尚未深入分析 | **高** — 管理器应维护消息列表 |
| **紧凑结构 (34B 缓存)** | 翻页后 34B 前缀存在对应数据 | **中** — 但仅 ~25 条 |
| **GetPagedMessages 内部** | 函数在处理消息时分配的堆对象 | **中** — 需要 Ghidra 分析 |
| **arg2 (PagingContext)** | 翻页后 cursor/counter 更新 | **低** — 元数据而非消息 |

---

## 成功标准检查

| 标准 | 结果 |
|------|------|
| 1. 找到稳定变化字段 | ✅ **Confirmed** — arg1+0x000, +0x008, +0x010 每次翻页必变 |
| 2. 找到变化后的对象指针 | ✅ PTR0（页面上下文）、PTR8（渲染缓冲区）|
| 3. 找到消息列表缓存对象 | ❌ 未找到 — arg1 不直接包含消息列表引用 |

**M7 结论：GetPagedMessages 通过副作用更新 arg1 的 3 个指针字段，但它们指向的是页面管理对象和渲染缓冲区，不是消息数据本身。消息数据的真实位置仍需进一步定位。**
