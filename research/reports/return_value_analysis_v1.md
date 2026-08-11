# M6 — Return Value Analysis V1

> 实验时间：2026-06-06
> 方法：Frida Hook onLeave 捕获 GetPagedMessages (FUN_1816ade70) 返回值
> 实验覆盖：文件传输助手(10次翻页) + 联系人(10次翻页) + 群聊(12次翻页) = 32次调用

---

## 核心发现

### 1. 返回值完全恒定

所有 32 次调用，返回值**完全相同**：

```
retval = 0x8ecb6ff4f0  （= arg1）
```

| 实验 | 翻页次数 | retval | arg1 |
|------|---------|--------|------|
| Task 2: 文件传输助手 | 10 | 0x8ecb6ff4f0 | 0x8ecb6ff4f0 |
| Task 3: 联系人 wxid_22e48sxjw2c222 | 10 | 0x8ecb6ff4f0 | 0x8ecb6ff4f0 |
| Task 4: 群聊 49622797405@chatroom | 12 | 0x8ecb6ff4f0 | 0x8ecb6ff4f0 |

### 2. retval = arg1

```
arg1  = 0x8ecb6ff4f0 (Global Context / 全局常量)
retval = 0x8ecb6ff4f0 (完全相同)
```

这意味着 **GetPagedMessages 返回的是 arg1 本身**（Global Context 对象指针）。函数不返回消息数据。

### 3. 模式归纳

```
func(arg0=Manager, arg1=GlobalCtx, arg2=PagingContext, arg3=PagingContext+0x20)
    → return arg1 (GlobalCtx)
```

函数签名为：
```
GlobalCtx* GetPagedMessages(Manager* mgr, GlobalCtx* ctx, PagingContext* pctx, void* inner);
```

- arg0 (Manager): 所有会话一致 → 全局 MessageList Manager
- arg1 (GlobalCtx): 所有会话一致 → 全局上下文
- **retval = arg1** → 返回全局上下文，不返回消息列表
- **消息数据通过副作用产生 → 存在 arg2 / 内部数据结构中**

### 4. RETVAL_INNER_PTR 变化

虽然 retval 本身不变，但 retval 指向的内存中的第一个指针（RETVAL_INNER_PTR）每次翻页会变化：

| HIT | RETVAL_INNER_PTR |
|-----|-----------------|
| #1-#4 | 0x1f42fe48040 |
| #5 | 0x1f47a7db5e0 |
| #6 | 0x1f43ea24f20 |
| #7 | 0x1f434bdf220 |
| #8 | 0x1f44350d320 |
| #9 | 0x1f43ea24f20 |
| #10 | 0x1f43edcd000 |
| #11 (切换联系人) | 0x1f44441b3a0 |
| #12 | 0x1f43edcd000 |
| #13-#20 | 0x1f44446b240 (多次复用) |
| #21 (切换群聊) | 0x1f418387920 |
| #22-#26 | 0x1f44446b240 (复用) |
| #27 | 0x1f43edcd000 |
| #28 | 0x1f418854c00 |
| #29 | 0x1f440749fc0 |
| #30 | 0x1f4325f7e20 |
| #31 | 0x1f48012ba80 |
| #32 | 0x1f42fe48040 |

观察到 **地址复用** 现象（如 0x1f44446b240 出现 8 次），说明 Global Context 内部有一个消息列表缓存区域被反复重用。

### 5. PagingContext 确认

ARG2_HEX 验证了之前的 PagingContext 结构：

```
+0x000: "filehelper" / wxid / @chatroom   ← 接收者
+0x028: cursor (Unix ms timestamp, 递减)   ← 翻页游标
+0x030: counter (递减, 步长~30)            ← 消息序号/偏移
```

**ARG2_WXID 读取**：
- 文件传输助手：失败（"filehelper" 内联存储，readPointer 读到 ASCII 字节作为地址导致访问越界）
- 联系人/群聊：成功读取到 wxid

### 6. 离线状态验证

所有 32 次 HIT 均在线下完成（用户断网操作），GetPagedMessages 全部命中。
**进一步确认：历史消息存储在本地，非网络拉取。**

---

## 重要推论

### GetPagedMessages 不返回消息列表

```
之前的假设：
翻页 → GetPagedMessages → 返回消息列表 → UI 显示
                            ✗ 错误

实际的行为：
翻页 → GetPagedMessages → 写入内部缓存 → UI 从缓存读取
        返回 arg1 (状态)
```

这意味着去拦截返回值这条路拿不到消息数据。**消息数据是通过函数执行过程中的副作用产生的**，可能写入以下几种位置：

1. **PagingContext (arg2)** — 函数执行后会更新 arg2 内的字段
2. **Global Context (arg1)** — arg1 内部的某处缓存（RETVAL_INNER_PTR 变化说明内部状态在更新）
3. **MessageList Manager (arg0)** — 全局管理器内部维护的消息列表
4. **紧凑结构（34B 缓存）** — 翻页后 UI 显示消息，紧凑结构中也有对应数据

### 下一步方向

| 方向 | 说明 | 难度 |
|------|------|------|
| **A. 追踪 arg0 内部状态** | Hook onLeave 后 dump arg0 附近的内存，看是否有消息列表 | 中 |
| **B. 追踪 compact 结构变化** | 翻页后扫描内存中的 34B 前缀 `1b 02 05 09` | 低（但 ~25 条限制） |
| **C. Hook 函数内部** | 在 GetPagedMessages 内部找消息处理的子函数 | 高（需 Ghidra 深入分析） |
| **D. 换入口函数** | 找其他能返回消息数据的函数，如 GetInitialMessages | 中 |

**推荐方向 A**：arg0 (MessageList Manager) 最有可能维护消息列表，onLeave 后 dump arg0+某个偏移。

---

## 成功标准检查

| 标准 | 结果 |
|------|------|
| 1. 确认返回值是状态码 | ✅ **Confirmed** — retval = arg1（全局上下文），函数通过副作用产生数据 |
| 2. 确认返回值是对象指针 | ✅ 是对象指针（arg1），但不是消息列表指针 |
| 3. 找到返回对象中的消息相关字段 | ⚠️ RETVAL_INNER_PTR 变化说明内部状态更新，但未识别出消息字段 |

**M6 结论：GetPagedMessages 返回 arg1 (Global Context)，不直接返回消息列表。返回值分析完成。**
