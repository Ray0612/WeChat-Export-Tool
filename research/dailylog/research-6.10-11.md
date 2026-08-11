# M112 — 路线 A/B 并行: 文本提取 + 备份捕获 + Key 提取

> 日期: 2026-06-10 ~ 2026-06-11

## 核心进展

### 路线 A: 文本提取
- WCDB 缓存裸文本提取成功 (3023 条)
- 改进 V2/V3 提取器，加入时间戳和 wxid 关联
- 确定文本存在于 WCDB key-value 缓存中（非 C++ 对象）
- 实时监控器 v3 (单会话模式) 开发完成

### 路线 B: 备份捕获
- 全量手机→电脑备份成功
- Buf 文件捕获器开发完成 → 11593 个文件
- 数据库全量写入: message_1.db 92MB
- 发现 migration.db (会话列表 + 时间戳)
- **结论: Buf 文件中只有媒体附件，文本在加密数据库中**

### Key 提取 (核心瓶颈)
- wx_key 源码分析 → 特征码匹配原理理解
- **Weixin.dll + 0x55d0f0 确认** (key 函数位置)
- wx_key.dll 调用失败 (权限/路径)
- Frida 多种注入方式测试:
  - Attach 到运行中进程 ✅ (但 key 已调用)
  - spawn+gating ✅ (子进程可 hook，主进程未捕获)
  - CREATE_SUSPENDED ⚠️ (Weixin.dll 加载时序问题)
  - Child-gating ⚠️ (部分成功)
- **确认 4.1.10.29 不被任何现有工具支持**

### 项目整理
- 桌面文件全部清理
- 项目归入单一目录 (816 文件)
- 第三方工具集中管理 (echotrace, wx_key, weixin-decrypte-script)
- 全量文档更新
