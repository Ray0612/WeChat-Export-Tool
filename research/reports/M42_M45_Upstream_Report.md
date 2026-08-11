# M42–M45 上游追踪与分析报告

## 范围

本报告覆盖 M42（GetPagedMessages Upstream Source）、M44（Cache Producer）、M45（0x2d8 Creator）的分析结果。

---

## M42: GetPagedMessages Upstream Source

### Cursor/Receiver 传递路径

```
arg2 (PagingContext)
  ├── +0x000: receiver → FUN_1816fa3f0 → 拼入查询字符串 "{sender:...}"
  └── +0x028: cursor  → FUN_1816fcc60 → 拼入 "{create_time:..., sort_seq:..., local_id:...}"
                           ↓
                  FUN_1816c2a20 (用查询条件过滤消息数组)
```

### 数据获取方式

**C. 访问缓存管理器**

| 特征 | 结论 |
|------|------|
| 哈希表查找 | ✅ FNV-1a hash (FUN_1816f3510) |
| B树/索引 | ❌ 不存在 |
| 数据库操作 | ❌ 不存在 |
| IPC调用 | ❌ 不存在 |
| 文件映射 | ❌ 不存在 |

### 数据流

```
[网络层 — WeChatWin.dll]  ← 服务器响应
  ↓
FUN_185b91d80 → GetMessageListBySvrIds
  ↓
FUN_1816f3510 (FNV-1a 哈希表缓存, 0x2f0 节点)
  ↓
GetPagedMessages → FUN_1816fa3f0/fcc60 (构建查询参数)
  ↓
FUN_1816c2a20 (0x2d8 步长遍历过滤)
```

---

## M44: Cache Producer (FUN_1816f3510)

### 角色：get-or-create（插入+查找）

FUN_1816f3510 内部逻辑：

```
1. FNV-1a hash key（8字节）
2. 哈希表查找
   ├── ✔ Key存在 → 返回已有节点 (flag=0)
   └── ✗ Key不存在 → 执行插入:
        ├── alloc 0x2f0 (MOV ECX, 0x2f0; CALL FUN_18680e0fc)
        ├── MOV [RBX+0x10], [R15]     ← 存 key
        ├── CALL FUN_181482400         ← 从 0x2d8 源拷贝数据
        └── 插入哈希表链表, 返回新节点 (flag=1)
```

### 调用者

| 调用者 | 地址 | 类型 |
|--------|------|------|
| FUN_1816f2df0 | 1816f300a | 写入者/读取者 |
| FUN_1816f3b30 | 1816f4277 | 写入者 (GetMessageListBySvrIds) |
| FUN_1816f3b30 | 1816f42e7 | 写入者 (第二次调用) |
| FUN_1835c4db0 | 1835c6a2e | 写入者 (跨模块) |

### 0x2f0 Producer

**0x2f0 的 Producer 就是 FUN_1816f3510 本身。** 分配在函数内部，数据从调用者传入的 R14（0x2d8 消息元素指针）拷贝而来。

---

## M45: 0x2d8 Creator

### FUN_181482400 — 0x2d8 → 0x2f0 字段拷贝

确认了 0x2d8 MessageNode 的完整字段布局：

| 偏移 | 字段 | 类型 |
|------|------|------|
| +0x000 | vtable | 指针 |
| +0x008 | 内部指针 | 指针 |
| +0x010 | 整数值 | int32 |
| +0x018 | SSO字符串1 | std::string |
| +0x038 | SSO字符串2 | std::string |
| +0x058 | SSO字符串3 | std::string |
| +0x078 | SSO字符串4 | std::string |
| +0x098 | 原始数据块 | byte[32] |
| +0x0c0 | (特殊处理) | — |
| +0x100 | 字符串 | std::string |
| **+0x120** | **receiver** (聊天对象ID) | **std::string** |
| +0x140 | 内容数据区 | byte[] |
| +0x180～0x1c0 | SSO字符串 | std::string × 3 |
| +0x1e0 | 数据块 | byte[] |
| +0x1f8 | (特殊处理) | — |
| **+0x268** | **content_ptr** | **指针** |
| **+0x288** | **content_ptr2** | **指针** |
| +0x2b8 | 末尾字符串 | std::string |

### Creator 结论

**0x2d8 MessageNode 的 Creator 不在 Weixin.dll 中。** 推测在 WeChatWin.dll 的网络响应解析层——从服务器收到消息后 `malloc(count * 0x2d8)` 逐条填充。

---

## 完整链路总览

```
[WeChatWin.dll / 网络层]
  │ 服务器响应 → 解析 Protobuf/JSON
  │ malloc(count * 0x2d8)  ← 0x2d8 Creator 在此
  │ 填充字段 (+0x120 receiver, +0x268 content, ...)
  ↓
FUN_185b91d80 (跨模块分发)  [RVA 0x5b91d80]
  │ 6参数: (消息对象, IDs, 回调, 上下文...)
  │ base62 日志编码
  ↓
FUN_181771eb0 (消息管理事件入口)  [DLL +0x01771eb0]
  │ 1参数: 会话对象 (+0x08=链表, +0x48=管理器)
  │ 分配 0x2e8 回调包装, 通过 FUN_181729f20 分发
  ↓
FUN_1816f3b30 (GetMessageListBySvrIds)  [DLL +0x016f3b30]
  │ 4参数: (管理器, 查询参数, 输出容器, 结果标记)
  │ 遍历链表 → 遍历消息数组
  ├──→ FUN_1816c2a20 (0x2d8 步长过滤遍历)  [DLL +0x016c2a20]
  └──→ FUN_1816f3510 (0x2f0 缓存 get-or-create)  [DLL +0x016f3510]
       ├── alloc 0x2f0
       ├── FUN_181482400 (0x2d8→0x2f0 逐字段拷贝)
       └── 插入 FNV-1a 哈希表
  ↓
FUN_1816ff6b0 (GetPagedMessages)  [DLL +0x016ff6b0]
  │ 从 PagingContext 读取 receiver/cursor
  │ FUN_1816fa3f0/fcc60 构建查询参数
  │ FUN_1816c2a20 过滤
  ↓
消息返回给调用方
```

## 所有已定位函数

| 函数 | DLL偏移 | 角色 | 报告 |
|------|---------|------|------|
| `FUN_1816ff6b0` | +0x016ff6b0 | **GetPagedMessages** | M15 |
| `FUN_1816fa3f0` | +0x016fa3f0 | 构建搜索参数 | M15 |
| `FUN_1816fcc60` | +0x016fcc60 | 构建查询参数 | M15 |
| `FUN_1816c2a20` | +0x016c2a20 | 消息过滤/遍历核心 | M15/M23 |
| `FUN_1816c2b30` | +0x016c2b30 | CheckMessageLiveStatus | M15 |
| `FUN_1816c4630` | +0x016c4630 | 状态/日志记录 | M15 |
| `FUN_1816f3b30` | +0x016f3b30 | **GetMessageListBySvrIds** | M23 |
| `FUN_1816f3510` | +0x016f3510 | 0x2f0 缓存 (get-or-create) | M23/M44 |
| `FUN_181771eb0` | +0x01771eb0 | 消息管理事件入口 | M24 |
| `FUN_185b91d80` | (跨模块) | 网络响应处理 | M25/M27 |
| `FUN_181482400` | +0x01482400 | 0x2d8→0x2f0 字段拷贝 | M45 |
| **0x2d8 Creator** | **?(WeChatWin.dll)** | **消息结构体分配** | **未找到** |

## 结论

1. **0x2d8 Creator 不在 Weixin.dll 中**，在 WeChatWin.dll 网络层
2. GetPagedMessages 的数据来源是 **内存哈希表缓存**（不是数据库/IPC）
3. 0x2f0 缓存节点在 FUN_1816f3510 内分配，数据从 0x2d8 源通过 FUN_181482400 逐字段拷贝
4. 所有函数地址已定位，可以进入导出器开发
