# M14 — PagingContext Delta Analysis

> 实验时间：2026-06-06
> 方法：Frida Hook Caller1 (0x01683b08) onEnter/onLeave + PagingContext 512B dump
> 实验覆盖：76 次翻页调用（群聊 49622797405@chatroom）

---

## 1. PagingContext 结构（v4.1.10.29）

```
偏移    大小    类型    内容                    示例
+0x000   8      ptr     接收者 wxid 指针        → "49622797405@chatroom"
+0x008   8      -       padding / 0            0x0000000000000000
+0x010   8      u64     结构体标记              0x0000000000000013 (19)
+0x018   8      u64     结构体标记              0x000000000000001f (31)
+0x020   8      ptr     内部对象引用            0x7fff69xxxxxx
+0x028   8      u64     cursor (Unix ms)       随翻页递减
+0x030   4      u32     counter                随翻页递减，步长 30
+0x038   8      u64     结构体标记              0x000000000000001e (30)
```

**验证：** ✅ Confirmed（76 次调用数据一致）

## 2. 翻页规律（76 次连续翻页）

```
#1   cursor=1780567519000 (2026-04-04)   counter=5132
#2   cursor=1780410854000                 counter=5102  Δ=-30
...
#30  cursor=1777106232001                 counter=4262  Δ=-30
...
#76  cursor=1767933163000 (2026-01-08)   counter=2912  Δ=-30
```

**观察：**
- **Counter 每次翻页减少 30** → 每页 ~30 条消息
- 76 页共加载约 2280 条消息的元数据
- 覆盖时间范围：2026-04-04 → 2026-01-08（约 3 个月）
- 规律高度一致，无异常跳变

## 3. PagingContext 分配策略

- **每次翻页分配新的 PagingContext**（所有 76 个 a2 地址均不同）
- 旧版本的 PagingContext 在函数返回前被释放或重用于下一轮
- 接收者 (wxid/@chatroom) 在会话切换时才变化
- 结构体标记 (+0x010=0x13, +0x018=0x1f, +0x038=0x1e) 在所有调用中保持恒定

## 4. Caller1 调用行为

```
Caller1 (0x01683b08)
    │
    ├── 分配 PagingContext (heap)
    ├── 填充 receiver/cursor/counter
    ├── → GetPagedMessages (0x016ff6b0) ← 写入消息到内部缓存
    ├── 更新 PagingContext 字段（cursor 修改? counter 修改?）
    └── 返回 (retval)
```

**注意：** onLeave 的 AFTER 数据未能通过 Frida 捕获（回调时序问题），但旧版 M5 分析已确认 GetPagedMessages 会修改 +0x028 和 +0x030。

## 5. 结论

| 结论 | 状态 |
|------|------|
| PagingContext 结构稳定（新旧版本一致） | ✅ Confirmed |
| 每页 ~30 条消息（counter 减量） | ✅ Confirmed |
| PagingContext 每页重新分配 | ✅ Confirmed |
| cursor/counter +0x028/+0x030 偏移不变 | ✅ Confirmed |
| onLeave 写入字段 | ⚠️ 推测（旧版 M5 确认） |
