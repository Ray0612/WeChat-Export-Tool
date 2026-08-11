# M13 — Caller1 Analysis

> 分析时间：2026-06-06
> 方法：Frida Hook FUN_181683b08 (DLL offset 0x01683b08)
> 数据：16 次翻页调用

---

## 1. Caller1 参数模型

```
FUN_181683b08(arg0, arg1, arg2, arg3, arg4, arg5)
```

| 参数 | 模式 | 含义 | 确认度 |
|------|------|------|--------|
| a0 | 0x1df56befa90 (恒定) | MessageList Manager | ✅ Confirmed |
| a1 | 0xb276dff560 (恒定) | GlobalContext | ✅ Confirmed |
| a2 | 变化 | PagingContext 指针 | ✅ Confirmed |
| a3 | a2 + 0x20 (恒定偏移) | PagingContext 内部字段 | ✅ Confirmed |
| a4 | a2 + 0x40 (恒定偏移) | PagingContext 内部字段 | ✅ Confirmed |
| a5 | 变化 (6 种不同值) | 可能是会话上下文或回调 | ⚠️ 规律不明 |

**与旧版 4.1.9.56 对比：**
- a0/a1/a2 模式完全一致
- 旧版只有 a0-a3，新版增加了 a4 (=a2+0x40) 和 a5（上下文）
- a3 = a2 + 0x20 的偏移关系保持

## 2. PagingContext 结构（已验证）

```
偏移    大小    内容                   示例
+0x000   8      接收者 wxid 指针        → "wxid_22e48sxjw2c222"
+0x008   8      padding / unknown     0x0000000000000000
+0x010   8      结构体 marker          0x0000000000000013 (19)
+0x018   8      结构体 marker          0x000000000000001f (31)
+0x020   8      对象引用指针            0x7fff6a0110cb
+0x028   8      cursor (u64)           Unix ms 时间戳
+0x030   4      counter (u32)          每页减 30
+0x034   4      padding               0x00000000
+0x038   8      结构体 marker          0x000000000000001e (30)
```

**cursor + counter 偏移与旧版完全相同（+0x028 / +0x030）。**

## 3. 翻页规律

```
#1  cursor=1778454731000    counter=4248
#2  cursor=1777552161000    counter=4218  Δ= -30
#3  cursor=1777019559000    counter=4188  Δ= -30
#4  cursor=1776784759000    counter=4158  Δ= -30
...
#16 cursor=1775914643000    counter=3798  Δ= -30
```

**观察到：**
- **Counter 每次翻页固定减 30** → 每页加载 ~30 条消息
- **Cursor（时间戳）递减** → 翻到更早的历史
- Counter 从 4248 → 3798，16 页共加载约 450 条消息的元数据

## 4. 调用关系

```
用户按 PageUp
    ↓
Caller1 (FUN_181683b08, DLL 0x01683b08)
    │
    ├── 分配新的 PagingContext (a2)
    ├── 设置 a3 = a2 + 0x20, a4 = a2 + 0x40
    ├── ...
    │
    ├──→ GetPagedMessages (FUN_1816ff6b0, DLL 0x016ff6b0)
    │     └── 从离线存储加载消息到内部缓存
    │
    ├── 更新 PagingContext 中的 cursor/counter
    │
    └── 返回 (retval)
```

## 5. PagingContext 的生存周期

- 每次翻页**分配新 PagingContext**（a2 每次不同，16 次中 16 个不同地址）
- 接收者 (wxid) 在会话切换时变化
- cursor/counter 在函数返回前更新
- arg2 地址不重复 → 每次分配新结构体，用完释放

## 6. a5 变化

a5 出现 6 种不同值，部分值重复出现：
- 0x1df64c071d0（出现 5 次）
- 0x1df6589c120（出现 3 次）
- 0x1df64c0e790（1 次）
- 0x1df64c08130（1 次）
- 0x1df64c0d3e0（1 次）
- 0x1df6003e390（1 次）

均在 0x1df6xxxxxxx 范围，可能指向某种调用上下文对象。

## 7. 结论

| 项目 | 结论 |
|------|------|
| Caller1 是翻页入口 | ✅ Confirmed (16 次命中) |
| PagingContext 结构保持 | ✅ Confirmed (+0x028, +0x030 不变) |
| 每页消息数 | ⚠️ ~30 条 (counter 减量) |
| Caller1 内部调用 GetPagedMessages | ⚠️ 极可能 (Ghidra xref 确认调用关系) |
| 消息数据可直接从返回获取 | ❌ 需要验证 (onLeave 未捕获) |
