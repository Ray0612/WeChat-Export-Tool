# 微信聊天记录导出研究 — 交接文档

> 研究时间: 2026-06-07 ~ 2026-06-11 (约50小时)
> 微信版本: 4.1.10.29 (当前 wx_key/Frida 均不支持此版本)
> 账号: wxid_caccoealsdbj12
> 数据库路径: D:\储存信息\xwechat_files\wxid_caccoealsdbj12_e8c8\db_storage\message\message_0.db

---

## 一、项目结构

```
C:\Users\OK\Desktop\wechat_v4_export_research\
├── gui/                          # M74 GUI 版导出工具 (tkinter)
│   ├── app.py                    # 主界面
│   ├── data_manager.py           # 数据加载
│   ├── config.py                 # 配置
│   └── exporter.py               # TXT/MD 导出
├── scripts/                      # 各类实验脚本
│   └── m112_routeA/              # M112 消息文本提取 + key 捕获脚本
├── tools/                        # 第三方工具
│   ├── echotrace/                # EchoTrace 微信导出 (Flutter)
│   ├── wx_key/                   # wx_key 密钥提取 (含预编译 DLL)
│   └── weixin-decrypte-script/   # Windows 4.x 解密脚本
├── db_exporter/                  # 数据库导出框架（待 key）
├── experiments/                  # 实验结果
│   ├── m81-m105/                 # 各阶段实验数据
│   └── m90-m105/                 # 近期实验
├── dailylog/                     # 研究日志
├── config.json                   # 昵称映射
└── run_gui.py                    # 启动入口
```

---

## 二、已确认的数据库结构

### 2.1 message_0.db 表结构 (SQLCipher 加密)

**Msg_ 表 (426 个, 每会话一个):**
```sql
CREATE TABLE Msg_<md5_hash>(
  local_id           INTEGER PRIMARY KEY AUTOINCREMENT,
  server_id          INTEGER,        -- svrid (消息服务端ID)
  local_type         INTEGER,        -- 消息类型 (1=文本, 3=图片, 49=分享)
  sort_seq           INTEGER,        -- 排序序列
  real_sender_id     INTEGER,        -- 发送者 (FK → SessionTable.rowid)
  create_time        INTEGER,        -- Unix 时间戳
  status             INTEGER,
  upload_status      INTEGER,
  download_status    INTEGER,
  server_seq         INTEGER,
  origin_source      INTEGER,
  source             TEXT,
  message_content    TEXT,            -- 消息文本内容
  compress_content   TEXT,
  packed_info_data   BLOB,
  WCDB_CT_message_content INTEGER,
  WCDB_CT_source     INTEGER
);
```

**SessionTable:**
```sql
CREATE TABLE SessionTable(
  username        TEXT PRIMARY KEY,   -- wxid 或 chatroom ID
  type            INTEGER,
  unread_count    INTEGER,
  summary         TEXT,               -- 最后一条消息摘要
  draft           TEXT,
  last_timestamp  INTEGER,
  sort_timestamp  INTEGER,
  last_msg_sender TEXT,               -- 最后发送者
  last_sender_display_name TEXT
);
```

**其他表:** DeleteInfo, DeleteResInfo, TimeStamp, ImgFtsV0/V3 (全文搜索)

### 2.2 会话 → 消息表映射

```
SessionTable.username (wxid_xxx / xxx@chatroom)
    ↓ MD5()
Msg_<md5_hash> 表名
    ↓
real_sender_id = SessionTable.rowid
```

### 2.3 SQLCipher 参数
- 加密类型: PBKDF2-HMAC-SHA1 (64000 迭代)
- 页面大小: 4096 bytes
- 保留字节: 80 bytes/page
- 总页数: 24410 (= 95.4MB)

---

## 三、所有已验证的路线

### ✅ 可用 (可继续使用的)

| 路线 | 说明 | 位置 |
|------|------|------|
| M112 裸文本提取 | 从 WCDB key-value 缓存中提取 3023 条中文消息 | scripts/m112_routeA/extract_raw_texts.py |
| M74 LevelDB 增量捕获 | 微信备份触发时捕获共享内存中的 XML 消息 | gui/app.py (monitor_worker) |
| DB Schema 完整解析 | 426 个 Msg_ 表 + SessionTable | experiments/m88/ |
| SessionTable 查询缓存 | 内存中 wxid + timestamp 缓存 | experiments/m90/ |
| JSON 消息缓存 (AppMsgId) | 最近 3 天消息内容 | experiments/m94/msg_cache.json |
| GUI 导出工具 | TXT/MD 格式，支持会话选择 | gui/ |

### ❌ 不可行 / 已放弃 (已验证死路)

| 路线 | 原因 | 阶段 |
|------|------|------|
| SQLCipher Key 搜索 | UIN/wxid/高熵扫描均无法找到密钥 | M81 |
| 0x2d8 节点实时捕获 | 生命周期极短(毫秒级)，轮询来不及 | M87 |
| 紧凑结构 02 05 09 | v4.1.10.29 中不存在此前缀 | M36 |
| Flutter/Dart 堆 | 只有 UI 渲染副本，无元数据 | M84-M85 |
| SQLite 解密页面缓存 | 数据页用完即释放，只有 Page 1 常驻 | M88 |
| sqlite3 handle 搜索 | 藏于 C++ 对象深处，pymem 无法定位 | M92 |
| protobuf Message 容器 | 对象池滑动窗口，非空率仅 1% | M107-M111 |
| vtable 消息对象扫描 | 0x1b4158 偏移量不正确，非 vtable | M112 |
| 数据库全量导出 | 需 SQLCipher key 或 handle | 贯穿全程 |

### ⚠️ 部分验证 (有发现但未完全打通)

| 路线 | 发现 | 遗留问题 |
|------|------|----------|
| CoGetSessionMessageListWithPageFromDB | 函数签名、参数、调用链已定位 | 需 Frida Hook 运行时验证 |
| MessagePageResult | 在内存中找到实例 (0x1a4092aa570) | 只有 filehelper，vector 为空 |
| 迭代器 (forward_iterator) | +0x08 函数指针 FUN_183659cb0 | 需运行时调用才能遍历结果 |
| C++ 消息对象 (vtable 0x1b4158) | 0x80 字节大小, +0x28=content | 19585 对象仅 1% 非空 |
| 消息分页参数 | page_size=1000, from_localid | 需通过分页遍历全量 |

---

## 四、关键函数与偏移 (Ghidra 分析 weixin.dll)

### CoGetSessionMessageListWithPageFromDB
```
地址: Weixin.dll + 0x360c210
签名: (context, output, index, session_name, page_size, from_localid, config)
RCX = context, RDX = output, R8 = index, R9 = session_name
RSP+0x28 = page_size, RSP+0x30 = from_localid, RSP+0x38 = config
```

### MessagePageResult 结构 (0xA0 bytes)
```
+0x00: 基类 vtable (0x1b4158)
+0x08: null
+0x10: 派生类 vtable (0x1b4308)
+0x18: self-pointer
+0x20: self-pointer  
+0x28: message_content (SSO string ptr) ← 消息文本
+0x30: null/SSO capacity
+0x38: sender/field (SSO string ptr)
+0x40: null
+0x48: field_3 (SSO string ptr)
+0x50: page_size (=1000) (uint32)
+0x54: count/status? (uint32)
+0x58: session_name SSO start (+0x61: session_name text)
+0x78: count (15)
```

### 消息对象结构 (0x80 bytes)
```
+0x00: 基类 vtable (0x1b4158) ← 21241 个共享
+0x08: null
+0x10: 派生类 vtable (0x1b4308) ← 含中文消息内容
+0x18: self-pointer
+0x20: self-pointer
+0x28: message_content (SSO string ptr) ✅
+0x38: sender (SSO string ptr, 可能为空)
+0x48: timestamp/data (SSO string ptr)
```

### flue.dll 关键函数
```
sqlite3_key_v2:  flue.dll + 0x2a9c805
sqlite3_key_v2 内存: WeChatAppEx 进程 flue.dll 基址 + 0x2a9c805
```

---

## 五、运行时环境

### 进程模型
```
explorer.exe
  └── Weixin.exe (PID 变化, 主进程, 持有 message_0.db 句柄)
      ├── Weixin.exe (子进程, UI 渲染)
      ├── WeChatAppEx.exe (多实例, 含 flue.dll, Chromium 沙箱)
      └── ...
```

### 工具可用性
| 工具 | 状态 | 说明 |
|------|------|------|
| pymem | ✅ | 可读写 Weixin.exe 和部分 WeChatAppEx 内存 |
| Frida | ❌ | WeChatAppEx Chromium 沙箱阻挡 DLL 注入 |
| DebugActiveProcess | ⚠️ | 可附加 WeChatAppEx, 但会杀死 Weixin.exe |
| Ghidra | ✅ | 两套分析: Weixin.dll, flue.dll |
| WinDbg | ❌ | 未尝试 |

### 进程重启问题
Weixin.exe 和 WeChatAppEx 频繁重启 (触发条件不明)，导致内存地址不断变化，无法依赖固定地址。

---

## 六、需专业人士继续的方向

### 6.1 Frida Hook (最高优先级)
在 WeChatAppEx 进程中 Hook `flue.dll+0x2a9c805` (sqlite3_key_v2) 或 `CoGetSessionMessageListWithPageFromDB`，捕获返回的消息列表。

需要绕过 Chromium 沙箱:
- 启动时添加 `--no-sandbox` 参数
- 或以管理员身份运行 Frida

### 6.2 WinDbg 内核调试
附加到 Weixin.exe，在 `weixin.dll+0x360c210` 设断点，读取返回的 MessagePageResult。

### 6.3 直接构造 SQLCipher key
通过逆向 flue.dll 中 DeriveKeyPbkdf2HmacSha1 的调用链，找到 passphrase 和 salt 的来源。

### 6.4 CreateRemoteThread + Shellcode
在不支持 Frida 的情况下，手动注入 shellcode 到 WeChatAppEx 调用函数并读取结果。

---

## 七、M112 进展 — 裸文本提取 + Key 提取 (2026-06-10~11)

### 发现: 消息存在于 WCDB key-value 缓存中

通过分析 34935 个中文文本的内存布局，发现消息文本**不存在于 C++ 对象中**，而是存在于 WCDB 内部 key-value 存储格式中。

典型内存布局:
```
+0x00: 字段名 (如 "14.origin_source", "ress_content")
+0x20: 元数据 (UUID, MD5 hash, 文件名)
+0x40: 字段分隔符 (00 00 01 00)
+0x48: 消息文本 (UTF-8 C 字符串, null 终止)
```

特征:
- 无 vtable 指针 (不是 C++ 对象)
- 文本前后有 UUID、MD5 hash、文件名等字段名
- 以 null 结尾的 UTF-8 C 字符串存储

### 提取成果: 3023 条不重复文本
- 干净文本: 2126 条
- 关联到 wxid: 227 条
- 已知发送者: wxid_caccoealsdbj12(98), wxid_a1n0j4x1gg8i22(76), wxid_22e48sxjw2c222(39)

### 当前瓶颈
1. 缺少发送者 wxid 和时间戳 (2126 条中仅 227 条有 wxid)
2. WCDB 缓存格式未完全逆向，无法解析完整结构化记录
3. SQLCipher key 未提取（版本 4.1.10.29 不被工具支持）
4. 已确定 key 函数位置（Weixin.dll + 0x55d0f0），但 hook 时机无法提前

### 脚本位置
```
scripts/m112_routeA/
├── extract_raw_texts.py    — ✅ 核心提取脚本 (3023 条)
├── extract_v2.py           — ✅ V2 提取（带时间戳/wxid）
├── extract_v3.py           — ✅ V3 自适应扫描
├── live_monitor_v2.py      — 实时监控 v2
├── live_monitor_v3.py      — 实时监控 v3 (单会话模式)
├── backup_monitor.py       — 备份过程内存监控
├── backup_monitor_v2.py    — 备份监控 v2 (XML/时间戳)
├── capture_buf.py          — ✅ Buf 文件捕获器 (11593 文件)
├── frida_capture_key.py    — Frida key 捕获
├── frida_full_spawn.py     — Frida spawn+gating 启动
├── capture_key_suspended.py— CREATE_SUSPENDED + Frida
├── capture_key_final.py    — spawn+gating 最终版
├── find_current_cache.py   — 缓存区域定位
├── scan_key_memory.py      — 内存 key 扫描
├── scan_messages_A.py      — vtable 扫描
├── find_vtable.py          — .rdata vtable 枚举
├── find_by_text.py         — 文本回溯找 vtable
├── find_objects.py/2.py    — 对象定位
├── scan_key.py             — SQLCipher key 扫描
├── scan_heaps.py           — 堆区域枚举
├── decrypt_test.py         — 解密参数测试
├── key_search_v2.py        — 综合 key 搜索
├── debug_text.py / dump_text_struct.py — 内存调试
├── use_wx_key.py           — wx_key.dll Python 调用
└── hook_key*.js            — Frida hook 脚本

数据输出: C:\Users\OK\Desktop\wx_export\raw_texts_1781028614.json (3023 条文本)
备份 Buf: C:\Users\OK\Desktop\wx_export\backup_experiment\buf_captures\ (11593 个文件)
```

---

```
C:\Users\OK\Desktop\wx_export\                      — 提取的消息数据
  ├── raw_texts_*.json               — M112 裸文本提取 (3023 条)
  ├── extract_v3_*.json              — M112 V3 提取 (带时间戳)
  ├── live_*.json                    — M112 实时监控增量
  ├── scan_*.json                    — M112 早期扫描
  ├── sqlcipher_key_*.txt            — Key 捕获输出
  ├── session_export_*.json          — 单会话导出
  └── backup_experiment/             — 备份实验数据
      ├── buf_captures/              — Buf 文件 (11593 个)
      ├── file_snapshots/            — 数据库快照
      └── cp_v2_*.json              — 备份 checkpoint

C:\Users\OK\Desktop\wechat_v4_export_research\experiments\
├── m88/       — DB Schema, Page 1 dump, 表结构
├── m89/       — 426 Msg_ 表清单, SessionTable
├── m90/       — 联系人映射, 消息队列
├── m94/       — 结构化缓存, 测试消息
├── m97/       — MessageList 监控日志
├── m100/      — OutputStructure.md, MessagePageResult 分析
├── m104/      — 分页结构最终确认
├── m105/      — MessagePageResult 监控
└── m112/      — M112 路线A: vtable扫描 + 裸文本提取
```

---

## 八、关键文件清单

```
C:\Users\OK\Desktop\wechat_v4_export_research\     — 项目主目录
├── todolist.md                  — 项目 Todo
├── references\WeChat_4.1.10.29_2026_06_06.gar — Ghidra 项目
├── scripts\m112_routeA\         — M112 全套脚本集
│   ├── extract_raw_texts.py     — 裸文本提取 (✅ 成功)
│   ├── capture_buf.py           — Buf 文件捕获 (✅ 11593 文件)
│   ├── frida_full_spawn.py      — Frida spawn+gating
│   ├── capture_key_final.py     — 最终版 key 捕获
│   ├── use_wx_key.py            — wx_key.dll 调用
│   └── ...
└── tools\                       — 第三方工具
    ├── wx_key\assets\dll\wx_key.dll  — 预编译 key 提取 DLL
    ├── echotrace\               — EchoTrace 导出工具
    └── weixin-decrypte-script\  — 解密脚本集

C:\Users\OK\AppData\Roaming\Tencent\xwechat\XPlugin\Plugins\RadiumWMPF\19899\extracted\runtime\
└── flue.dll                     — SQLCipher 库 (201MB, 需 Ghidra 分析)
```

---

## 九、Ghidra 分析进度

**Weixin.dll (175MB) ✅ 已分析**
- 基址: 0x180000000 (Ghidra) / 运行时动态
- 关键函数偏移已知
- 函数签名已还原

**flue.dll (201MB) ✅ 已分析 (部分)**
- 基址: 0x180000000 (Ghidra) / 运行时动态
- sqlite3_key_v2 在 RVA 0x2a9c805
- DeriveKeyPbkdf2HmacSha1 字符串在 .rdata
- 需要更多逆向分析

**wx_key 特征码匹配 (M112 Phase 2):**
- Weixin.dll 中 key 函数特征码匹配成功
- 目标函数 RVA: **Weixin.dll + 0x55d0f0**
- 对应版本范围: >4.1.6.14
- Frida 可 hook 但时序问题未能捕获

---

## 十、联系方式 / 后续

本项目的核心瓶颈:
1. **工具限制:** pymem 只能读不能 hook, Frida 被沙箱阻挡
2. **进程重启:** 所有内存地址不固定
3. **加密:** SQLCipher key 未知（版本 4.1.10.29 不被工具支持）
4. **时序问题:** Key 函数在进程启动毫秒级内调用，外部 hook 来不及

**已取得的进展:**
- ✅ SQLCipher 参数确认: PBKDF2-HMAC-SHA512 × 256000 次迭代
- ✅ Key 函数位置: Weixin.dll + 0x55d0f0
- ✅ 特征码匹配成功（与 wx_key >4.1.6.14 配置一致）
- ✅ 全量备份成功: message_1.db 92MB
- ✅ 备份 Buf 捕获: 11593 个媒体文件
- ✅ Frida 可 attach 到部分 WeChatAppEx 进程

**待解决:**
1. wx_key.dll 调用失败 — 尝试移至纯英文路径以管理员运行
2. Frida spawn+gating hook 时序 — 需更早的注入方法
