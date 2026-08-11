# M23: MessageNode Creator Hunt -- FUN_1816f3510 Analysis

## Objective
Locate the code path responsible for creating the 0x2d8-sized MessageNode structure identified in M22. The primary target was `FUN_1816f3510`, suspected to be the creator based on cross-reference analysis from earlier session work.

## Key Function: FUN_1816f3510 (Cache Manager -- Get-or-Create)

| Attribute | Value |
|-----------|-------|
| Address | `FUN_1816f3510` |
| RVA | `0x16f3510` |
| Allocation size | **0x2f0** (not 0x2d8) |
| Hash algorithm | FNV-1a (64-bit) |
| Role | **Dual-role**: both insert and lookup in a hash-table-backed cache |

### Functional Analysis

`FUN_1816f3510` implements a **get-or-create cache manager**:

1. **Hash table storage**: Uses a FNV-1a 64-bit hash to index into a bucket array
2. **Allocation**: `malloc(0x2f0)` -- this is the cache node size, which is 0x18 bytes **larger** than the MessageNode (0x2d8)
3. **The extra 0x18 bytes** are likely hash-table metadata: next-pointer (0x8), hash-key (0x8), and possibly flags/status (0x8)
4. **Lookup first**: Before allocating, the function walks the hash chain to check if the requested key already exists
5. **Create on miss**: Only allocates a new 0x2f0 node if no existing entry matches

### Relationship to 0x2d8 MessageNode

- `FUN_1816f3510` does **not** directly allocate 0x2d8 -- it allocates 0x2f0
- The 0x2d8 MessageNode is embedded within the 0x2f0 cache node (at offset 0x18, after the metadata header)
- The actual 0x2d8 data source is the caller's **linked-list traversal**: callers iterate a linked list of 0x2d8 nodes, and `FUN_1816f3510` copies/promotes entries into the hash table

## Callers of FUN_1816f3510

| Function | Address | Role |
|----------|---------|------|
| `FUN_1816f3b30` | `0x16f3b30` | Message list batch inserter; iterates caller's linked list, calls get-or-create for each |
| `FUN_1816f2df0` | `0x16f2df0` | Single message lookup/insert wrapper; thin shim around the cache |
| `FUN_1835c4db0` | `0x35c4db0` | Cross-module (MM) bridge; adapts MM-layer message handles for Weixin.dll cache |

## Findings & Conclusion

| Finding | Detail |
|---------|--------|
| **0x2d8 is NOT allocated here** | `FUN_1816f3510` allocates 0x2f0, not 0x2d8 |
| **0x2d8 comes from caller** | The 0x2d8-sized block is a pre-existing structure passed in via the caller's linked list |
| **Cache is secondary storage** | The hash table at `FUN_1816f3510` is a **cache layer**, not the primary allocation site for MessageNodes |
| **FNV-1a confirmed** | Hash function uses FNV-1a 64-bit constants (0xCBF29CE484222325 prime, 0x100000001B3 multiplier) |
| **0x2f0 layout** | First 0x18 bytes: metadata (next, hash, flags); remaining 0x2d8 bytes: MessageNode payload |

## Next Steps

- Trace upstream to find where the 0x2d8 linked-list nodes are initially allocated (likely in `FUN_181771eb0` or its callers)
- Verify the 0x2f0 node layout by examining field accesses in the cache bucket operations
- Search for `malloc(0x2d8)` calls across the entire Weixin.dll binary (not just shallow analysis)
