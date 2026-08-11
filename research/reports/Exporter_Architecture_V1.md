# WeChat V4 Exporter — Architecture V1

> 设计目标：为微信 4.1.9.56 设计一个可扩展的聊天记录导出器架构。
> 当前状态：架构设计阶段，未进入实现。

---

## 1. 核心对象模型

```
Message
├── sequence: int          ← 同会话内序号，逐条 +1
├── content: string         ← 消息文本（明文）
├── receiver: string        ← 接收者 wxid / "filehelper"
├── timestamp: int          ← Unix 秒级时间戳
├── msg_id: uint64          ← 服务器消息 ID
├── source: string          ← 消息源信息 (<msgsource> XML)
├── chatroom_id: string?    ← 群聊 ID（仅群聊）
├── chatroom_name: string?  ← 群聊名称（仅群聊）
└── attachments: Attachment[]?  ← 附件列表

Session
├── id: string              ← 会话标识（wxid / chatroom_id）
├── name: string            ← 会话显示名称
├── type: enum              ← 单聊 / 群聊 / 公众号
├── latest_sequence: int    ← 最新消息序号
├── unread_count: int       ← 未读数
└── messages: Message[]     ← 消息列表

Contact
├── wxid: string            ← 微信号（唯一标识）
├── nickname: string        ← 昵称
├── remark: string          ← 备注名
├── alias: string           ← 别名
├── avatar: bytes?          ← 头像数据
└── type: enum              ← 联系人 / 公众号 / 群聊

ChatRoom
├── id: string              ← 群聊 ID (@chatroom)
├── name: string            ← 群名
├── owner: string           ← 群主 wxid
├── members: Contact[]      ← 成员列表
└── notice: string          ← 群公告

Attachment
├── type: enum              ← 图片 / 文件 / 语音 / 视频
├── name: string            ← 文件名
├── size: int               ← 文件大小
├── path: string            ← 导出路径
└── metadata: map           ← 类型相关元数据

ExporterContext
├── app_version: string     ← 微信版本
├── export_time: datetime   ← 导出时间
├── data_source: string     ← 数据来源
├── my_wxid: string         ← 当前用户 wxid
├── sessions: Session[]     ← 导出的会话列表
└── total_messages: int     ← 总消息数
```

---

## 2. 模块架构

```
┌─────────────────────────────────────────────────────┐
│                    CLI / GUI Layer                    │
├─────────────────────────────────────────────────────┤
│                        │                              │
│                  Exporter Engine                       │
│                        │                              │
│   ┌────────────────────┼────────────────────┐         │
│   │                    │                    │         │
│   ▼                    ▼                    ▼         │
│ DataSource          Parser               Exporter     │
│   │                    │                    │         │
│   │ ┌──────────┐   ┌──────┐    ┌──────┐   │         │
│   │ │MemoryScan│   │Compact│   │ JSON │   │         │
│   │ │HookDS   │   │Proto  │   │ CSV  │   │         │
│   │ │FileDS   │   │Raw    │   │ MD   │   │         │
│   │ └──────────┘   └──────┘    └──────┘   │         │
│   └────────────────┴────────────────────┘         │
└─────────────────────────────────────────────────────┘
```

### 2.1 DataSource 层

负责从不同来源获取原始消息数据。

```
interface DataSource:
    name() -> string                           // 数据源名称
    initialize() -> bool                       // 初始化
    get_sessions() -> List<Session>            // 获取会话列表
    get_messages(session, start, limit) -> List<Message>  // 获取消息
    get_contacts() -> List<Contact>            // 获取联系人
    get_chatrooms() -> List<ChatRoom>          // 获取群聊
    close()                                    // 清理
```

**内置实现：**

| DataSource | 来源 | 原理 | 优先级 |
|-----------|------|------|--------|
| MemoryScanDS | 堆内存 | 搜索 `1b 02 05 09 01 01 04`，34B 步长遍历 | ⭐ 推荐主方案 |
| HookDS | 运行时 Hook | Hook GetPagedMessages / MessageListToDB | ⭐ 推荐增强方案 |
| FileDS | 本地文件 | 解析微信本地缓存文件 | 待验证 |

### 2.2 Parser 层

负责将原始二进制数据解析为 Message 对象。

```
interface Parser:
    name() -> string                          // 解析器名称
    can_parse(data: bytes) -> bool            // 是否可解析
    parse_messages(data: bytes) -> List<Message>  // 解析消息列表
    parse_message(data: bytes) -> Message     // 解析单条消息
```

**内置实现：**

| Parser | 输入 | 对应 DataSource |
|--------|------|-----------------|
| CompactParser | 34B 固定结构 | MemoryScanDS |
| ProtoBufParser | ProtoBuf 消息 | HookDS |
| RawParser | 未处理二进制 | 调试用 |

### 2.3 Exporter 层

负责将 Message 对象输出为目标格式。

```
interface Exporter:
    name() -> string
    extension() -> string                     // 文件扩展名
    export(context: ExporterContext, path: string) -> bool
    export_session(session: Session, path: string) -> bool
```

**内置实现：**

| Exporter | 格式 | 适合场景 |
|----------|------|----------|
| JsonExporter | JSON | 程序处理、导入其他工具 |
| CsvExporter | CSV | Excel 分析 |
| MarkdownExporter | MD | 人类阅读 |
| HtmlExporter | HTML | 可视化浏览 |

### 2.4 Engine 层

统筹协调 DataSource → Parser → Exporter 的流程。

```
class ExporterEngine:
    run(config: Config) -> bool:
        1. 初始化 DataSource
        2. 获取所有会话
        3. 对每个会话:
           a. 获取消息列表
           b. 用 Parser 解析
           c. 用 Exporter 输出
        4. 生成上下文报告
```

---

## 3. 导出格式分析

| 格式 | 大小 | 可读性 | 可解析性 | 中文支持 | 推荐度 |
|------|------|--------|----------|----------|--------|
| JSON | 中 | 差 | ⭐⭐⭐ | ✅ | 首选（数据处理）|
| CSV | 小 | 中 | ⭐⭐⭐ | ⚠️ 需处理换行 | 中等（数据量太大时）|
| Markdown | 大 | ⭐⭐⭐ | ⭐ | ✅ | 人类阅读 |
| HTML | 大 | ⭐⭐⭐ | ⭐ | ✅ | 可视化浏览 |

**推荐输出策略：**
- 默认输出 JSON（程序可读）
- 同时生成 Markdown 版本（人类可读）
- 大数据量时提供 CSV 选项

---

## 4. 插件机制

```
interface Plugin:
    name() -> string
    version() -> string
    type() -> enum             // datasource / parser / exporter
    initialize(config) -> bool
    cleanup()
```

**扩展点：**

| 扩展点 | 接口 | 未来可能实现 |
|--------|------|-------------|
| 数据源 | IDataSource | 企业微信、QQ、钉钉 |
| 解析器 | IParser | 3.x MSG.db 解析器、macOS 解析器 |
| 输出格式 | IExporter | PDF、TXT、SQLite 数据库 |
| 过滤器 | IFilter | 关键词过滤、日期范围、联系人过滤 |
| 转换器 | IConverter | 图片解密、语音转文字 |

---

## 5. 目录结构

```
wechat-exporter/
├── README.md
├── requirements.txt          ← Python 依赖
├── config.yaml               ← 默认配置
│
├── src/
│   ├── main.py               ← CLI 入口
│   ├── engine.py             ← ExporterEngine
│   ├── models.py             ← 数据模型 (Message, Session, Contact...)
│   ├── context.py            ← ExporterContext
│   │
│   ├── datasource/
│   │   ├── __init__.py
│   │   ├── base.py           ← DataSource 接口
│   │   ├── memory_scan.py    ← MemoryScanDS
│   │   ├── hook_ds.py        ← HookDS
│   │   └── file_ds.py        ← FileDS
│   │
│   ├── parser/
│   │   ├── __init__.py
│   │   ├── base.py           ← Parser 接口
│   │   ├── compact.py        ← CompactParser (34B 结构)
│   │   ├── protobuf.py       ← ProtoBufParser
│   │   └── raw.py            ← RawParser
│   │
│   ├── exporter/
│   │   ├── __init__.py
│   │   ├── base.py           ← Exporter 接口
│   │   ├── json_exporter.py
│   │   ├── csv_exporter.py
│   │   ├── markdown_exporter.py
│   │   └── html_exporter.py
│   │
│   ├── plugin/
│   │   ├── __init__.py
│   │   └── loader.py         ← 插件加载器
│   │
│   └── utils/
│       ├── pymem_helper.py   ← 内存读写工具
│       ├── proto_reader.py   ← ProtoBuf 简易解析
│       └── logger.py         ← 日志工具
│
├── plugins/                  ← 第三方插件
│
├── output/                   ← 导出结果
│
├── tests/
│   ├── test_parser_compact.py
│   ├── test_parser_protobuf.py
│   └── test_exporters.py
│
└── docs/
    ├── architecture.md       ← 本文档
    ├── message_model.md      ← Message Model V1
    └── datasource_comparison.md
```

---

## 6. 未来路线图

```
Phase 1 — 基础导出（当前）
  ├── MemoryScanDataSource
  ├── CompactParser
  ├── JsonExporter + MarkdownExporter
  └── 支持当前会话 ~25 条消息
  └── 预计工作量: 3-5 天

Phase 2 — 深度导出
  ├── HookDataSource (Frida)
  ├── GetPagedMessages 拦截
  ├── 翻页加载历史消息
  └── 预计工作量: 5-10 天（含 Frida hook 开发）

Phase 3 — 全量导出
  ├── 图片/文件解密
  ├── 多会话批量导出
  ├── 增量导出（断点续传）
  └── 预计工作量: 5-7 天

Phase 4 — 生态建设
  ├── 插件 API 稳定
  ├── 企业微信支持
  ├── GUI/TUI 界面
  └── CLI 工具发布
```

---

## 7. 设计原则

1. **DataSource 与 Parser 分离**
   - 同一数据源可换不同解析器
   - 同一解析器可接不同数据源

2. **Parser 与 Exporter 分离**
   - 解析结果统一为 Message 对象
   - Exporter 只处理 Message 对象，不关心来源

3. **增量可验证**
   - 每个 Phase 产出可运行的导出工具
   - 不追求一步到位

4. **错误不中断**
   - 单个消息解析失败不影响整体导出
   - 导出报告记录失败详情
