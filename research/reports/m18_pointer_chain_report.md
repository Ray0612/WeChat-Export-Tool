# M18 — Reverse Pointer Recovery

> 实验时间：2026-06-07（基于 06-06 的数据）
> 方法：pymem 全内存扫描反向指针
> 状态：⚠️ 分析过程中 WeChat 退出，数据丢失，链未完全打通

---

## 已确认的指针链

```
Content String ("RAY_TEST_AAA_20260606")
    @ 0x1df1c15a24c
    ↑
Pointer Table Entry (0x20 stride)
    @ 0x1df24a26620   ← 存有 content_ptr
    ↑
Message Node? 
    @ 0x1df24ae2088   ← 引用了 table_entry
    ↑
??? (更高层引用)
```

## 多消息对比

| 层级 | AAA | BBB | CCC |
|------|-----|-----|-----|
| Content | `0x1df1c15a24c` | `0x1df1c15a21c` | `0x1df56f478e0` |
| Table Entry | `0x1df24a26620` | `0x1df24a26640` | `0x1df24a26700` |
| Node | `0x1df24ae2088` | `0x1df24ae2528` | `0x1df56f72118` (直连) |

## 关键观察

1. **AAA 和 BBB 相邻**（间距 0x30 字节）→ 同一批发送
2. **Table Entry 间距 0x20** → 固定步长指针表
3. **CCC 有直连引用** (`0x1df56f72118`) → 可能是 MessageBody 对象直接引用了内容
4. **Table Base (`0x1df24a26600`) 被 `0x1df24a28c28` 引用** → 表的所有者对象

## 推测的完整路径

```
MessageList (容器)
    ↓
MessageNode (0x2d8 结构体)
    ↓
MessageBody 或 Table (0x20 指针表)
    ↓
Content String (UTF-8 在堆上)
```

## 下一步

需要重新运行 WeChat 后：
1. 重新发送测试消息
2. 再次执行反向指针扫描
3. 从 `0x??f72118` 类型的直连引用往上追溯
