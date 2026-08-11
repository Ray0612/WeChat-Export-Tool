# 微信 4.1.9.56 导出项目 — 交接文档

> 编写时间：2026-06-06 22:00
> 研究周期：2026-06-04 至 2026-06-06（3 天）
> 项目仓库：https://github.com/Ray0612/WeChat-v4-export-research

---

## 一、项目概况

### 目标
开发一个工具，**自动导出微信 4.1.9.56（Windows 版）的聊天记录**。

### 当前阶段
已完成 Message Model V1、Business Object Map V1、Exporter Architecture V1。
已确认 GetPagedMessages 函数地址，Frida Hook 验证通过。
**项目已从"解密问题"转变为"数据提取问题"。**

### 核心结论
1. **聊天消息不在磁盘上**（35063 文件搜索 0 匹配）
2. **聊天消息在 Weixin.exe 内存中**（pymem + Frida 双重验证）
3. **历史消息存储在本地**（离线可翻大量历史，但位置未知）
4. **GetPagedMessages 是历史消息加载入口**（Ghidra xref + Frida PoC 确认）
5. **紧凑结构是内存消息缓存**（34B/条，~25 条，易失）

---

## 二、环境配置

### 用户环境
| 项目 | 内容 |
|------|------|
| OS | Windows 11 中文版，2560×1600 |
| 微信版本 | 4.1.9.56 |
| 微信进程 | `Weixin.exe` + `WeChatAppEx.exe`（Chromium 子进程）|
| 核心 DLL | `Weixin.dll`（181MB，Qt 5.15.14，symbol strip）|
| 数据目录 | `AppData\Roaming\Tencent\xwechat\radium\users\<hash>\` |
| Python | 3.13.5（`D:\Users\OK\AppData\Local\Programs\Python\Python313\`）|
| Go | 1.26.4（`C:\Program Files\Go\bin\go`）|
| Java | 21.0.11（`C:\Users\OK\java21\jdk-21.0.11+10`）|
| Ghidra | 12.1（`C:\Users\OK\Desktop\ghidra\ghidra_12.1_PUBLIC\`）|
| Frida | 17.10.1（Python package + CLI）|
| Tesseract | 5.4.0（`C:\Program Files\Tesseract-OCR\`）|

### 关键工具
| 工具 | 用途 | 安装方式 |
|------|------|----------|
| pymem 1.14.0 | 进程内存读写 | pip |
| pycryptodome 3.23.0 | AES 解密 | pip |
| psutil | 进程枚举 | pip |
| frida 17.10.1 | Hook 注入 | pip |
| frida-tools 14.9.0 | Frida CLI | pip |
| Ghidra 12.1 | 反汇编分析 | 手动解压（ZIP 570MB）|
| radare2 5.9.8 | 轻量反汇编（备选）| 手动解压（ZIP 12MB）|
| chatlog v0.0.31 | 数据库解密验证（Go）| go install |

---

## 三、项目文件结构

```
C:\Users\OK\Desktop\wechat_v4_export_research\
│
├── README.md                                ← 项目总览
├── 2026-06-05_log.md                        ← 6.5 日志
├── coding_sprint_v0_1.md                   ← Sprint 1 编码总结
│
├── daily/                                   ← 详细研究日志
│   ├── HANDOVER.md                          ← 本文件（交接文档）
│   ├── research-6.4.md                      ← 第一天：全面探索失败
│   ├── research-6.5.md                      ← 第二天：核心突破
│   └── research-6.6.md                      ← 第三天：Ghidra+Frida
│
├── 04_message_model.md                       ← Message Model V1
├── 05_export_architecture.md                 ← 内存导出架构设计
├── memory_export_architecture.md             ← 导出架构（早期版）
├── Exporter_Architecture_V1.md              ← 完整导出架构设计
├── Memory_Exporter_V0.1_Feasibility_Report.md ← MVP 可行性评估
│
├── Weixin_Business_Object_Map_V1.md         ← DLL 业务对象地图
├── HookDS_Feasibility.md                    ← Hook 可行性评估
├── HistoryLoader_Confirmation_Report.md     ← HistoryLoader 确认报告
├── msgid_timestamp_final.md                 ← 时间戳验证报告
├── fifth_iteration_report.md                ← 第五次迭代报告
├── m2_getpagedmessages_xref.md             ← M2 Xref 报告
│
├── wechat_4_1_9_56_research_v1.md           ← ★ 综合研究报告（最重要）
│
├── sprint1_result.md                        ← Sprint 1 结果
├── storage_map.md                           ← 存储地图
│
├── v0.1_skeleton/                           ← ★ V0.1 代码骨架（可开始编码）
│   ├── requirements.txt
│   ├── README_V0.1.md
│   └── src/
│       ├── main.py
│       ├── engine.py
│       ├── models/__init__.py               ← Message/Session/ExportResult dataclass
│       ├── reader/weixin_reader.py          ← ProcessReader 骨架
│       ├── scanner/memory_scanner.py        ← MemoryScanner 骨架
│       ├── parser/compact_parser.py         ← CompactParser 骨架
│       └── exporter/json_exporter.py        ← JsonExporter 骨架
│
├── v0.1_design/                             ★ V0.1 设计文档
│   ├── project_structure.md
│   ├── models_design.md
│   ├── process_reader_design.md
│   ├── compact_parser_design.md
│   ├── json_export_design.md
│   ├── mvp_execution_flow.md
│   └── v0_1_risk_assessment.md
│
├── frida_hook_poc.py                        ← ★ Frida PoC（已验证可运行）
├── run_hook2.py                             ← 参数日志 Hook
├── m5_dump.py                               ← 内存 Dump Hook
├── hook_poc.js                              ← JS Hook 脚本（备选）
│
├── external_GPT_ideas.md                    ← GPT 思路参考
│
├── weixin-decrypte-script/                  ← ZedeX 工具（密钥提取成功）
│   ├── scan_keys.py                         ← ✅ 密钥提取成功（21 个）
│   ├── found_keys.txt                       ← 密钥列表
│   ├── decrypt_db.py                        ← ❌ 解密失败
│   └── ...
│
└── 导出结果_截图/                            ← 截图工具产出（已停用）
```

---

## 四、已确认的核心结论

### 存储模型

| 结论 | 证据 | 确认度 |
|------|------|--------|
| 聊天记录不在磁盘 | 35063 文件搜索 TEST_RAY=0 匹配 | **Confirmed** |
| 聊天记录在 Weixin.exe 内存 | pymem 57 匹配 + Frida 验证 | **Confirmed** |
| 离线可翻大量历史 | 断网后仍可翻页查看数月前消息 | **Confirmed** |
| 历史消息本地存储 | 离线 GetPagedMessages 10 次命中 | **Confirmed** |
| SQLite/LevelDB/MMKV 不存消息 | 全盘搜索 + ProcMon 无 .db 访问 | **Confirmed** |

### 消息对象模型

| 字段 | 来源 | 确认度 |
|------|------|--------|
| content | 紧凑结构 + ProtoBuf | **Confirmed** |
| sequence | 紧凑结构（30+ 条验证，同会话 +1） | **Confirmed** |
| receiver | ProtoBuf + 记录区 0x73 | **Confirmed** |
| timestamp | ProtoBuf field4（20 秒间隔实验） | **Confirmed** |
| chatroom_id | 记录区 0x76 | **Confirmed** |
| chatroom_name | 记录区 0x77（中文 UTF-8） | **Confirmed** |
| user_id | 紧凑结构常量 6a 22 5e | Likely |

### 消息存储格式

| 格式 | 特点 | 数据量 |
|------|------|--------|
| 紧凑结构（34B/条） | 易失缓存，窗口切换后清除 | ~25 条 |
| ProtoBuf | 完整字段，可能残留 | 多条副本 |
| 记录区 | 键值对，receiver/chatroom 映射 | 不定 |

### GetPagedMessages 函数

| 属性 | 值 |
|------|-----|
| 函数名（Ghidra） | FUN_1816ade70 |
| DLL 偏移 | 0x016ade70 |
| 运行时地址 | Weixin.dll 基址 + 0x016ade70 |
| 首指令 | PUSH RBP（0x55）|
| 调用者 | 3 个（FUN_181633180, FUN_181641530, FUN_1845d92f0）|
| 字符串 xref | 9 个 xref（"GetPagedMessages"×2 + "has messages"×7）|
| 参数模型 | arg0=全局管理器, arg1=全局常量, arg2=PagingContext, arg3=arg2+0x20 |

### PagingContext 结构体（arg2）

| 偏移 | 内容 | 确认度 |
|------|------|--------|
| +0x000 | receiver wxid（filehelper 内联/其他为指针） | **Confirmed** |
| +0x028 | 候选 MsgID / 时间戳（每次翻页变化） | Likely |
| +0x030 | 候选计数器 | Likely |
| +0x188 | 候选序号（递增） | Likely |

---

## 五、走过的死路（不要重复尝试）

### 数据库路线
- ❌ 自己写 pymem 提密钥（算法不匹配）
- ❌ ZedeX/weixin-decrypte-script（13 库全失败）
- ❌ chatlog decrypt（输出 0 字节）
- ❌ SQLCipher PRAGMA 直接解密（数据库已锁/参数不匹配）

### 自动翻页路线
- ❌ keyboard.send("page up") / keybd_event / SendInput 全部 19 种方法无效
- ❌ 微信 Chromium WebView 拦截所有程序化输入
- ❌ 鼠标滚轮 / 拖拽 / Frida 均无法翻页
- **物理 PageUp 键是唯一有效的翻页方式**

### 其他
- ❌ Accessibility / UI Automation（Qt+Chromium 无法访问）
- ❌ Frida Hook 导出名（Weixin.dll 符号被 strip）
- ❌ 长字符串全盘搜索（A1 有 25110 假阳性）

---

## 六、现有的可用工具

### ✅ 可立即使用的
| 工具 | 位置 | 功能 |
|------|------|------|
| `scan_keys.py` | `weixin-decrypte-script/` | 从内存提取数据库密钥 |
| `chatlog`（Go 编译） | `C:\Users\OK\go\bin\chatlog.exe` | 数据库解密（V4 不支持） |
| `run_hook2.py` | `当前目录` | Frida Hook 记录参数 |
| `m5_dump.py` | `当前目录` | 内存 Dump PagingContext |

### ✅ V0.1 代码骨架
`v0.1_skeleton/` 目录下已有完整项目骨架，包含：
- 数据模型（Message, Session, ExportResult）
- ProcessReader 接口 + WeixinReader 骨架
- MemoryScanner 骨架
- CompactParser 骨架（34B 结构解析）
- JsonExporter / MarkdownExporter 骨架

**下一步就是把这些骨架功能的 TODO 实现成真实代码。**

---

## 七、未解决问题

| 问题 | 优先级 | 说明 |
|------|--------|------|
| 存储层位置未知 | **P0** | 离线可翻大量历史，但 35063 文件 0 匹配。可能存储在非标准目录/非标准格式 |
| 返回值结构未知 | **P0** | GetPagedMessages 返回的消息列表格式未分析（需要 Hook onLeave）|
| 离线历史消息存储 | **P0** | 用户确认断网可翻数月历史，一定有本地存储 |
| MsgID 字段待确认 | P1 | ProtoBuf field5 疑似 MsgID |
| 图片/文件存储 | P2 | 未研究 |
| 缓存淘汰机制 | P2 | 紧凑结构何时创建/销毁 |

---

## 八、对话模式说明

本项目的推进方式比较特殊——**每一轮迭代都由 GPT 提供详细的实验指导**，具体流程：

1. 我把当前状态和发现发给 GPT（用纯文本）
2. GPT 回复详细的下一步实验计划（含步骤、成功标准、禁止事项）
3. 我在 Claude Code 中执行实验
4. 实验结果汇报给 GPT
5. 重复

### 关键协作工具
- **GPT**：提供实验设计、方向判断、架构建议
- **Claude Code（我）**：执行实验、写代码、分析结果
- **用户（Ray）**：操作微信（发消息、翻页、装工具）、提供反馈

---

## 九、下一步建议

### 短期（下一轮迭代）
```
最高优先级：M6 — 返回值分析
  用 Frida Hook onLeave 捕获返回值
  判断返回的消息列表格式（ProtoBuf? 数组?）
  如成功，可直接进入 M7（消息对象恢复）

次优先级：存储层定位
  离线可翻历史说明一定有本地存储
  可能方向：微信安装目录、沙箱、非标准扩展名
  建议：正常打开微信 → 搜文件系统修改时间最新的文件
```

### 中期（V0.1 实现）
```
基于已知的紧凑结构（34B）实现基础导出器
可以导出当前可见 ~25 条消息的 content + sequence
虽然有限，但这是目前唯一不依赖 Hook 的可行路径
```

### 长期
```
完整 HookDS → 拦截 GetPagedMessages → 翻页导出全量历史
需要分析返回值结构 → 编写 ProtoBuf 解析器 → 导出
```

---

## 十、特别提醒

1. **用户不能一直远程操作电脑**，设计实验时要考虑用户可操作的时间窗口
2. **GitHub 网络受限**，从本环境无法直接访问，需要用户手动上传
3. **Ghidra xref 已经做完**，函数地址已验证，**不需要重做**
4. **Frida PoC 已验证可运行**，直接基于 `run_hook2.py` 修改即可
5. **紧凑结构是已知的易失缓存**，导出器需要先让用户打开聊天窗口
6. **所有结论标注了确认度**（Confirmed/Likely/Hypothesis），不要混写
7. **Ghidra 分析产生的 ghidra_projects 目录有锁文件**，删除后才能重分析
