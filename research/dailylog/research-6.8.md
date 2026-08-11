# 研究日志 2026-06-08（第 5 天）

> 核心主题：从密钥搜索全面转向运行时数据库读取
> 里程碑：M80 → M88

---

## 上午/下午：M80-M87 回顾与收尾

### M80 — 数据库验证
- 确认 `message_0.db` 在发消息后 size 增加 +4KB
- 确认 WAL / FTS / material 文件同步变化
- 结论：message_0.db 是活跃聊天库 ✅

### M81 — SQLCipher 密钥尝试（全部失败）
- UIN 推导 ❌
- wxid 推导 ❌
- config 文件 XOR 0x45 ❌
- WeChatAppEx 堆内存高熵 32B 扫描 ❌（4238 候选，全部假阳性）
- 注册表搜索 ❌
- 命令行参数 ❌
- material 文件 / backup.attr 分析 ❌
- **结论：密钥未知，放弃此路线**

### M84-M85 — 运行时消息定位
- 测试消息 `RAY_RUNTIME_TEST_20260608_001` 在 PID 6312 内存中找到 43 处
- 发现 66 个 chatroom ID 和 32 个 wxid 的会话列表缓存
- 结论：消息在内存中，但大多在 Flutter UI 层

### M86 — DB 写入追踪
- WAL 变化可实时监测
- 消息对象生命周期极短（毫秒级）
- 0x2d8 数组存在但无法实时捕获

### M87 — 0x2d8 结构 + Ghidra 分析
- Ghidra 确认字段偏移：
  - `+0x010` = type
  - `+0x018` = sender wxid (SSO 字符串)
  - `+0x148` = svrid
  - `+0x278` = content pointer
- 0x2d8 节点生命周期极短，pymem 来不及捕获
- 所有候选节点实为 Flutter/Dart 对象

---

## 晚上：M88 — 决定性突破

### 发现解密页面
在 Weixin.exe PID 6312 堆内存中搜索到 **"SQLite format 3" 字符串 49 处**，证明 `message_0.db` 已在内存中完全解密！

### 解析 Page 1
- Page size = 4096 ✅
- Page count = 24410（= 95.3MB = message_0.db 大小）✅
- Text encoding = UTF-8 ✅
- Schema cookie = 1716
- **Page type = INTERIOR B-tree（0x05），118 条 sqlite_master 记录**

### 获取完整表结构
从进程内存中提取到 912 个 CREATE TABLE 语句，确认：

```sql
CREATE TABLE Msg_<32-char-hex>(
  local_id           INTEGER PRIMARY KEY AUTOINCREMENT,
  server_id          INTEGER,        -- svrid
  local_type         INTEGER,        -- 消息类型
  sort_seq           INTEGER,        -- 排序键
  real_sender_id     INTEGER,        -- 发送者 (FK)
  create_time        INTEGER,        -- 时间戳
  status             INTEGER,
  upload_status      INTEGER,
  download_status    INTEGER,
  server_seq         INTEGER,
  origin_source      INTEGER,
  source             TEXT,
  message_content    TEXT,            -- 消息内容！
  compress_content   TEXT,
  packed_info_data   BLOB,
  WCDB_CT_message_content INTEGER,
  WCDB_CT_source     INTEGER
)
```

### 字段映射（0x2d8 → DB）

| 0x2d8 偏移 | DB 列 | 已完成 |
|------------|-------|--------|
| +0x010 | local_type | ✅ |
| +0x148 | server_id | ✅ |
| +0x018 | real_sender_id | ✅（FK） |
| +0x278 | message_content | ✅ |
| 未定位 | create_time | ✅ |
| 未定位 | sort_seq | ✅ |

### 会话 Hash 映射
表名 `Msg_00a2071937cf2d5b4115b92b337bb766` 中的 hash 与附件目录 `msg/attach/00a2071937cf2d5b4115b92b337bb766/` 一致，确认 hash = session ID。

### 已保存文件
- `experiments/m88/page1.bin` — 原始 Page 1
- `experiments/m88/schema_output.json` — 完整 schema
- `experiments/m88/sample_msg_table.txt` — 示例 Msg_ 表结构
- `experiments/m88/all_tables.sql` — 所有 179 个会话表的 CREATE TABLE
- `experiments/m88/SCHEMA_SUMMARY.md` — 结构汇总

---

## 当前瓶颈
叶子页不在 SQLite 页面缓存中，需要找到 sqlite3 句柄才能直接执行查询。

## 下一步方向
1. 在 WeChatAppEx 中定位 sqlite3* handle → 直接 SELECT 查询
2. 或触发 WeChat 加载页面 → 从缓存抓取
3. 用 DB schema 实现全量导出

## 文件清理
- 桌面 40+ 个临时脚本已删除
- 项目脚本保留在 `scripts/` 和 `gui/` 目录
