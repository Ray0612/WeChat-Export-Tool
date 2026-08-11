# 微信聊天记录导出项目 — 完整上下文 (给失忆 GPT 看)

> 最后更新: 2026-06-10
> 微信版本: 4.1.10.29
> GitHub 讨论: https://github.com/ggvna/wechat-export-issue

---

## 一、项目目标

导出一个 Windows 微信账号的**全部聊天记录** (文本消息、图片、文件、链接等)，导出格式为 TXT/MD，保存到本地。

**约束条件：**
- 必须在 Windows 上运行（不能模拟点击）
- 微信版本 4.x（Electron/Chromium 架构）
- 不能修改微信文件
- 不能依赖手机同步/备份

---

## 二、数据存储方式

### 2.1 加密的 SQLite 数据库

微信聊天记录存储在 `message_0.db`，这是一个 **SQLCipher 加密的 SQLite 数据库**。

- 路径: `D:\储存信息\xwechat_files\wxid_xxx\db_storage\message\message_0.db`
- 大小: 95.4 MB
- 加密: AES-256-CBC + PBKDF2-HMAC-SHA1 (64000 迭代)
- 页面大小: 4096 bytes
- 总页数: 24410

### 2.2 数据库结构 (已逆向)

数据库包含 **426 个 Msg_ 表**，每个会话一个：

```sql
CREATE TABLE Msg_<MD5(wxid)>(
  local_id           INTEGER PRIMARY KEY AUTOINCREMENT,
  server_id          INTEGER,        -- 消息服务端ID
  local_type         INTEGER,        -- 消息类型 (1=文本, 3=图片, 49=分享)
  sort_seq           INTEGER,        -- 排序序列
  real_sender_id     INTEGER,        -- 发送者 (FK → SessionTable.rowid)
  create_time        INTEGER,        -- Unix 时间戳
  status             INTEGER,
  upload_status      INTEGER,
  download_status    INTEGER,
  message_content    TEXT,           -- 消息文本内容
  compress_content   TEXT,
  ...
);
```

**映射关系:**
```
SessionTable.username (wxid_xxx / xxx@chatroom)
    ↓ MD5()
Msg_<md5_hash> 表名
    ↓
real_sender_id = SessionTable.rowid
```

### 2.3 核心困难

数据库被 SQLCipher 加密，密钥未知。密钥由微信客户端在运行时通过 `sqlite3_key_v2()` 传入，每次启动可能不同（基于登录 session token）。

加密函数在 `flue.dll` (201MB) 中: `flue.dll+0x2a9c805 = sqlite3_key_v2`

---

## 三、全部研究历史 (M1-M112)

### 第一阶段: 旧版方法 (M1-M73)
微信 3.x 时代有可用的 SQLCipher 密钥提取方法（通过扫描内存中的 `PRAGMA key` 或 hook SQLite 函数）。但这些方法对 4.x 无效。

### 第二阶段: 加密突破尝试 (M80-M83)
**目标: 找到 SQLCipher 密钥**

试过的所有方法:
| 方法 | 结果 |
|------|------|
| 用 UIN/账号/wxid 作为 password | 失败 |
| 在 WeChatAppEx 堆中搜索 32/64 字节高熵 | 失败 |
| 在注册表/配置文件中找 key | 失败 |
| 搜索 "SetDBKey" 字符串附近的内存 | 失败 |
| 扫描全部内存找 `0x` 开头的 hex string | 失败 |
| PCRE 模式搜索 (SQLCipher 的 page 1 特征) | 失败 |

### 第三阶段: 运行时分析 (M84-M93)
**目标: 在内存中找到解密后的数据**

| 方法 | 结果 |
|------|------|
| 0x2d8 C++ 消息节点捕获 | 生命周期毫秒级，来不及读 |
| Flutter/Dart UI 堆扫描 | 只有渲染副本，无元数据 |
| SQLite 解密页面缓存扫描 | 数据页用完即释放 |
| sqlite3* handle 搜索 | 在 WeChatAppEx Chromium 沙箱内，无法访问 |
| DebugActiveProcess 附加 | 杀死进程 |
| Frida Hook | Chromium 沙箱阻挡 DLL 注入 |

### 第四阶段: 结构分析和部分成功 (M94-M111)
**目标: 找到消息在内存中的缓存形式**

**M94-M97: MessageList 结构化缓存** ✅ 部分成功
- 发现堆中有 `wxid_timestamp_id` 格式的结构化条目
- 361 条记录，41 个联系人，覆盖 7 个月
- 但这是 SessionTable 的摘要，不是完整消息

**M100-M105: CoGetSessionMessageListWithPageFromDB** ✅ 结构确认
- 函数在 `weixin.dll+0x360c210`
- 签名: `(context, output, index, session_name, page_size, from_localid, config)`
- 返回值: MessagePageResult (0xA0 字节)
- MessagePageResult 是"查询控制器"，不是消息容器
- page_size = 1000 已确认
- 迭代器模式访问消息 (forward_iterator 在 +0x08)
- 首次发现时 session="filehelper"，vector 为空

**M107-M111: C++ 消息对象扫描** ⚠️ 部分验证
- 发现 21241 个 C++ 对象共享同一个 vtable (推测 `weixin.dll+0x1b4158`)
- 对象大小 0x80 字节
- +0x00: 基类 vtable
- +0x28: message_content (SSO string)
- +0x38: sender (SSO string)
- 但 99% 的对象是空的（滑动窗口缓存）
- 确认有真实消息内容: "哇呜这个我也特别认同呀"、"瑞瑞，你明天早上9点到吧"

### 第五阶段: M112 — 当前阶段 (2026-06-10)
**目标: 直接在内存中提取消息**

做了 5 次尝试:

1. **vtable 扫描** ❌ — 扫描 weixin.dll+0x1b4158 的 vtable，0 命中。因为 0x1b4158 根本不是 vtable（是函数体），交接文档记录错了。

2. **.rdata vtable 枚举** ⚠️ — 找到 109454 个候选 vtable，但无法确定哪个是消息对象。

3. **中文文本回溯** ⚠️ — 找到 34935 个中文文本，但回溯 0x200 字节找不到 vtable 指针。

4. **内存布局分析** ✅ 关键发现 — dump 文本周围内存发现：
   - 文本不存在于 C++ 对象中
   - 存在于 **WCDB 的 key-value 缓存**（类似 LevelDB/SSTable 格式）
   - 格式: 字段名 + 元数据 + 00 00 01 00 分隔符 + UTF-8 C 字符串
   - 无 vtable 指针，不是 C++ 对象

5. **裸文本提取** ✅ 成功 — 扫描 0x01a400000000-0x01a600000000 范围：
   - 提取 **3023 条不重复中文消息**
   - 2126 条干净文本
   - 227 条关联到 wxid
   - 已知发送者分布:
     - wxid_caccoealsdbj12 (自己): 98 条
     - wxid_a1n0j4x1gg8i22: 76 条
     - wxid_22e48sxjw2c222: 39 条

---

## 四、当前选择的路线

### 当前主路线: 裸文本内存提取

**理由:**
- 这是目前唯一能实际拿到消息内容的方法
- 不需要 SQLCipher key
- 只需要 pymem（不需 Frida/WinDbg）
- 微信运行时就会把解密后的消息缓存在内存中

**原理:**
WeChat 4.x 使用 WCDB (WeChat DataBase) 框架，内部有 sled-like 的 key-value 缓存层。当用户打开聊天窗口翻页时，WCDB 从 SQLCipher 加密的数据库中读取数据、解密、然后以序列化记录格式缓存在堆内存中（0x01a400000000-0x01a600000000 范围）。这些记录包含字段名称、UUID、MD5 hash 和 UTF-8 消息文本。

**当前成果:**
- 提取了 3023 条唯一消息文本
- 脚本: `scripts/m112_routeA/extract_raw_texts.py`
- 数据: `C:\Users\OK\Desktop\wx_export\raw_texts_1781028614.json`

**瓶颈:**
1. 大多数字段没有 wxid 和时间戳（文本附近 200 字节内找不到）
2. WCDB 缓存的完整记录格式未逆向
3. 需要用户手动翻聊天窗口来触发数据加载

### 待定: SQLCipher key 扫描 (路线 B)

**工具:** `scripts/m112_routeA/scan_key.py`

**理由:** 既然数据库能被解密（内存中有缓存数据），key 一定在 WeChatAppEx 的 flue.dll 上下文中。问题是 pymem 能读 WeChatAppEx 内存但找不到 key。

**计划方法:**
1. 扫描 32/64 字节高熵数据块（排除全零、重复模式）
2. 搜索 "0x" 开头的 hex key 字符串
3. 在 flue.dll+0x2a9c805 (sqlite3_key_v2) 附近找函数参数
4. 更仔细地分析 flue.dll 的 DeriveKeyPbkdf2HmacSha1 调用链

---

## 五、技术栈和工具

| 工具 | 用途 | 状态 |
|------|------|------|
| pymem | 读写进程内存 | ✅ 可用 |
| Ghidra | 逆向分析 weixin.dll (175MB) 和 flue.dll (201MB) | ✅ weixin.dll 已分析，flue.dll 部分分析 |
| Frida | Hook 函数调用 | ❌ Chromium 沙箱阻挡 |
| WinDbg | 内核调试 | ❌ 未尝试 |
| Python 3.13 | 脚本编写 | ✅ |

### 关键 DLL 信息

**weixin.dll (175MB)**
- Ghidra 基址: 0x180000000
- 运行时基址: 动态 (本例: 0x7ffa80e00000)
- SizeOfImage: 0xaf0e000

**flue.dll (201MB)**
- 位于: WeChatAppEx Chromium 沙箱内
- sqlite3_key_v2: flue.dll+0x2a9c805
- 包含: PBKDF2-HMAC-SHA1 (64000 迭代), AES-256-CBC

### 进程模型
```
explorer.exe
  └── Weixin.exe (主进程, 持有 message_0.db 句柄)
      ├── Weixin.exe (子进程, UI 渲染)
      ├── WeChatAppEx.exe (多实例, 含 flue.dll, Chromium 沙箱)
      └── ...
```

---

## 六、代码和脚本体系

### GUI 导出工具 (可直接使用)
```
wechat_v4_export_research/gui/
├── app.py           — tkinter 界面
├── data_manager.py  — 数据加载
├── config.py        — 配置管理
├── exporter.py      — TXT/MD 导出
```

用法: `python run_gui.py`

功能:
- 浏览已解析的会话列表
- 查看消息内容
- 导出 TXT/MD
- 昵称设置
- 消息统计

### M112 路线 A 脚本
```
scripts/m112_routeA/
├── extract_raw_texts.py    — ✅ 裸文本提取 (3023 条)
├── live_monitor.py         — 实时监控 (1s 轮询，需要用户翻页)
├── scan_messages_A.py      — vtable 扫描 (原始方法，当前 0 命中)
├── find_vtable.py          — .rdata vtable 枚举
├── find_by_text.py         — 文本回溯找 vtable
├── find_objects.py/2.py    — 对象搜索
├── scan_key.py             — SQLCipher key 扫描
├── debug_text.py           — 内存布局调试
└── dump_text_struct.py     — 文本结构分析
```

### 提取数据
```
C:\Users\OK\Desktop\wx_export\
├── raw_texts_1781028614.json    — 3023 条文本 (主输出)
└── live_*.json                  — 实时监控增量
```

---

## 七、完整实验目录

```
experiments/
├── m74_fresh/    — LevelDB 增量捕获
├── m84/          — Flutter 堆分析
├── m85/          — Flutter 堆分析 (续)
├── m86/          — 运行时分析
├── m87/          — 0x2d8 节点捕获
├── m88/          — DB Schema + Page 1 dump
├── m89/          — 426 Msg_ 表 + SessionTable
├── m90/          — 联系人映射 + 消息队列
├── m91/          — sqlite3 handle 搜索
├── m92/          — handle 监控 + WeChatAppEx 搜索
├── m93/          — vector 搜索
├── m94/          — 结构化缓存 + 测试消息
├── m95/          — 消息捕获封装
├── m97/          — MessageList 监控
├── m100/         — OutputStructure / MessagePageResult
├── m104/         — 分页结构确认
├── m105/         — MessagePageResult 监控
└── m112/         — 路线A: vtable扫描 + 裸文本提取 (当前)
```

---

## 八、如果你想从这里继续

### 最快能做什么

```bash
# 1. 运行实时监控器 (同时翻微信聊天窗口)
python scripts/m112_routeA/live_monitor.py

# 2. 提取所有文本
python scripts/m112_routeA/extract_raw_texts.py

# 3. 用 GUI 查看已有的解析数据
python run_gui.py
```

### 需要继续的方向

**方向 1: 改进裸文本提取 (低门槛，渐进式)**
- 提高上下文窗口大小或扫描精度，捕获更多 wxid/时间戳
- 逆向 WCDB 缓存记录格式，解析结构化数据
- 长时间运行监控器，覆盖所有重要聊天

**方向 2: SQLCipher key 提取 (高回报，高难度)**
- 在 WeChatAppEx (flue.dll) 中搜索 key
- 需要更仔细地逆向 flue.dll 的 DeriveKeyPbkdf2HmacSha1
- 可能方案: 在 sqlite3_key_v2 调用前后 dump 内存找 key

**方向 3: Frida / WinDbg (门槛最高)**
- 绕过 Chromium 沙箱注入 Frida
- 或用 WinDbg 内核模式附加
- Hook sqlite3_key_v2 直接拦截 key

### 重要的 C++ 函数偏移 (Ghidra RVA)
```
CoGetSessionMessageListWithPageFromDB: weixin.dll + 0x360c210
FUN_18365ac60 (输出处理):              weixin.dll + 0x365ac60
sqlite3_key_v2:                        flue.dll + 0x2a9c805
```

### 重要的结构体偏移
```
MessagePageResult (0xA0 bytes):
  +0x50: page_size (=1000, uint64)
  +0x58: total/count (uint64)
  +0x60: session_name (SSO string)
  +0x78: count (15)

C++ Message Object (0x80 bytes):
  +0x00: vtable  (weixin.dll 代码段指针)
  +0x28: message_content (SSO string)
  +0x38: sender (SSO string)
  +0x48: timestamp/data (SSO string)
```

---

## 九、注意事项

1. **Weixin.exe 会频繁重启** — PID 和内存地址不断变化，所有脚本必须动态获取 PID
2. **WeChatAppEx 有 Chromium 沙箱** — Frida/Shellcode 注入无法直接工作
3. **SSO 字符串格式不确定** — WCDB 使用的 SSO 格式可能是自定义的，不一定是 C++ std::string 格式
4. **vtable 偏移 0x1b4158 是错误的** — 手写交接文档时记录错误，该地址是函数体不是 vtable
5. **UTF-8 输出** — Windows 上运行为确保中文输出正常，需要 `sys.stdout.reconfigure(encoding='utf-8')`
6. **消息只在翻页时加载** — 需要用户主动打开聊天窗口翻页，触发 CoGetSessionMessageListWithPageFromDB

---

## 十、总结

```
项目状态: 进行中 — 已找到有效的数据提取路径
当前路线: 裸文本内存提取 (M112 路线 A)
可行性:   ✅ 已验证可提取 3023 条文本
覆盖率:   受限于用户翻页范围
局限性:   缺少发送者/时间戳元数据
下一步:   改进提取精度 或 走 SQLCipher key 路线 (路线 B)
```
