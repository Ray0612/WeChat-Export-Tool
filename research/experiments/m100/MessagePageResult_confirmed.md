# M102 — MessagePageResult 内存验证

## 状态：✅ 内存中存在已验证

### Found 2 instances in PID 2132

```
Instance 1: 0x1392e22f680 → session="filehelper", page_size=1000
Instance 2: 0x13944f64e00 → session="filehelper", page_size=1000
```

### 确认字段布局

```
+0x00: flags (low 32 = init_status, high 32 = type?)
+0x08: forward_iterator  (函数指针，用于遍历消息列表)
+0x10: reverse_iterator  (函数指针)
+0x18: static_vtable     
+0x20: heap pointer (结果上下文?)
+0x28: QueryConfig start
+0x48: 1 (initialized flag) ✅
+0x50: 1000 (page_size) ✅
+0x58: count/total ✅
+0x60: session_name (SSO string) ✅
+0x78: count or version (15)
```

### 消息访问方式

消息通过**迭代器模式**访问。调用 `+0x08` 的函数指针进入下一个消息对象，逐个遍历结果。

### 关键发现

1. **不是 vector/数组**，而是迭代器模式
2. **session_name 内联存储**（SSO 字符串，≤15B）
3. **完全确认是数据库查询结果对象**
4. **两个实例指向同一个 session** (filehelper)
