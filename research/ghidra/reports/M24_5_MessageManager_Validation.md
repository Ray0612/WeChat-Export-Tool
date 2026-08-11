# M24-5: MessageManager Call Chain Validation

## Objective
Validate the call chain `FUN_181771eb0 -> GetMessageListBySvrIds -> MessageNode` and confirm the query semantics, data structures, and result container types involved.

## Primary Function: FUN_181771eb0 (RVA 0x1771eb0)

### Parameter Analysis

```
param_1 -> Chat Session Object
```

The object at `param_1` has been partially reverse-engineered:

| Offset | Field | Size | Description |
|--------|-------|------|-------------|
| `+0x00` | vtable/type | 8 | Virtual function table pointer |
| `+0x08` | message_link_list_head | 16 (2x8) | Doubly-linked list head for message storage |
| `+0x48` | message_manager_ptr | 8 | Pointer to the `MessageManager` sub-object |

### Field Semantics

- **`+0x08` (Message Linked List)**: This is a linked list of 0x2d8-sized MessageNode entries. The list appears to hold messages loaded for the current chat session view. Walking this list yields the raw 0x2d8 structures that get promoted into the hash table cache by `FUN_1816f3510`.
- **`+0x48` (MessageManager Pointer)**: Points to a sub-object that controls message query, pagination, and cache management for this session. The offset +0x48 suggests this is a member of the chat session class, initialized at construction time.

## Call Chain Structure

```
FUN_181771eb0
  └─> GetMessageListBySvrIds (internal method)
       ├─> FUN_1816f3510 (cache get-or-create, FNV-1a hash table)
       │    └─> 0x2f0 allocation (cache node)
       └─> linked-list traversal of 0x2d8 nodes
```

## Query Semantics Confirmation

### GetMessageListBySvrIds

The function name (as assigned in Ghidra) reflects the observed parameter pattern:

| Parameter | Type | Description |
|-----------|------|-------------|
| `param_1` | ChatSession* | The chat session context (this pointer) |
| `param_2` | uint64[] | Array of server message IDs (SvrIds) to query |
| `param_3` | uint32 | Count of IDs in the array |
| `param_4` | void** | Output pointer for result list |

**Semantics**: "Given a list of server-side message IDs, find the corresponding MessageNode objects and return them."

This is a **query-by-key** operation -- the caller provides specific server IDs (not a range or filter), and the function resolves them to cached MessageNode instances.

### Data Source

- The function first checks the **FNV-1a hash table** (via `FUN_1816f3510`) for each SvrId
- If not found in cache, it falls back to **walking the linked list** at `+0x08`
- If still not found, the message is considered unavailable (not in memory)

## Result Container

The results are packaged into a container with the following properties:

| Property | Detail |
|----------|--------|
| **Type** | FNV-1a hash table (same as FUN_1816f3510 cache) |
| **Node size** | 0x2f0 |
| **Nodes returned** | Set of matching MessageNode wrappers |
| **Empty result** | Returns null/empty container if no SvrIds match |

## Confirmation Status

| Claim | Status | Evidence |
|-------|--------|----------|
| `FUN_181771eb0 -> GetMessageListBySvrIds` | **Confirmed** | Direct call within function body |
| `param_1` is ChatSession with +0x08 list | **Confirmed** | Linked-list operations at +0x08 offset from param_1 |
| `param_1` has MessageManager at +0x48 | **Confirmed** | Pointer dereference to MessageManager methods |
| Query semantics = "by server IDs" | **Confirmed** | Parameter pattern matches SvrId array + count |
| Result container = FNV-1a hash table | **Confirmed** | FUN_1816f3510 wraps results in 0x2f0 nodes |

## Implications

1. The MessageManager layer is an **in-memory cache** -- all resolved SvrId queries go through the hash table
2. The linked list at +0x08 is a **pre-loaded working set** for the current chat session
3. The 0x2d8 MessageNode is distinct from the 0x2f0 cache node: the former is the logical message object, the latter is the cache wrapper
4. SvrId-based lookup is the primary query pattern for this layer -- consistent with WeChat's server-centric message addressing
