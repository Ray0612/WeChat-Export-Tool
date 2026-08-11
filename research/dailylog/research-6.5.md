# 微信 4.1.9.56 研究日志 — 2026-06-05

> 第二天：核心突破日 — 消息模型建立 + 业务对象发现

---

## 上午：第三次迭代 — 数据定位

### GPT 指导
- **核心问题**：微信 4.1.9.56 的聊天记录到底存储在哪里？
- **假设**：A. SQLite位置变化 B. 新数据库(LevelDB/MMKV) C. WeChatAppEx子进程管理

### Task 2：存储数据地图（9:00-10:00）
- **扫描范围**：`AppData\Roaming\Tencent` + `AppData\Local\Tencent`
- **结果**：1425 个文件（.db .dat .bin .log 等）
- **关键发现**：
  - ❌ 不存在 `contact.db`、`message*.db`、`session.db`
  - ✅ 唯一的 .db 文件是 `applet.db`（6.2MB，但不是聊天数据库）
  - 🔍 发现 IndexedDB LevelDB 存储：`xwechat/radium/web/profiles/.../IndexedDB/`
  - 🔍 发现 MMKV 存储：`xwechat/radium/users/<hash>/mmkv/`
- **结论**：SQLite 路线基本排除

### Task 1：ProcMon 动态追踪（10:00-11:00）
- **操作**：用户手动打开 ProcMon → 设置过滤条件 → 记录微信进程文件操作
- **PML 分析**：24MB 日志文件，搜索 .db / .sqlite / .ldb
- **结果**：
  - 572 次 xwechat 访问（主要是 config.ini 和插件配置）
  - 0 次 .db 文件访问
  - 0 次 .sqlite 文件访问
- **结论（Confirmed）**：微信进程在聊天操作期间不访问任何数据库文件

### Task 4：IndexedDB/LevelDB 分析（11:00-12:00）
- **目标**：`weixin_xworker_0.indexeddb.leveldb/`
- **方法**：二进制搜索关键字符串（联系人、chatroom、message）
- **结果**：数据为 Web 配置信息，无聊天消息内容

### 发送唯一消息实验（12:00-12:30）
- **操作**：用户发送 `TEST_RAY_20260605_938274615` → 关闭微信
- **全盘搜索**：35063 个文件，0 匹配（UTF-8 + UTF-16LE 均搜索）
- **结论（Confirmed）**：聊天消息不在磁盘上

---

## 下午：第四次迭代 — 内存验证

### GPT 指导
- **目标**：确认消息是否仅存在于内存

### 内存验证实验（14:00-14:30）
- **方法**：重启微信 → 确认消息显示 → `pymem.pattern_scan_all()` 搜索
- **结果**：TEST_RAY 在 Weixin.exe 内存中发现 **57 个匹配**
- **结论（Confirmed）**：消息在 Weixin.exe 堆内存中以明文 ASCII 存在

---

## 下午-晚间：第五次迭代 — 消息对象模型

### GPT 指导
- **目标**：从"找数据"转向"理解消息对象结构"

### 紧凑结构深入分析（15:00-16:00）
- **地址**：`0x1f4726220ee` 附近
- **发现**：连续消息队列，每条 34 字节，**倒序排列**（新消息在前）
- **序列号验证**：HELLO_5(335) → HELLO_1(331) → TEST_AAAAA(330)
- **同会话内逐条 +1 递增（Confirmed）**

### 消息结构解析（16:00-17:00）
```
+0: 1b 02 05 09 01 01 04   前缀
+7: 消息文本
+?: 04                      分隔符
+?: 序列号 2字节             小端序 uint16
+?: 9e 96 xx               session_tag
+?: 6a 22 5e xx            user_id
```

### ProtoBuf 结构发现（17:00-18:00）
- **地址**：`0x1f40b1111d4`
- **结构**：
```
field1 = 1
field2.receiver = "filehelper"
field2.content = "HELLO_1"
field3 = 1
field4 = 27145628745 → **时间戳候选**
field5 = 40645169484
field6 = "<msgsource>..."
```

### 结构化记录区发现（18:00-18:30）
- **地址**：`0x1f448dd44d0`
- **结构**：键值存储区
- **关键键码**：
  - `0x73` → wxid（✅ 对方微信号）
  - `0x76` → @chatroom（✅ 群聊 ID）
  - `0x77` → 中文群名（✅ "科技1班班委群"）

---

## 晚间：第六/七次迭代 — 时间戳验证

### GPT 指导
- **目标**：确认 field4/filed5 是 MsgID 还是 Timestamp

### 时间戳实验（20:00-20:30）
- **操作**：发送 TIME_TEST_A(13:47:35)、TIME_TEST_B(13:47:45)、TIME_TEST_C(13:47:55)
- **结果**：
  ```
  TIME_TEST_A: field4 = 1,780,638,454
  TIME_TEST_C: field4 = 1,780,638,474
  差值 = +20（精确匹配 20 秒间隔）
  ```
- **结论（Confirmed）**：**field4 = Unix 秒级时间戳**，field5 不是时间戳

### 会话切换实验（20:30-21:00）
- **操作**：切换到另一个联系人 → 对比参数变化
- **发现**：联系人 `wxid_049vxvhc4asy22` 的 wxid 出现在记录区

---

## 深夜：第八次迭代 — 导出架构设计

### GPT 指导
- **目标**：设计可扩展的导出器架构

### 成果
- `Exporter_Architecture_V1.md` — 模块化架构设计
- `Memory_Exporter_V0.1_Feasibility_Report.md` — MVP 可行性评估
- `v0.1_design/` — 7 个详细设计文档

### V0.1 目录结构
```
src/
├── main.py                    CLI 入口
├── engine.py                  ExporterEngine
├── models/                    Message/Session/ExportResult
├── reader/                    WeixinReader(pymem)
├── scanner/                   MemoryScanner
├── parser/                    CompactParser
└── exporter/                  JsonExporter/MarkdownExporter
```

---

## 第二日总结

| 迭代 | 成果 | 状态 |
|------|------|------|
| 第三次 | 数据定位 → ❌ 不在磁盘 | ✅ 完成 |
| 第四次 | 内存验证 → ✅ 在 Weixin.exe | ✅ 完成 |
| 第五次 | 消息模型 → ✅ 7 个字段确认 | ✅ 完成 |
| 第六次 | MsgID/Timestamp → ✅ field4=时间戳 | ✅ 完成 |
| 第七次 | 导出架构 → ✅ 完整设计 | ✅ 完成 |

### Message Model V1（最终确认 7 个字段）

| 字段 | 确认度 | 证据 |
|------|--------|------|
| content | Confirmed | 3 种格式交叉验证 |
| sequence | Confirmed | 30+ 消息逐条 +1 递增 |
| receiver | Confirmed | ProtoBuf + 记录区 |
| timestamp | Confirmed | 20 秒间隔实验 |
| user_id | Likely | 紧凑结构常量 6a 22 5e |
| chatroom_id | Confirmed | 记录区 0x76 |
| chatroom_name | Confirmed | 记录区 0x77（中文 UTF-8） |

---

## 文件产出

- `storage_map.md` — 全盘存储扫描结果
- `第三/四/五次迭代报告.md` — 迭代报告
- `msgid_timestamp_final.md` — 时间戳验证报告
- `memory_export_architecture.md` — 导出架构
- `Message_Model_V1.md` — 消息模型文档
- `v0.1_design/` — 7 个设计文档
- `v0.1_skeleton/` — 17 个 Python 骨架文件
- `coding_sprint_v0_1.md` — Sprint 1 报告
- `wechat_export_sprint1.txt` — 首次成功导出的 20 条消息
