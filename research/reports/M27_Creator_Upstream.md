# M27 — Creator Trace Upstream 分析报告

## 基本信息

| 项目 | 值 |
|------|-----|
| DLL | Weixin.dll 4.1.10.29 |
| 目标 | 分析 FUN_185b91d80 (RVA 0x5b91d80)，找 0x2d8 Creator |
| 状态 | **超出当前 Ghidra 项目范围 ❌** |

## Task 分析结果

### Task 1: FUN_185b91d80 内部

| 项目 | 值 |
|------|-----|
| 完整地址 | `0x185b91d80` |
| RVA | `0x5b91d80` |
| 所属模块 | 非 Weixin.dll（跨模块，推测 WeChatWin.dll） |
| 参数数量 | **6 个** |
| 返回值 | `undefined8`（指针/状态码） |
| 内部常量 0x2d8? | **无** |
| 内部常量 0x2e8? | **有** — FUN_18680e0fc(0x2e8) 回调包装 |
| 内部常量 0x2f0? | **有** — 清理哈希表缓存 |

### Task 2: 分配行为

`FUN_185b91d80` 内部的分配：

```
分配类型               大小        用途
FUN_18680e0fc(0x2e8)   0x2e8(744)  回调包装节点
FUN_18680e0fc(various) 可变         字符串/日志缓冲区
thunk_FUN_18686f098     0x2f0(752)  哈希表缓存清理
```

**没有 0x2d8 的分配。**

### Task 3: 字段写入

因为没有 `alloc(0x2d8)`，所以不存在写入 `+0x120`/`+0x268` 字段的操作。

### Task 4: 调用者（XREF）

| 调用者 | 地址 | 模块 |
|--------|------|------|
| `FUN_185b89cf0` | 0x185b89cf0 | 跨模块 |
| `FUN_1846d67d0` | 0x1846d67d0 | 跨模块 |

两者均在 Weixin.dll 之外，当前 Ghidra 项目无法进一步分析。

## 当前追踪链终止点

```
FUN_1846d67d0 / FUN_185b89cf0  (另一 DLL)
  │  ❌ 超出 Ghidra 项目范围
  │
  └── FUN_185b91d80  (跨模块)
       │  ✅ 已分析，无 0x2d8 分配
       │
       └── FUN_181771eb0  (Weixin.dll, +0x01771eb0)
            │  ✅ 已分析，无 0x2d8 分配
            │
            └── FUN_1816f3b30  (Weixin.dll, +0x016f3b30)
                 │  ✅ 已分析，无 0x2d8 分配
                 │
                 └── FUN_1816c2a20  (+0x016c2a20, 0x2d8 步长遍历)
                      ✅ 已分析
```

## 结论

**0x2d8 MessageNode 的创建不在 Weixin.dll 中。** 它位于另一个 DLL（WeChatWin.dll 或类似）的网络接收/解析层。

## 关于 Creator 位置的推断

根据调用链逻辑，0x2d8 的分配位置最可能是：

```
服务器响应到达
  ↓
网络层解析 (另一 DLL)
  ├── 解析 Protobuf/JSON 消息列表
  ├── malloc(count * 0x2d8)   ← 批量分配
  ├── 逐条填充字段 (+0x120, +0x268, +0x288 ...)
  └── 插入消息管理器
       ↓
FUN_185b91d80 等分发函数被调用
  ↓
GetMessageListBySvrIds 查询
  ↓
FUN_1816c2a20 过滤
```

如需继续查找，需要在 Ghidra 中额外导入 **WeChatWin.dll**。
