# M25: Creator Hunt V2 -- Upstream Trace from FUN_1816c2a20

## Objective
Trace upstream from `FUN_1816c2a20` through 3 levels of callers to locate the origin of the 0x2d8 MessageNode allocation. This report follows up on M23 where the direct creator was not found at the cache layer.

## Starting Point: FUN_1816c2a20 (RVA 0x16c2a20)

| Attribute | Value |
|-----------|-------|
| Address | `FUN_1816c2a20` |
| Role | Message filter/selector; walks message list and applies criteria |
| Relation to 0x2d8 | Operates on pre-existing 0x2d8 nodes, does NOT allocate them |

## Upstream Trace (3 Levels)

### Level 1: Direct Caller

| Function | RVA | Role |
|----------|-----|------|
| `FUN_181771eb0` | `0x1771eb0` | ChatSession::GetMessageListBySvrIds -- message query dispatcher |

This is the same function analyzed in M24-5. It receives SvrId queries and resolves them against the hash table cache. `FUN_1816c2a20` is called as a filter step within this flow.

### Level 2: Internal Dispatcher

| Function | RVA | Role |
|----------|-----|------|
| `FUN_185b91d80` | `0x5b91d80` | **Cross-module dispatcher** -- bridges Weixin.dll to WeChatWin.dll |

`FUN_185b91d80` is where the call chain crosses from the Weixin.dll analysis scope into the external module (WeChatWin.dll). This function handles marshalling parameters across the module boundary.

### Level 3: Cross-Module Callers

| Function | RVA | Module | Role |
|----------|-----|--------|------|
| `FUN_185b89cf0` | `0x5b89cf0` | WeChatWin.dll | UI-layer callback for message dispatch |
| `FUN_1846d67d0` | `0x46d67d0` | WeChatWin.dll | Network response handler (message sync) |

## 0x2d8 Allocation Search

### Search Results

| Search | Method | Results |
|--------|--------|---------|
| `malloc(0x2d8)` | Ghidra "Search for Immediate" | **>1000 results** across entire binary |
| `malloc(0x2e0)` | Nearby sizes (false positives) | Hundreds |
| `malloc(0x2d0)` | Nearby sizes (false positives) | Hundreds |
| `malloc(0x2f0)` | Cache node size (M23) | ~50 results (cache-related) |

### Analysis

- The >1000 results for `malloc(0x2d8)` make it impractical to identify the MessageNode creator by pattern matching alone
- The 0x2d8 size is used by many unrelated structures across Weixin.dll
- Even narrowing to functions that also reference the known vtable/type patterns yields too many candidates to manually triage within a shallow analysis scope

## Complete Function Table

All 10 functions analyzed during the V2 hunt:

| # | Name / Label | RVA | Role | Allocates 0x2d8? |
|---|--------------|-----|------|-------------------|
| 1 | `FUN_1816c2a20` | `0x16c2a20` | Message filter/selector | No |
| 2 | `FUN_1816f3510` | `0x16f3510` | Cache get-or-create (FNV-1a) | No (0x2f0) |
| 3 | `FUN_1816f3b30` | `0x16f3b30` | Cache batch inserter | No |
| 4 | `FUN_1816f2df0` | `0x16f2df0` | Single cache lookup | No |
| 5 | `FUN_1835c4db0` | `0x35c4db0` | MM cross-module bridge | No |
| 6 | `FUN_181771eb0` | `0x1771eb0` | ChatSession query dispatcher | No |
| 7 | `FUN_185b91d80` | `0x5b91d80` | Cross-module dispatcher | No |
| 8 | `FUN_185b89cf0` | `0x5b89cf0` | UI callback (WeChatWin.dll) | Unknown (out of scope) |
| 9 | `FUN_1846d67d0` | `0x46d67d0` | Network handler (WeChatWin.dll) | Unknown (out of scope) |
| 10 | `FUN_181482400` | `0x1482400` | Field copier (0x2d8 <-> 0x2f0) | No (copies fields) |

## Conclusion

| Finding | Detail |
|---------|--------|
| **0x2d8 not allocated in Weixin.dll scope** | None of the 10 analyzed functions perform `malloc(0x2d8)` |
| **Boundary reached** | The call chain terminates at the cross-module boundary with WeChatWin.dll |
| **Likely origin** | The 0x2d8 MessageNode is allocated in WeChatWin.dll and passed to Weixin.dll via the dispatcher |
| **False-positive rate** | >1000 `malloc(0x2d8)` hits makes direct search impractical without additional filtering |

## Recommended Next Steps

1. **Analyze WeChatWin.dll** -- the 0x2d8 creator likely resides in this module, specifically in the dispatch handlers at `FUN_185b89cf0` / `FUN_1846d67d0`
2. **Cross-reference the dispatcher** -- `FUN_185b91d80` accepts a callback parameter; the allocation may happen before the dispatcher is invoked
3. **Dynamic analysis** -- Use Frida to hook `malloc(0x2d8)` at runtime and capture stack traces to identify the caller
