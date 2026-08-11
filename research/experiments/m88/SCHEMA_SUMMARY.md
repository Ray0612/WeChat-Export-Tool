# M88 — Schema Summary

## Database Info
- File: message_0.db
- Page size: 4096
- Page count: 24410 (~95.3 MB)
- Text encoding: UTF-8
- Schema cookie: 1716 (version 4)
- Encryption: SQLCipher (decrypted in memory)
- Status: ✅ Fully accessible via PID 6312 heap

## Table Structure

### Per-Session Message Tables (179 found)

Naming: `Msg_<32-char-hex>` where the hex is a hash of the session ID.

```
CREATE TABLE Msg_<hash>(
  local_id           INTEGER PRIMARY KEY AUTOINCREMENT,
  server_id          INTEGER,        -- svrid (message server ID)
  local_type         INTEGER,        -- message type (1=text, 3=image, 49=share)
  sort_seq           INTEGER,        -- sort sequence
  real_sender_id     INTEGER,        -- FK to contact table (not wxid!)
  create_time        INTEGER,        -- Unix timestamp
  status             INTEGER,        -- send/read status
  upload_status      INTEGER, 
  download_status    INTEGER,
  server_seq         INTEGER,
  origin_source      INTEGER,
  source             TEXT,
  message_content    TEXT,           -- The actual message text!
  compress_content   TEXT,           -- Compressed content (if any)
  packed_info_data   BLOB,           -- Binary metadata
  WCDB_CT_message_content INTEGER,   -- WCDB change tracking
  WCDB_CT_source     INTEGER
)
```

### Indexes (per table)
- `Msg_<hash>_SENDERID` ON `real_sender_id`
- `Msg_<hash>_SERVERID` ON `server_id`
- `Msg_<hash>_SORTSEQ` ON `sort_seq`
- `Msg_<hash>_TYPE_SEQ` ON `(local_type, sort_seq)`

### Other Tables

| Table | Purpose |
|-------|---------|
| `DeleteInfo` | Deletion tracking |
| `DeleteResInfo` | Resource deletion |
| `TimeStamp` | Timestamp tracking |

### Full-Text Search Tables
- `message_fts_v4_*` — FTS index for message search

## Field Mapping (0x2d8 ← → DB)

| 0x2d8 Offset | DB Column | Type |
|---|---|---|
| +0x010 | `local_type` | INTEGER |
| +0x148 | `server_id` | INTEGER |
| +0x018 | `real_sender_id` | INTEGER (FK) |
| +0x278 | `message_content` | TEXT |
| +0x00c/+0x158 | `local_id` | INTEGER |
| unknown | `create_time` | INTEGER |
| unknown | `sort_seq` | INTEGER |

## Session Hash Mapping

The `Msg_<hash>` table names use a 32-char hex hash.
Example: `Msg_00a2071937cf2d5b4115b92b337bb766` corresponds to the attachment directory `msg/attach/00a2071937cf2d5b4115b92b337bb766/`.

This hash is derived from the chatroom ID or partner wxid.

## Next Steps

### Short-term: Verify column data in page cache
- Find a loaded data page in memory
- Verify: create_time, local_type, message_content values match known messages

### Medium-term: Read DB through handle
- Find the sqlite3* handle in WeChatAppEx memory
- Execute SELECT queries on the handle
- Extract message data without needing all pages cached

### Long-term: Full message export
- Map session hashes to chatroom names/wxids
- Join with contact table to get real sender names
- Export per-session with TXT/MD format
