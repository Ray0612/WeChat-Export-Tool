# HookDS 可行性评估

## Task 1：业务函数链整理

基于 Weixin.dll 字符串普查结果整理的完整函数链。

```
消息加载链路（从打开聊天到显示消息）:
                                    ↓
打开聊天窗口 → ChatViewModelOwner
    ↓
SessionList.GetMessageSessionList        → 获取会话列表
    ↓
MessageList.GetInitialMessages           → 首次加载消息
    ↓
RecyclerList (虚拟滚动)                   → 检测滚动位置
    ↓
MessageList.GetPagedMessages             → **翻页加载历史消息** ← 关键
    ↓
MessageList.GetMessageListBySvrIds       → 按服务器ID拉取（可选的加载方式）
    ↓
CoPrepareShowMessage                     → 准备渲染消息
    ↓
UI 显示

消息发送链路:
发送消息 → StartSendMessageSyncStage
    ↓
GetAddSendMessageToDb                    → 写入本地数据库
    ↓
CoPrepareShowMessage                     → 本地显示
```

### 候选 Hook 目标排名

| 优先级 | 函数 | 位置（偏移） | 理由 | 难度 |
|--------|------|-------------|------|------|
| P0 | GetPagedMessages | ~0x83e35a4 | 翻页入口，拦截历史消息加载 | 高 |
| P1 | GetInitialMessages | ~0x83e3583 | 首次打开聊天触发，加载可见消息 | 高 |
| P2 | GetMessageListBySvrIds | ~0x83e3509 | 按ID查询消息 | 高 |
| P3 | GetAddSendMessageToDb | ~0x83e36a0 | 拦截消息持久化 | 中 |
| P4 | CoPrepareShowMessage | ~0x83e36b6 | 拦截渲染，获取消息对象 | 中 |

---

## Task 2：Frida Hook 难度评估

### 需要哪些步骤？

```
1. 安装 Frida（已完成）
2. 确定目标函数地址 ← ⚠️ 当前卡点
3. 编写 Frida hook 脚本 (JavaScript)
4. 注入 Weixin.exe
5. 触发翻页 → 验证 Hook 是否命中
```

### 是否需要 IDA/Ghidra？

**是。** 当前我们只有字符串的 .rdata 地址（偏移 0x83e35a4），不是函数入口地址。

函数入口定位有两种方式：

**方式A：IDA/Ghidra 反汇编（推荐）**
  1. 用 Ghidra 加载 Weixin.dll（181MB，需要 8G+ 内存）
  2. 定位字符串 `GetPagedMessages`（偏移 0x83e35a4）
  3. 追踪交叉引用（XREF）
  4. 找到引用该字符串的函数 → 这就是 GetPagedMessages 的调用方
  5. 记录函数地址

**方式B：运行时硬编码搜索（不推荐）**
  - 用 Frida 的 `Process.getModuleByName('Weixin.dll').enumerateExports()` → 无导出
  - 用 Frida 的 `Memory.scan()` 搜索特征码 → 不稳定
  - 只能备份方案

### 能否仅靠字符串引用定位？

**不能直接定位。** Weixin.dll 使用日志消息表机制，字符串通过索引而非直接地址引用，我们已经验证了：
- 搜索绝对地址引用：0 处
- 搜索 RIP-relative LEA：0 处
- 搜索相邻 5 个字符串的引用：全部 0 处

这意味着标准 xref 搜索技术在只有 pymem 的情况下不可行。

唯一的可靠方式是：**Ghidra 加载 DLL → 手动追踪 xref → 记录函数地址**。

### 所需工具

| 工具 | 需求 | 原因 |
|------|------|------|
| Ghidra / IDA | **必需** | 181MB DLL，字符串 xref 分析 |
| Frida | **必需** | Hook 注入 |
| Python | 建议保留 | 编写辅助脚本 |
| 内存 8G+ | **必需** | Ghidra 加载 181MB DLL |

---

## Task 3：成功概率评估

### P0: Hook GetPagedMessages（翻页入口）

| 因素 | 评估 |
|------|------|
| 函数存在性 | ⭐⭐⭐ 我们已验证日志字符串，函数存在 |
| 参数可推导性 | ⭐⭐ 从日志推测参数含 session_id, last_id, limit |
| 定位难度 | ⭐ 需要 Ghidra 分析 |
| 调用频率 | ⭐⭐⭐ 每次翻页触发 |
| 返回值类型 | ⭐ 未知（可能是 ProtoBuf 或 MessageList 对象）|
| **综合成功率** | **60-70%**（主要风险：函数定位 + 返回值解析）|

### P1: Hook GetInitialMessages（首次加载）

| 因素 | 评估 |
|------|------|
| 函数存在性 | ⭐⭐⭐ 已验证 |
| 调用时机 | 仅打开聊天时触发一次 |
| Hook 难度 | 同 GetPagedMessages |
| **综合成功率** | **50-60%**（一次性的，容易被错过）|

### P3: Hook GetAddSendMessageToDb（持久化）

| 因素 | 评估 |
|------|------|
| 函数存在性 | ⭐⭐⭐ 已验证 |
| 参数 | 包含明文消息内容（较高置信度）|
| 调用频率 | 发送每条消息时触发 |
| 定位难度 | 同其他函数 |
| **综合成功率** | **70%**（参数最容易推测）|

### 结论

| Hook 目标 | 成功率 | 推荐度 |
|-----------|--------|--------|
| GetAddSendMessageToDb | 70% | ⭐⭐⭐ 最容易解析返回值 |
| GetPagedMessages | 60-70% | ⭐⭐⭐ 最有价值 |
| GetInitialMessages | 50-60% | ⭐⭐ 一次性的 |
| CoPrepareShowMessage | 50% | ⭐⭐ 参数未知 |

---

## Task 4：最小验证实验（Hook PoC Plan）

### 目标

不导出消息，只证明函数被调用。

### 步骤

```
Step 1: 用 Ghidra 分析 Weixin.dll
  输入: Weixin.dll (181MB)
  操作: 搜索字符串 "GetPagedMessages"
  定位: 字符串地址 (已知 0x83e35a4)
  追踪: 交叉引用 → 找到函数入口

Step 2: 用 Frida 验证 Hook
  脚本:
    var funcAddr = Module.findBaseAddress('Weixin.dll').add(offset);
    Interceptor.attach(funcAddr, { onEnter: ... });
  操作: 在微信中向上翻页
  预期: console.log 输出 "GetPagedMessages called!"
  验证: Hook 成功命中

Step 3: 打印参数
  onEnter: 尝试读取第一个参数 (session_id)
  验证参数是否符合预期 (String 类型，值类似 wxid_xxx)

Step 4: 验证返回值
  onLeave: 尝试读取返回值 (可能是 Message 列表)
  输出返回值的类型和大小

Step 5: PoC 成功
  确认函数被正确 Hook
  确认参数可读取
  确认返回值可读取
```

### 最小工作量估计

| 阶段 | 工作内容 | 耗时 |
|------|---------|------|
| Ghidra 分析 | 加载 DLL、定位 xref、找函数入口 | 2-4 小时 |
| Frida PoC | 编写 Hook 脚本、验证命中 | 1-2 小时 |
| 参数验证 | 读取参数、确认 Message 结构 | 2-3 小时 |
| **总计** | | **5-9 小时** |

### 风险

| 风险 | 概率 | 影响 | 应对 |
|------|------|------|------|
| Ghidra 分析 181MB DLL 时 OOM | 中 | 高 | 需 8G+ 内存 |
| 函数入口定位错误 | 中 | 高 | 用多个字符串交叉验证 |
| Hook 导致 WeChat 崩溃 | 中 | 中 | 用 onEnter 空实现测试 |
| 返回值结构复杂（ProtoBuf 等）| 高 | 中 | 先从简单的函数开始 |

---

## 最终结论

```
HookDS 可行性：可行，但需要 Ghidra 辅助定位函数地址
前置条件：Ghidra 分析 Weixin.dll（2-4小时）
最小 PoC：5-9 小时
最大风险：函数入口定位 + 返回值结构

推荐策略：先 PoC 验证 GetPagedMessages 是否可 Hook
成功后再决定是否继续开发完整 HookDS
```
