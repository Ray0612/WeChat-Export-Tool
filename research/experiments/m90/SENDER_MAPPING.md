# M90 — real_sender_id 映射分析

## 确认的映射链

```
Msg_<hash>.real_sender_id  (INTEGER)
    = SessionTable.rowid   (SQLite 隐式 rowid)
    ↓
SessionTable.username       (TEXT PK) = wxid / chatroom ID
    ↓
SessionTable.last_msg_sender
    ↓
contact_fts_v5              (全文搜索, rowid = SessionTable.rowid)
```

## 证据

| 来源 | 内容 | 意义 |
|------|------|------|
| SessionTable schema | `username TEXT PRIMARY KEY` | wxid/chatroom 是文本主键 |
| SQL 查询 (内存) | `SELECT ... FROM SessionTable WHERE username == 'filehelper' ORDER BY rowid` | SessionTable 通过 rowid 排序 |
| SQL 查询 (内存) | `SELECT T.'local_type' FROM 'main'.'contact_fts_v5' T WHERE T.'rowid'=?` | contact_fts_v5 用 rowid 关联 |
| Msg_ 表结构 | `real_sender_id INTEGER` + `Msg_xxx_SENDERID` 索引 | 通过整数 ID 查找发送者 |

## 映射方法

### 完整映射需要查询数据库
```sql
SELECT s.rowid, s.username, c.content 
FROM SessionTable s 
LEFT JOIN contact_fts_v5 c ON c.rowid = s.rowid
```

### 已知的映射关系
```
MD5(username) → Msg_<hash>  (表名)
SessionTable.rowid → real_sender_id
SessionTable.username → wxid / chatroom ID
```

## 待解决

contact_fts_v5 和 user_info 表在 contact.db 中，需要访问该数据库。如果 contact.db 也有解密页面在内存中，可以类似方法读取。

## 输出文件

- `sender_mapping.json` — 已知的 wxid 和昵称映射（来自 config + 备份数据）
