# M104 — MessagePageResult 分页结构最终确认

## 结构布局 (0xA0 bytes)

```
+0x00: vtable/function pointers (0x00-0x17)
  +0x08: forward_iterator (FUN_183659cb0)
  +0x10: reverse_iterator (FUN_18365a910)

+0x18-0x27: QueryConfig section
  +0x18: sort_order (uint32, from config)
  +0x20: orientation (uint32, from config) 
  +0x28: NULL padding?

+0x28-0x9F: QueryParams (写入于 FUN_18365aa50)
  +0x28: reserved/padding (QWORD*2)
  +0x38: result array begin (ptr, from vector)
  +0x40: result array end (ptr)  
  +0x48: result array capacity (ptr)
  +0x50: page_size (uint64 = 1000) ✅
  +0x58: total/count (uint64 = 1335/1338) ✅
  +0x60: session_name (SSO string: "filehelper") ✅
  +0x70: capacity/count (15)
  +0x78-0x88: zeros
  +0x90-0x98: (two ptrs, non-message data)
```

## 分页参数

- **page_size = 1000**: 每页最多加载1000条
- **from_localid = sequential**: 翻页传入起始local_id
- **total ~1335**: 该会话总消息数（近似）
- **15**: 当前加载消息数（刚打开的会话只加载了15条）

## 翻页模型

```sql
-- 微信内部的查询逻辑 (推测)
SELECT * FROM Msg_<md5>
WHERE local_id < from_localid
ORDER BY local_id DESC
LIMIT page_size
```

## 迭代器模式

MessagePageResult 不直接存储消息列表。
消息通过 **+0x08 函数指针**（前向迭代器）逐个访问。
每调用一次返回一个 Message 对象。

## 确认状态

| 项目 | 状态 |
|------|------|
| MessagePageResult 存在于内存 | ✅ 2个实例 |
| page_size 确认 | ✅ = 1000 |
| session_name 确认 | ✅ = "filehelper" |
| total/count 确认 | ✅ ~1335 |
| from_localid 参数 | ✅ |
| Message 对象 | ❌ 需要 Hook 迭代器 |
