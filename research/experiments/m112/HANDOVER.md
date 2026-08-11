# 微信 4.1.10.29 导出项目 — 交接文档

> 编写时间：2026-06-07 22:00
> 研究周期：2026-06-04 ~ 2026-06-07（4 天）
> 里程碑总数：80+ 轮
> 当前阶段：GUI 版开发 + 验证

---

## 一、项目概况

### 目标
开发微信 4.1.x (Windows) 的聊天记录导出工具。

### 当前状态
- 研究阶段已完成 ✅
- GUI 版 v1.0 可运行 ✅
- 内存捕获 + 解析 + 展示 + 导出链路已打通 ✅
- 已知有若干待修问题 🔧

### 核心结论
1. 聊天消息不在磁盘（35063 文件搜索 0 匹配）
2. 消息在 Weixin.exe 进程堆内存中
3. 通过手机备份触发，可在共享内存中捕获 LevelDB 格式的消息数据
4. 文本以紧凑结构（39B，前缀 `XX 02 05 09 01 01 04`）内联存储
5. 历史层在 Chromium LevelDB 中，完整访问需要分析 WeChatAppEx.exe

---

## 二、项目结构

```
C:\Users\OK\Desktop\wechat_v4_export_research\
├── README.md
├── .gitignore
├── config.json              # 用户配置（昵称映射、身份 wxid）
├── run_gui.py               # GUI 启动入口
│
├── gui/                     # GUI 应用代码
│   ├── app.py               # 主界面 + 内存监控 + 自动解析
│   ├── data_manager.py      # 数据加载 + 会话聚类
│   ├── config.py            # 配置管理
│   └── exporter.py          # TXT/MD 导出
│
├── scripts/                 # 实验脚本
│   ├── m36_compact_exporter.py   # 紧凑结构导出器（M36 核心产出）
│   ├── m59_full_parse.py         # LevelDB 全量解析器
│   ├── m73_capture_verify.py     # 内存捕获验证（GROWN 检测）
│   └── m74_fresh_capture.py      # 全新捕获管线
│
├── experiments/
│   ├── logs/                # 解析后的 JSON/TXT 数据
│   │   ├── m74_parsed.json  # ← 当前 GUI 读取的数据文件
│   ├── dumps/               # 原始 dump 文件（363 个 .bin）
│   ├── m57_v3/              # 历史 dump（162 个，已被清理）
│   └── m73_test/            # M73 验证输出
│
├── reports/                 # 15+ 份分析报告
│   ├── final_project_report.md
│   ├── project_status_to_gpt.md
│   └── ...
│
├── daily/                   # 每日研究日志
├── design/                  # V0.1 设计文档
├── references/              # Ghidra 分析文档 + 交接文档
└── mac_ghidra_task.md
```

---

## 三、核心文件说明

### run_gui.py — 启动入口
```bash
python run_gui.py
```
- 首页：开始监测 → 触发手机备份 → 自动捕获 → 自动解析
- 会话列表：显示所有会话（按 wxid 分组）
- 聊天详情：按时间排序，一来一回显示
- 昵称管理：右键改名 / 群成员独立昵称
- 导出：TXT / Markdown
- 重置数据：清空捕获和解析数据（保留昵称配置）

### gui/data_manager.py — 数据加载
- 自动搜索 `experiments/logs/` 下的 JSON 文件
- 优先级：`m74_parsed.json` > `m66_structured.json` > `m65_by_conversation.json`
- 支持 m61/m65/m66/m74 四种格式
- `_normalize()` 过滤 type 2000/2001/62 系统消息
- 未知发送者的消息归入「未识别发送者的消息」会话

### gui/app.py — 核心功能
- **`start_monitor()`**: 500ms 扫描 Weixin.exe 内存，检测 NEW + GROWN 区域
- **`auto_parse()`**: 解析 dump 文件 → 提取 XML → 去重 → 保存 m74_parsed.json
- **`refresh_chat_view()`**: 按时间排序显示消息，我/对方颜色区分
- **`check_identity()`**: 身份识别弹窗
- **`edit_member_nicknames()`**: 群成员独立昵称编辑
- **`reset_data()`**: 重置按钮（清空 dump + parsed）

---

## 四、消息类型映射

| type | 含义 | 说明 |
|------|------|------|
| 1 | 文本 | 纯文本消息 |
| 6 | 文件 | docx/pdf/zip 等 |
| 19 | 合并转发 | 收藏的聊天记录 |
| 33 | 链接 | 小程序/网页链接 |
| 36 | 语音 | 语音消息 |
| 47 | 表情 | emoji 动画表情 |
| 49 | 转发 | 消息转发 |
| 51 | 视频 | 视频消息 |
| 53 | 接龙 | 群接龙 |
| 57 | 聊天卡片 | 分享卡片/引用消息 |
| 62 | 拍一拍 | "拍一拍" 系统消息 |
| 2000 | 转账 | 微信转账 |
| 2001 | 红包 | 微信红包 |

---

## 五、数据流

```
手机触发备份
  ↓
Weixin.exe 分配/增长共享内存区域（363 个文件, ~150MB）
  ↓  (500ms 轮询 + GROWN 检测)
dump .bin 文件
  ↓  (auto_parse / m59_full_parse.py)
解析 XML <msg> 节点（re.DOTALL 必须！）
  ↓  (提取 fromusername/tousername/content/type/timestamp)
去重（content[:80] + from）
  ↓  (DataManager._normalize)
过滤系统消息（type 2000/2001/62）
  ↓  (DataManager._add_session)
按会话聚类（from/to → session）
  ↓
m74_parsed.json
  ↓
GUI 展示 + 导出
```

### 关键注意点
1. `re.findall(r'<msg>.*?</msg>', txt, re.DOTALL)` — **必须加 re.DOTALL**，否则跨行 `<msg>` 块会漏掉
2. `fromusername` 可能出现在 `<emoji>` 等子元素上，不在 `<msg>` 直接属性里
3. `type` 可能是 `<type>N</type>` 标签或 `type="N"` 属性
4. `<appmsg>` 消息通常不带 `fromusername`（发送者信息在独立结构中）
5. 同一个消息会出现在多个 dump 文件中（区域重叠），需要去重

---

## 六、当前待解决问题

### 1. 未识别发送者过多
- 363 个 dump 文件 → 11,042 条 <msg> → 3,030 去重 → 162 条带 wxid
- 大部分消息来自 `<appmsg>` 格式，LevelDB dump 中不含 `fromusername`
- **可能需要换捕获方式**（Frida Hook WeChatAppEx.exe 的 IndexedDB API）

### 2. type 2000（转账）仍在未识别会话中
- `_normalize()` 已过滤 type 2000/2001/62 无 from 的消息
- 但仍有少部分残留（待确认）

### 3. 昵称映射不彻底
- 会话列表显示昵称 ✅
- 聊天窗口显示昵称 ✅
- 但消息发送者仍然显示 wxid（需要用户手动设昵称）

### 4. GUI 偶发崩溃
- `rmargin1` 参数在 Windows Tk 上不支持（已修）
- 线程安全问题（auto_parse 在 monitor 线程中写 tk 变量）

### 5. 数据文件路径硬编码
- `app.py` 中 `experiments/dumps/` 和 `experiments/logs/m74_parsed.json` 是硬编码的
- `data_manager.py` 的 `DATA_FILES` 列表需要手动维护

---

## 七、关键函数地址（v4.1.10.29）

| 函数 | DLL 偏移 | 说明 |
|------|---------|------|
| Caller1 | `0x01683b08` | 翻页入口 |
| GetPagedMessages | `0x016ff6b0` | 消息加载 |
| FUN_1816c2a20 | `0x016c2a20` | 消息过滤遍历（步长 0x2d8） |
| FUN_1816c2a20 循环体 | `0x016c2a76` | R14 指向当前 0x2d8 元素 |
| FUN_1816f3b30 | `0x016f3b30` | GetMessageListBySvrIds |
| FUN_1816f3510 | `0x016f3510` | 消息缓存（0x2f0 分配） |
| FUN_181bc3b00 | `0x01bc3b00` | **0x2d8 Creator** |
| Weixin.dll 基址 | `0x7fff08db0000` | ASLR 后运行时地址 |

---

## 八、已知死路（不要重复尝试）

| 方向 | 原因 |
|------|------|
| 数据库解密 | V4 不使用 SQLite |
| 自动翻页 | Chromium 拦截所有程序化输入 |
| 文件 API Hook | 翻页时不读文件 |
| 反向指针追踪文本 | 文本内联存储 |
| WeChatAppEx.exe 找消息 | M55 确认 AppEx 中不含消息文本 |
| 0x2d8 后处理 | 生命周期极短，离开页面即释放 |

---

## 九、下一步建议

| 方向 | 工作量 | 说明 |
|------|--------|------|
| **A. 修复未识别发送者** | 2-3 天 | 分析 LevelDB 存储格式，找到 from 字段的真实存储位置 |
| **B. 改用 Frida Hook** | 3-5 天 | Hook WeChatAppEx.exe 的 IndexedDB API，实时捕获原始消息 |
| **C. GUI 工程化** | 2-3 天 | 打包 exe、修 bug、优化 UI |
| **D. 工程化 M36** | 1-2 天 | 将紧凑结构导出器打包成独立 CLI |
| **E. 推 GitHub** | 0 天 | 立即推送 |

---

## 十、环境

| 项目 | 内容 |
|------|------|
| OS | Windows 11 中文版 |
| Python | 3.13.5 |
| 微信 | 4.1.10.29 |
| 核心 DLL | Weixin.dll (175MB) @ 0x7fff08db0000 |
| 依赖 | tkinter, pymem 1.14, psutil |
| Weixin.exe PID | 6312（重启后会变） |
| 数据目录 | `AppData\Roaming\Tencent\xwechat\` |
