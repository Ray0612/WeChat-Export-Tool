# M18 — Reverse Pointer Recovery V2

> 实验时间：2026-06-07
> 方法：pymem 反向指针扫描
> 目标：RAY_TEST_AAA/BBB/CCC（重新发送到文件传输助手）

---

## 核心发现

### 0x2d8 消息结构体关键偏移

```
偏移      大小    内容                 示例
+0x000    8      Manager/所有者指针    → 0x21d01bac520
+0x008-   var    (多种业务字段)         ...
+0x120    12    接收者名称（内联）      "filehelper\0\0\0"
+0x260    8      对象引用              → 0x21d00000001
+0x268    8      内容字符串指针         → "RAY_TEST_BBB_20260607"
+0x2d8    —      END
```

### 验证

| 消息 | 内容地址 | 0x2d8 结构体地址 | 内容偏移 |
|------|---------|-----------------|---------|
| BBB (文件助手) | `0x21d01bacd00` | `0x21d02062608` | **+0x268** |
| BBB (其他 ref) | `0x21d01bacd00` | `0x21d01c32760` | **+0x288** |
| BBB (其他 ref) | `0x21d01bacd00` | `0x21d01c32a38` | **+0x288** |

### 完整指针链

```
Caller1 (0x01683b08)  ← 翻页入口
  ↓
GetPagedMessages (0x016ff6b0)
  ↓
FUN_1816c2a20 (0x016c2a20)  ← 步长 0x2d8 遍历
  ↓
0x2d8 Message Struct
  ├── +0x000: owner/manager ptr
  ├── +0x120: receiver name ("wxid_xxx" / "filehelper")
  ├── +0x260: internal object ref
  └── +0x268: → "message content" (UTF-8字符串指针)
```

## 对导出工具的意义

基于此结构，可以直接从内存中提取消息：

1. 在 Weixin.exe 堆中搜索 0x2d8 对齐的结构
2. 检查 +0x120 是否有有效 wxid/filehelper
3. 从 +0x268 读取内容字符串
4. 配合 PagingContext 的 +0x028 获取时间戳

## 待确认

| 字段 | 偏移 | 状态 |
|------|------|------|
| 发送者 wxid | ? | ⏳ 未在本次结构中定位 |
| 时间戳 | ? | ⏳ 需配合 PagingContext |
| 消息类型 | ? | ⏳ 未定位 |
