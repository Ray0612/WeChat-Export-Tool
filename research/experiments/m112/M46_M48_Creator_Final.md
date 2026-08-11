# M46–M48: 0x2d8 MessageNode Creator 最终报告

## 核心发现

**FUN_181bc3b00 (DLL +0x01bc3b00) 就是 0x2d8 MessageNode 的 Creator。**

## 分配模式

```
FUN_181bc3b00(param_1)  ← 消息节点工厂函数
│
├── 分配辅助对象 (0x20, 0x30, 0x2f8 等)
│
├── ★ alloc 0x2d8 × 6 次:
│   │   MOV ECX, 0x2d8
│   │   CALL FUN_18680e0fc    ← 堆分配
│   │
│   ├── FUN_183c0fd10          ← 基础初始化
│   │   ├── vtable 指针 (×7)
│   │   ├── 区域清零 (+0x198~+0x1e8)
│   │   ├── SSO 字符串初始化 (+0x1f0, +0x210, +0x230)
│   │   ├── FUN_183c10390      ← 填入参数数据
│   │   ├── 链表哨兵节点 ×3
│   │   └── FUN_183c10580      ← 后续初始化
│   │
│   ├── FUN_1868970d0          ← memcpy 从源数据填充字段
│   │
│   └── FUN_180264ea0          ← 插入消息容器
│
└── 返回
```

## 字段填充验证

| 偏移 | 字段 | 填充时机 |
|------|------|---------|
| +0x000 | vtable | FUN_183c0fd10 |
| +0x010 | vtable 2 | FUN_183c0fd10 |
| +0x030 | vtable 3 | FUN_183c0fd10 |
| +0x068 | vtable 4 | FUN_183c0fd10 |
| +0x0c0 | vtable 5 | FUN_183c0fd10 |
| +0x120 | **receiver** | memcpy 或下游填充 |
| +0x130 | vtable 6 | FUN_183c0fd10 |
| +0x138 | vtable 7 | FUN_183c0fd10 |
| +0x198~0x1e8 | 清零区 | FUN_183c0fd10 |
| +0x1f0, +0x210, +0x230 | SSO 字符串 | FUN_183c0fd10 |
| +0x240 | 数据区 | FUN_183c10390 |
| +0x268 | **content** | memcpy 或下游填充 |
| +0x298~ | 链表结构 | FUN_183c0fd10 |

## 0x2d8 Scalar Search 结果总结

| 模式 | 结果 | 结论 |
|------|------|------|
| `MOV ECX, 0x2d8` + CALL | **6 处** (在 FUN_181bc3b00) | Creator 确认 ✅ |
| `LEA [RBP + 0x2d8]` | 大量 | 栈操作，非分配 |
| `SUB/ADD RSP, 0x2d8` | 少量 | 栈空间预留 |
| `IMUL x 0x2d8` | 无 | 无批量分配 |

## Creator 定位过程

```
M15: GetPagedMessages Call Tree 建立
M23: 发现 0x2d8 步长循环，开始找 Creator
M24-M25: 向上游追踪至 FUN_181771eb0、FUN_185b91d80
M27-M28: 发现 Creator 不在浅层调用链中
M42-M45: 确认 0x2d8→0x2f0 拷贝函数，确认字段布局
M46: 多轮 Scalar 搜索，结果过多无法定位
M46A: 分析 FUN_1816ef670 (Getter)
M47: 分析 FUN_185b91d80 (Dispatcher)
M48: 定向搜索 MOV ECX, 0x2d8 → 找到 FUN_181bc3b00  ✅
```

## 最终完整链路

```
[WeChatWin.dll 网络层] ← 服务器消息数据
  │
  ↓
FUN_185b91d80 / FUN_1835c4db0  ← 调度/分发
  │
  ↓
FUN_181bc3b00  ← ★ 0x2d8 Creator (alloc ×6)
  │  MOV ECX, 0x2d8; CALL FUN_18680e0fc
  │  FUN_183c0fd10 (初始化 vtable + 默认值)
  │  FUN_1868970d0 (memcpy 填充数据)
  │
  ├──→ FUN_1816ef670 (Getter: 读取 begin/end)
  │
  ├──→ FUN_181771eb0 (事件入口)
  │   └── FUN_1816f3b30 (GetMessageListBySvrIds)
  │       ├── FUN_1816c2a20 (0x2d8 步长过滤)
  │       └── FUN_1816f3510 (0x2f0 缓存)
  │
  └──→ GetPagedMessages (FUN_1816ff6b0, +0x016ff6b0)
       └── 消费者返回消息给 UI
```

## 关键函数完整列表

| 函数 | DLL 偏移 | 角色 |
|------|---------|------|
| **FUN_181bc3b00** | **+0x01bc3b00** | **★★ 0x2d8 Creator (工厂)** |
| FUN_183c0fd10 | (跨段) | 0x2d8 基础初始化 |
| FUN_1816ff6b0 | +0x016ff6b0 | GetPagedMessages |
| FUN_1816c2a20 | +0x016c2a20 | 0x2d8 过滤遍历 |
| FUN_1816f3b30 | +0x016f3b30 | GetMessageListBySvrIds |
| FUN_1816f3510 | +0x016f3510 | 0x2f0 缓存 (FNV-1a) |
| FUN_181482400 | +0x01482400 | 0x2d8→0x2f0 字段拷贝 |
| FUN_1816ef670 | +0x016ef670 | Getter: begin/end |
| FUN_181771eb0 | +0x01771eb0 | 消息管理事件 |
| FUN_1835c4db0 | (跨段) | 分发器 |
| FUN_185b91d80 | (跨段) | 网络调度器 |
