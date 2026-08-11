# 微信导出项目 Todo List

## 项目状态
> 最后更新: 2026-06-11
> 微信版本: 4.1.10.29
> 当前阶段: M112 (Key 提取 + 备份捕获)

## 已完成 ✅

### 数据库分析
- [x] DB Schema 完整解析 (426 Msg_ + SessionTable)
- [x] MD5(wxid) → Msg_<hash> 映射确认
- [x] SessionTable 查询缓存
- [x] SQLCipher 参数确认 (SHA512, 256K iter, 80 byte reserve)
- [x] V4 解密参数完全确定 (PBKDF2-HMAC-SHA512 × 256000)

### 文本提取
- [x] WCDB 缓存裸文本提取 (3023 条)
- [x] 时间戳提取 (341/395 条带时间戳)
- [x] wxid 关联 (60/261 条)
- [x] 实时监控器 (live_monitor_v3)

### 备份捕获
- [x] Buf 文件全量捕获 (11593 个媒体文件)
- [x] migration.db 会话列表 (13 个会话)
- [x] 备份 XML 消息捕获 (62 条)
- [x] 全量备份成功 (message_1.db 92MB)

### 工具集成
- [x] pywxdump 安装 (不支持 4.1.10.29)
- [x] weixin-decrypte-script (2 候选 key 验证失败)
- [x] wx_key 源码分析 (特征码匹配成功)
- [x] Echotrace 下载
- [x] Frida 17.10.1 安装

### Key 提取进展
- [x] Key 函数位置定位: **Weixin.dll + 0x55d0f0**
- [x] wx_key 特征码确认 (与 >4.1.6.14 一致)
- [x] Frida 可 hook sqlite3_key_v2 (但已调用完毕)
- [x] spawn+gating 子进程监控
- [x] CREATE_SUSPENDED 启动测试

### 项目整理
- [x] 桌面文件清理
- [x] 项目归入单一目录
- [x] 第三方工具集中管理
- [x] 全量文档更新

## 待办 ❌

### 高优先级
- [ ] wx_key.dll 纯英文路径重试 (C:\tools\wx_key\)
- [ ] 管理员权限运行 wx_key
- [ ] 或用 WeChatDataAnalysis 工具尝试提取 key

### 中优先级
- [ ] Frida spawn+gating + Weixin.dll module-loaded hook 时序优化
- [ ] ByPass Chromium 沙箱注入 (syscall 方式)
- [ ] key_info_data 逆向分析 (protobuf 结构解析)

### 低优先级
- [ ] WCDB 缓存格式完整逆向
- [ ] 全文搜索提取改进
- [ ] GUI 适配新导出格式
- [ ] Media 文件自动分类

## 已放弃 ❌

- SQLCipher key 暴力搜索 (UIN/wxid/堆扫描) — 全部失败
- 0x2d8 节点实时捕获 — 生命周期极短
- 紧凑结构 02 05 09 — v4.1.10.29 不存在
- Flutter/Dart 堆 — 只有 UI 副本
- 解密页面缓存 — 只有 Page 1
- vtable 消息对象扫描 — 偏移量记录错误
