# M15 — GetPagedMessages Call Tree Analysis

> 分析时间：2026-06-06
> 方法：Ghidra Call Tree + Frida 命中验证
> 目标函数：FUN_1816ff6b0 (GetPagedMessages, DLL 0x016ff6b0)
> 验证函数：FUN_1816c2a20 (DLL 0x016c2a20)

---

## 函数总览

| 项目 | 值 |
|------|-----|
| GetPagedMessages | FUN_1816ff6b0 (DLL 0x016ff6b0) |
| 函数大小 | ~0x3000 字节 |
| 内部 CALL | 28 个（去重后 28 个子函数） |

## Call Tree

```
FUN_1816ff6b0 (GetPagedMessages)
│
├── 构建查询参数
│   ├── FUN_1816fa3f0  — 构建搜索参数 {orientation, sort_order, types, ...}
│   └── FUN_1816fcc60  — 构建 {create_time, sort_seq, local_id}
│
├── ★ FUN_1816c2a20 [VERIFIED] — 核心消息遍历入口
│   │  DLL 偏移 0x016c2a20
│   │  步长 0x2d8 遍历消息数组，逐条处理
│   │  ✅ Frida 验证：翻页时命中，~8 次/页
│   │
│   ├── FUN_1816c2b30  — CheckMessageLiveStatus
│   │   哈希表查找(FNV-1a)，检查直播状态
│   │
│   ├── FUN_1816c4100  — 引用计数转发 → FUN_183566640
│   ├── FUN_1816c4230  — (未深入分析)
│   ├── FUN_1816c44d0  — 引用计数转发 → FUN_182bd8310
│   ├── FUN_1816c4630  — 状态跟踪/日志记录
│   ├── FUN_1816ca380  — (未深入分析)
│   ├── FUN_1816cc4c0  — (未深入分析)
│   ├── FUN_1816c8300  — (未深入分析)
│   └── FUN_1816ce220  — (未深入分析)
│
├── 运行时/库函数 (C++ CRT)
│   FUN_18018ce40, FUN_1809490a0, FUN_180054470, ...
│
└── 跨模块调用 (thunk)
    FUN_1835edf20, FUN_186861478, FUN_1868970d0, ...
```

## Frida 验证结果

| 函数 | DLL 偏移 | 翻页命中 | 调用频率 |
|------|---------|---------|---------|
| **FUN_1816c2a20** | **0x016c2a20** | **✅ 40+ 次/5页** | **~8 次/页** |
| FUN_1816c2b30 | TBD | TBD | TBD |

## 关键候选函数

| 优先级 | 函数 | DLL 偏移 | 理由 |
|--------|------|---------|------|
| **P0** | **FUN_1816c2a20** | **0x016c2a20** | **消息数组遍历主入口，已验证命中** |
| P1 | FUN_1816c2b30 | TBD | CheckMessageLiveStatus，消息过滤 |
| P2 | FUN_1816fa3f0 / FUN_1816fcc60 | TBD | 查询参数构建 |

## 下一步建议

1. 深入分析 FUN_1816c2a20 内部调用链（子函数的子函数）
2. 在 FUN_1816c2a20 的 onLeave 捕获处理后的消息数据
3. 检查 0x2d8 步长的消息结构体内容
