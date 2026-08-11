# 全量历史消息导出指导

## 背景
- M36 导出器可抓取约 200 条近期消息，95% 准确率
- 0x2d8/39B 紧凑结构是显示缓存，不包含全部历史
- 历史消息存储在 WeChatAppEx.exe 的 Chromium 内存层
- Weixin.exe 仅映射渲染输出，无法直接访问完整历史

## 方法方向

### 1. 内存全量 dump
- 冷启动后 dump WeChatAppEx.exe 全部可读内存
- 工具：ProcDump / Process Hacker / WinDbg
- 覆盖：db_storage/message, db_storage/session, cache 区

### 2. 格式分析
- 解析 Chromium db_storage / IndexedDB / LevelDB 格式
- 提取 seq, msgid, msgsource, receiver, sender, content, timestamp
- 与 M36 的 0x2d8/39B 对比验证

### 3. 动态分析（可选）
- Hook WeChatAppEx.exe 的 Chromium IndexedDB API
- 避免渲染碎片干扰

### 4. 数据聚合
- 按会话聚合，按时序排序
- 输出 JSON / CSV / Markdown

## 总结

| 方案 | 覆盖范围 | 工作量 |
|------|---------|--------|
| M36 紧凑结构导出器 | ~200 条近期 | ✅ 已完成 |
| 全量 Chromium dump | 全部历史 | 🔄 新研究 |
