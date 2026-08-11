# M57B — Weixin.exe 历史消息动态监控指导

## 方案
在手机备份/恢复聊天记录时，动态监控 Weixin.exe 内存和函数调用，定位完整历史层。

## 监控点

### Frida Hook
- Caller1 (0x01683b08) — 翻页入口
- GetPagedMessages (0x016ff6b0) — 消息加载
- FUN_1816c2a20 (0x016c2a20) — 0x2d8 遍历
- FUN_1816f3510 (0x016f3510) — 缓存分发

### 内存快照
- 备份前/后对比，找出新增大块内存（>10MB）

### ProcMon
- 过滤 Weixin.exe 的读写操作
- 观察 db_storage / cache 路径

## 预期输出
- 历史层地址和大小
- 消息结构字段偏移
- 全量导出器可直接使用的接口
