# WeChat 4.1.x Message Architecture V1

> Based on findings from M1 through M11 (2026-06-04 to 2026-06-06)
> WeChat version: 4.1.9.56 / 4.1.10.29

---

## Legend

| Mark | Meaning |
|------|---------|
| ✅ **Confirmed** | Verified by >=2 independent methods (pymem, Frida, Ghidra, behavioral) |
| ⚠️ **High Confidence** | Single method verification + logical inference |
| ❌ **Falsified** | Tested and disproven |

---

## Layer 1: User Operations

```
User Input (keyboard / mouse)
    │
    ├── PageUp (Physical Key Only)
    │     - All programmatic methods (SendInput, keybd_event, Frida, pyautogui) blocked
    │     - Only physical PageUp key works
    │     - ✅ Confirmed (19 methods tested, all failed, M1)
    │
    ├── Chat Session Switch
    │     - Triggers new PagingContext allocation
    │     - Receiver wxid stored in PagingContext+0x000
    │     - ✅ Confirmed (M4, M5: cross-session parameter comparison)
    │
    └── Open Chat Window
          - Triggers GetPagedMessages initial load
          - Messages load from offline storage into memory
          - ✅ Confirmed (M8: offline restart still shows full history)
```

## Layer 2: Business Logic

```
                    ┌─────────────────────────────┐
                    │  MessageList Manager (arg0) │
                    │  0x1f46ba1c1b0 (invariant)  │
                    ├─────────────────────────────┤
                    │  Role: Session registry      │
                    │  Contains session pointers,  │
                    │  DB schema refs ("create_time│
                    │  INTEGER"), encoded session  │
                    │  keys                        │
                    ├─────────────────────────────┤
                    │  ✅ Confirmed (M7.5)         │
                    │  ❌ Does NOT store messages  │
                    └─────────────────────────────┘
                             │ arg0 (invariant)
                             ▼
┌───────────────────────────────────────────────────────┐
│                GetPagedMessages                        │
│          FUN_1816ade70 (v4.1.9.56)                     │
│          FUN_0x???????? (v4.1.10.29, TBD)              │
├───────────────────────────────────────────────────────┤
│ Signature: GlobalCtx* fn(Manager*, GlobalCtx*,         │
│                         PagingContext*, void*)         │
│                                                       │
│ arg0 = MessageList Manager (invariant)                 │
│ arg1 = GlobalContext (invariant, returned as retval)   │
│ arg2 = PagingContext (changes per call)                │
│ arg3 = arg2 + 0x20                                    │
│ retval = arg1 (NOT a message list!)                    │
│                                                       │
│ ✅ Confirmed (M2-Ghidra xref, M3.5-Frida PoC,        │
│   M6-retval=arg1, M4-parameter model)                 │
│                                                       │
│ ⚠️ The function populates internal message cache      │
│    as a side effect. Messages ARE NOT returned.        │
└───────────────────────────────────────────────────────┘
        │                                      │
        │ arg2 (per-call)                      │ side effect
        ▼                                      ▼
┌──────────────────────┐          ┌──────────────────────────┐
│   PagingContext       │          │   GlobalContext (arg1)   │
│   (per-call struct)   │          │   0x8ecb6ff4f0           │
├──────────────────────┤          ├──────────────────────────┤
│ +0x000  receiver     │          │ +0x000 → PageContext     │
│         wxid/wxid_   │          │          (per-page meta) │
│         /filehelper  │          │ +0x008 → RenderBuffer    │
│         /@chatroom   │          │          (Qt texture)    │
│ +0x028  cursor       │          │ +0x010 = +0x008          │
│         (Unix ms ts) │          ├──────────────────────────┤
│ +0x030  counter      │          │ ✅ Confirmed (M7)        │
│         (decreasing) │          │ ❌ NOT message data      │
│ +0x188  seq number   │          └──────────────────────────┘
├──────────────────────┤
│ ✅ Confirmed (M5)    │
│ ❌ NOT message data  │
└──────────────────────┘
```

## Layer 3: Cache Layer

```
┌─────────────────────────────────────────────────────────────┐
│                  Internal Message Cache                      │
│                                                              │
│  Location: Unknown (Weixin.exe heap, not in arg0/arg1/arg2)  │
│                                                              │
│  Evidence that it exists:                                    │
│  ● GetPagedMessages returns no messages (M6)                 │
│  ● But UI displays messages after call (M3.5)                │
│  ● Messages must be stored somewhere as side effect          │
│                                                              │
│  ⚠️ Inferred — not directly observed                        │
└─────────────────────────────────────────────────────────────┘
        │                              │
        │ reads from?                  │ writes to?
        ▼                              ▼
┌──────────────────────┐   ┌──────────────────────────────┐
│  Compact Structure   │   │   Page Context (+0x000)      │
│  (34B per message)   │   │   (from arg1)                │
├──────────────────────┤   ├──────────────────────────────┤
│ Prefix: 1b 02 05 09 │   │ +0x00: vtable ptr (fixed)    │
│         01 01 04     │   │ +0x0c: page message count    │
│ Order: Reversed      │   │   (3/47/49 varies per page)  │
│       (newest first) │   ├──────────────────────────────┤
│ Size: ~25 entries    │   │ ✅ Confirmed (M7)            │
│ Volatile: cleared on │   │ ❌ NOT message data          │
│   session switch     │   └──────────────────────────────┘
├──────────────────────┤
│ Fields:              │
│ +0x00  7B prefix     │   ┌──────────────────────────────┐
│ +0x07  content text  │   │   Render Buffer (+0x008)     │
│ +0x??  04 separator  │   │   (from arg1)                │
│ +0x??  sequence u16  │   ├──────────────────────────────┤
│ +0x??  session_tag   │   │ Qt texture/font rendering    │
│ +0x??  heap ptr      │   │ Contains text glyph data     │
│ +0x??  user_id (?)   │   │ e.g., "111" text rendering   │
│ +0x??  81 be tail    │   │ All zeros if no re-render    │
│                      │   ├──────────────────────────────┤
│ ✅ Confirmed (M1)    │   │ ✅ Confirmed (M7 deep dive)  │
│ ⚠️ Volatile cache    │   │ ❌ NOT message data          │
└──────────────────────┘   └──────────────────────────────┘

ProtoBuf Fragments (in heap):
  - Found in Weixin.exe heap (M1)
  - Contains full message fields: receiver, content, timestamp, msgsource
  - ✅ Confirmed (M1, 20s interval experiment verified timestamp)
  - ⚠️ May be residual from message processing, not actively updated

Record Area (key-value in heap):
  - Key 0x73: wxid  (✅ Confirmed)
  - Key 0x76: @chatroom (✅ Confirmed)
  - Key 0x77: chatroom name UTF-8 (✅ Confirmed)
```

## Layer 4: Storage Layer

```
┌──────────────────────────────────────────────────┐
│           Offline History Storage                 │
│                                                   │
│  Existence: ✅ Confirmed                          │
│    ● GetPagedMessages hits offline (M3.5, M8)     │
│    ● 143 pages reached across 319 days (M8)      │
│    ● Counter=1 reached (all history loaded)       │
│                                                   │
│  Location: ❌ Unknown                             │
│    ● 35,063 files searched → 0 matches (M1)       │
│    ● File API hooks show NO reads during paging   │
│      (NtCreateFile, NtReadFile, CreateFileW,      │
│       ReadFile, MapViewOfFile; M9)                │
│    ● Not SQLite/LevelDB/MMKV (M1, M2)             │
│                                                   │
│  Loading: ⚠️ At WeChat startup or first           │
│    chat open, not on-demand during paging         │
│                                                   │
│  Format: ❌ Unknown                               │
│    Custom binary format (likely)                  │
│    Possibly memory-mapped at startup              │
└──────────────────────────────────────────────────┘
```

## Layer 5: UI Layer

```
┌──────────────────────────────────────────────┐
│  Note: UI layer was NOT directly studied.    │
│  The following is inferred from DLL strings  │
│  and Qt architecture.                        │
└──────────────────────────────────────────────┘

Weixin.dll string evidence (Business Object Map V1):
  - mmui::ContactsManagerHBoxlayoutClickArea
  - mmui::ChatStickyFoldButton
  - mmui::UnreadBarView
  - mmui::ContactHeadView
  - CoPrepareShowMessage
  - GetAddSendMessageToDb

✅ Confirmed: DLL contains Qt 5.15.14 UI classes (Business Object Map)

Likely architecture (Qt + custom Chromium WebView):
  RecyclerList (chat message container)
    └── ChatView (scrollable viewport)
          └── ChatTextViewHost (text bubble renderer)
                └── Canvas / web rendering
```

---

## Complete Data Flow

```
Physical PageUp
    │
    ▼
GetPagedMessages (FUN_1816ade70)
    │
    ├── arg0 = MessageList Manager (session registry)
    ├── arg1 = GlobalContext → +0x000=PageCtx, +0x008=RenderBuf
    ├── arg2 = PagingContext {receiver, cursor, counter}
    ├── arg3 = arg2 + 0x20
    └── retval = arg1 (not message data)
    │
    ▼
[Side Effect] Reads offline storage → populates Internal Message Cache
    │
    ├── Compact Structure (34B, ~25 entries, volatile)
    ├── ProtoBuf fragments (residual)
    └── Record area (key-value mapping)
    │
    ▼
UI reads from cache → renders via Qt → displays in Chromium WebView
```

## Confidence Summary

| Component | Status | Key Evidence |
|-----------|--------|-------------|
| DB/SQLite storage | ❌ Falsified | 35k files 0 match, ProcMon 0 .db access |
| Auto-scrolling | ❌ Falsified | 19 methods all blocked by Chromium |
| Messages in disk files | ❌ Falsified | Unique string TEST_RAY search 0 matches |
| Messages in Weixin.exe memory | ✅ Confirmed | pymem 57 matches, Frida verified |
| GetPagedMessages = paging entry | ✅ Confirmed | Ghidra xref (9 refs) + Frida PoC (143 hits) |
| PagingContext structure | ✅ Confirmed | Frida dump + cross-session comparison |
| retval = arg1 (no message return) | ✅ Confirmed | 32 calls, all retval == arg1 |
| arg1 +0x000/+0x008 pointer change | ✅ Confirmed | 30 calls, 3 segment diff each |
| Compact structure (34B) | ✅ Confirmed | Prefix scan, sequence validation |
| ProtoBuf message fields | ✅ Confirmed | Timestamp experiment (20s precision) |
| Offline history exists | ✅ Confirmed | 143 pages offline, counter=1 boundary |
| Offline storage location | ❌ Unknown | 35k files 0 match, 0 file API hits |
| GetPagedMessages internal logic | ❌ Unknown | Function moved in v4.1.10.29 |
| Internal message cache structure | ❌ Unknown | Not in arg0/arg1/arg2 |
