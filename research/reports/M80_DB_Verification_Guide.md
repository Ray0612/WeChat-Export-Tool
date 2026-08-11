# M80 — 聊天数据库验证指导

> 目标：确认 `db_storage/message/message_*.db` 是否存储聊天消息，定位写入数据库，为全量导出做准备。
> 背景：M1-M75 研究结论"聊天记录不在磁盘"是**错误的**——96MB 加密数据库已发现，但未验证写入。

---

## 1️⃣ 数据库文件清单

路径（适配用户实际 wxid）：

```
D:\储存信息\xwechat_files\wxid_caccoealsdbj12_e8c8\db_storage\message\
├── message_0.db     (96MB)
├── message_1.db     (?)
├── message_2.db     (?)
├── message_fts.db   (全文搜索索引)
├── message_resource.db
├── media_0.db       (媒体文件)
├── biz_message_0.db (公众号消息)
└── weclaw.db
```

**第一步：** 列出所有 message 相关数据库的大小和修改时间。

### 执行命令

```bash
ls -lh "/d/储存信息/xwechat_files/wxid_caccoealsdbj12_e8c8/db_storage/message/"
```

输出示例：

```
message_0.db   96M Jun  7 22:13
message_1.db  512K Jun  7 22:13
message_2.db  256K Jun  7 22:13
message_fts.db 64K Jun  7 22:13
...
```

---

## 2️⃣ 实时验证方法

核心思路：**发唯一消息 → 观察哪个文件变化**。

### 步骤

1. **前提**：微信 PC 已登录，能找到测试对象（可以给自己发文件传输助手）
2. **记录基线**：所有 `message_*.db` 的 `ls -lh` 时间戳和大小
3. **发送唯一测试消息**（下面三个任选）：
   - 文本：`HELLO_M80_DB_TEST_001`
   - 或英文+数字：`M80_VERIFY_20260607_001`
   - **必须每次不同**，否则无法确认写入
4. **立即检查**：`ls -lh` 看哪个文件修改时间变了、大小变了
5. **重复**：换不同会话（群聊、单聊），不同消息类型（文本、图片、文件），至少 3 轮

### 执行命令（包装成脚本）

```bash
echo "=== M80 Baseline ==="
ls -lh "/d/储存信息/xwechat_files/wxid_caccoealsdbj12_e8c8/db_storage/message/message_*.db"
date '+%Y-%m-%d %H:%M:%S'
```

发送测试消息后：

```bash
echo "=== M80 After Message ==="
ls -lh "/d/储存信息/xwechat_files/wxid_caccoealsdbj12_e8c8/db_storage/message/message_*.db"
date '+%Y-%m-%d %H:%M:%S'
```

---

## 3️⃣ 观察规律

### 需要记录的内容

| 轮次 | 测试会话 | 消息类型 | 消息内容 | 变化的 DB | 增量 |
|------|---------|---------|---------|----------|------|
| 1 | 文件传输助手 | 文本 | M80_TEST_001 | message_0.db | +4KB |
| 2 | 群聊 A | 文本 | M80_TEST_002 | ? | ? |
| 3 | 单聊 B | 表情 | (内置表情) | ? | ? |
| 4 | 单聊 C | 文件 | 1KB txt | ? | ? |

### 关键观察点

- **哪几个 db 文件变化？** 只有 message_0.db，还是 message_1/2 也变？
- **写入时机**：发送后立刻写入，还是延迟几秒批量写入？
- **增量规律**：每条消息多少字节？多次发送是否增量稳定？
- **多会话分布**：不同会话是否写入不同 message_N.db（分库策略）？

---

## 4️⃣ 输出日志格式

每次操作应生成结构化的日志文件到 `experiments/logs/M80_verify.log`：

```
=== M80 Verify ===
[2026-06-07 22:30:00] === Baseline ===
  message_0.db  100663296  (96.0MB)
  message_1.db  524288     (0.5MB)
  message_2.db  262144     (0.3MB)
[2026-06-07 22:30:05] Sent: M80_TEST_001 to 文件传输助手
[2026-06-07 22:30:10] === After ===
  message_0.db  100667392  (96.0MB)  ← +4096 bytes, time changed!
  message_1.db  524288     (0.5MB)  ← no change
  message_2.db  262144     (0.3MB)  ← no change
[2026-06-07 22:30:15] → message_0.db confirmed: single text message adds ~4KB
```

### 自动化脚本

可选：用 Python 脚本自动轮询文件变化，减少人工操作。

```python
import os, time
msg_dir = r"D:\储存信息\xwechat_files\wxid_caccoealsdbj12_e8c8\db_storage\message"

def snapshot():
    result = {}
    for f in ['message_0.db', 'message_1.db', 'message_2.db']:
        path = os.path.join(msg_dir, f)
        if os.path.exists(path):
            result[f] = (os.path.getsize(path), os.path.getmtime(path))
    return result

print("Monitoring file changes. Send a test message now!")
base = snapshot()
time.sleep(10)
current = snapshot()
for f in current:
    if current[f] != base.get(f):
        print(f"{f}: SIZE {base.get(f, (0,0))[0]} → {current[f][0]}, TIME changed!")
```

---

## 5️⃣ 后续行动

### 验证成功后

1. **定位密钥来源**
   - 搜索 Weixin.exe 进程内存中可能的密钥字符串（SetDBKey、sqlite3_key 等）
   - 分析 `config/` 目录中 `file_config_202*v2` 大文件（256KB）的结构
   - 参考 WeChat 3.x 已知方法：Hook sqlite3_key / sqlite3Codec 等 SQLCipher API

2. **分析表结构**
   - 解密后先看 `message_0.db` 的 schema：`.tables` + `PRAGMA table_info()`
   - 重点表：`message`（消息体）、`session`（会话）、`contact`（联系人）
   - 字段映射：`CreateTime`、`StrContent`、`FromUser`、`ToUser`、`Type`、`Sequence`

3. **实现全量导出**
   - 如果 message_0 是完整历史 → 直接全量 SQL 读取
   - 如果 message_0 是分片/近期 → 需要组合 message_0/1/2 + FTS + resource

4. **废弃内存捕获路径**
   - 一旦数据库解密可行，M36/M59/M73/M74 的内存扫描方法可以退役
   - GUI 数据源从 `m74_parsed.json` 切换到 SQLCipher 直连

### 验证失败的备用方案

如果 message_N.db 不变化：

1. 检查是否写入其他 `db_storage/` 下的数据库（`session.db`、`general.db`）
2. 检查是否写入 `config/` 下的文件
3. 回退到 M73/M74 的内存捕获 + LevelDB dump 方式
4. 考虑 Hook NtWriteFile 监控所有文件 I/O，确认数据真正写入位置

---

## 6️⃣ 注意事项

| 项目 | 说明 |
|------|------|
| 数据库加密 | 所有 `.db` 头部均为随机字节（熵 250+/256），**不要尝试直接 sqlite3 打开** |
| 文件完整性 | 不要复制/修改数据库文件到外部再打开，只在原地观察 |
| 微信状态 | 保持微信 PC 在线登录，部分写入可能只有接收消息时触发 |
| 测试消息 | 每次发唯一字符串，否则无法确认是新的写入还是 WAL/日志刷盘 |
| 写入延迟 | 微信可能批量写入（WAL 模式），消息发送后等待 10-30 秒再检查 |

---

## 总结

M80 是项目转折点。如果 message_N.db 确认接收写入，意味着：

> **研究方向从「内存抓取零散数据」转向「数据库解密 + 全量导出」**

96MB 的 message_0.db 如果完全解密，可以拿到完整聊天历史（数月甚至数年），远超过 M36 紧凑结构捕获的 ~25 条/页。
