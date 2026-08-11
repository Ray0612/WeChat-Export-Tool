# M54 — Chromium db_storage 内存格式分析

## 目标

深入 Chromium db_storage 格式的内存区域，提取全量历史消息。

## 已发现的关键内存区域

| 区域 | 内容 | 特征 |
|------|------|------|
| `db_storage\message\message` | 消息数据库 | 含完整消息二进制记录 |
| `db_storage\session\session` | 会话数据 | 含会话列表和元数据 |
| `cache\YYYY-MM\Message\` | 按月消息缓存 | 按月分片的历史消息 |
| `wxid_USER\...` | 按用户隔离 | 每个用户独立存储 |

## 分析步骤

### 1. 数据采集
- dump 整个 37MB 新内存区域到文件
- 用 pymem 逐块读取并保存

### 2. 格式分析
- 分析消息条目的二进制结构
- 寻找 seq / msgid / msgsource / receiver / content 的偏移
- 与已知的 0x2d8 / 39B 格式对比

### 3. 导出器实现
- 解析 dump 文件为消息列表
- 按会话聚类
- 输出 JSON / CSV

## 注意事项
- 共享内存由 WeChatAppEx.exe 创建，Weixin.exe 映射访问
- 数据可能加密或压缩
- M36 导出器可作为对比验证
