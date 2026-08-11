# M42-M45: Comprehensive Upstream Report

## Objective
Provide a consolidated data-flow analysis covering M42 through M45, tracing the full path from network data arrival through message caching, query, filtering, and field access. This report unifies findings across multiple analysis sessions.

## Data Flow Overview

```
Network Layer (WeChatWin.dll)
  │
  │  Data arrives as protobuf/JSON from server
  ▼
FUN_1846d67d0 (WeChatWin.dll - network response handler)
  │
  │  Parses server response, extracts message records
  ▼
FUN_185b91d80 (Weixin.dll - cross-module dispatcher)   [M27]
  │
  │  Marshals parameters across module boundary
  │  Allocates 0x2e8 callback wrapper
  ▼
FUN_181771eb0 (ChatSession::GetMessageListBySvrIds)     [M24-5]
  │
  │  Resolves SvrId array to cached messages
  ▼
FUN_1816f3510 (Cache get-or-create, FNV-1a hash table)  [M23]
  │
  │  Get-or-create: checks cache, allocates 0x2f0 on miss
  │  Copies 0x2d8 MessageNode fields into 0x2f0 cache node
  ▼
FUN_1816c2a20 (Message filter)                           [M25]
  │
  │  Applies cursor/paging constraints
  ▼
GetPagedMessages (Pagination layer)
  │
  │  Returns windowed subset to caller
  ▼
UI Layer / Client Code
```

## Cursor & Receiver Path

### PagingContext Structure

The paging system uses a `PagingContext` object that tracks the current position within the message list:

| Field | Offset | Description |
|-------|--------|-------------|
| cursor_position | PagingContext+0x00 | Current position in the message stream |
| page_size | PagingContext+0x08 | Number of messages per page |
| direction | PagingContext+0x10 | Forward/backward paging direction |
| receiver_ptr | PagingContext+0x18 | Pointer to the **receiver/cursor object** |

### Receiver Object

The receiver/cursor identified at `PagingContext+0x18` is the same object that appears at `MessageNode+0x120` (see M42 field mapping). This confirms:

- The **receiver** field in the MessageNode (+0x120) is used as a paging cursor
- Messages are filtered by receiver identity when paging through a specific chat
- The cursor is passed through from the UI layer -> dispatcher -> query -> filter chain

## Data Source Confirmation

### What the data source IS

| Attribute | Detail |
|-----------|--------|
| **Source type** | In-memory hash table cache |
| **Cache structure** | FNV-1a hash table with 0x2f0 nodes |
| **Backing store** | Linked list at ChatSession+0x08 (pre-loaded working set) |
| **Lookup mechanism** | SvrId-based key resolution via `FUN_1816f3510` |

### What the data source is NOT

| Ruled out | Reason |
|-----------|--------|
| **SQLite/DB** | No database API calls in any function in the chain |
| **IPC** | No inter-process communication primitives detected |
| **File I/O** | No file read operations in the hot path |
| **Direct network** | Network layer terminates at `FUN_1846d67d0` before entering Weixin.dll |

## FUN_181482400: Field Copy Confirmation (0x2d8 <-> 0x2f0)

`FUN_181482400` (RVA 0x1482400) is confirmed as the function responsible for **copying fields between the 0x2d8 MessageNode and the 0x2f0 cache node**.

### Confirmed Field Layout

| Offset (from MessageNode start) | Field | Size | Notes |
|----------------------------------|-------|------|-------|
| `+0x000` | vtable / type tag | 8 | Polymorphic type identifier |
| `+0x008` | message_id | 8 | Server-assigned message ID |
| `+0x010` | sequence_num | 8 | Client-side sequence number |
| `+0x018` | timestamp | 8 | Unix timestamp (seconds) |
| ... | ... | ... | (other fields between) |
| **`+0x120`** | **receiver_ptr** | **8** | **Pointer to receiver/cursor object** -- confirmed cursor linkage |
| ... | ... | ... | (other fields between) |
| `+0x260` | content_type | 4 | Content/data type identifier |
| `+0x264` | content_length | 4 | Length of content payload |
| **`+0x268`** | **content_data** | **8** | **Pointer to actual message content** (text, media refs, etc.) |

### Key Fields

- **`+0x120` (receiver_ptr)**: Confirmed as the cursor object that links M42 (MessageNode layout) to M45 (paging context). This field is populated during the field copy and is used downstream for receiver-based filtering.
- **`+0x268` (content_data)**: Points to the message payload. For text messages, this points to a UTF-8 string; for media messages, it points to a media reference structure.

## Summary of Findings (M42-M45)

| Report | Key Finding |
|--------|-------------|
| **M42** | MessageNode layout: 0x2d8 structure with receiver at +0x120 and content fields |
| **M43** | Cache layer (FUN_1816f3510): FNV-1a hash table, 0x2f0 node size, get-or-create semantics |
| **M44** | Query path: GetMessageListBySvrIds resolves SvrIds against cache; receiver/cursor flows through |
| **M45** | PagingContext: cursor + receiver fields used for windowed message access |

## Implications

1. **End-to-end flow understood**: Network -> parse -> cache -> query -> filter -> UI is fully mapped
2. **Data source is purely in-memory**: No persistence layer is involved at this level of the stack
3. **Receiver/cursor links M42 and M45**: The +0x120 field is the bridge between message objects and paging state
4. **Cache is write-through at query time**: Messages are cached when first queried, not pre-loaded
