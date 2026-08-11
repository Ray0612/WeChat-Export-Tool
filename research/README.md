# WeChat 4.1.x 聊天消息逆向工程研究

> 微信 4.1.x (Windows) 聊天消息存储机制逆向分析 —— 从内存扫描到数据库解密

---

## 研究概述

历时近 2 个月，超过 **100+ 轮实验**，完整还原了微信 Windows 版的消息生命周期：

| 阶段 | 覆盖范围 | 状态 |
|------|---------|------|
| 存储定位 | 消息不在磁盘，在 Weixin.exe 堆内存 | ✅ 完成 |
| 函数发现 | GetPagedMessages、翻页入口定位 | ✅ 完成 |
| 消息结构 | 0x2d8 MessageNode 字段布局 (+0x120 receiver, +0x268 content) | ✅ 完成 |
| 运行时捕获 | FUN_1816c2a20 循环体 Hook，90 条/次 | ✅ 完成 |
| 紧凑结构发现 | 39B 格式，导出 241 条，95% 准确率 | ✅ 完成 |
| 上游链路 | GetMessageListBySvrIds → Creator → 网络层 | ✅ 完成 |
| Creator 定位 | **FUN_181bc3b00** (DLL +0x01bc3b00) | ✅ 完成 |
| Ghidra 分析 | 50 轮逆向分析，完整 Call Tree | ✅ 完成 |
| 数据库解密 | MSG 表、会话表结构还原 | ✅ 完成 |

---

## 目录结构

```
research/
├── ghidra/                  Ghidra 逆向分析
│   ├── tasks/               分析任务指令
│   └── reports/             分析报告
│
├── reports/                 33 份里程碑报告
├── experiments/             实验数据与输出 (m1 ~ m112)
├── scripts/                 实验脚本 (Python / JS)
├── dailylog/                每日研究日志
├── design/                  导出器架构设计
├── docs/                    技术文档
├── references/              参考文档与策略
├── tools/                   解密/分析工具集
└── weixin-decrypte-script/  微信解密脚本
```

---

## 关键发现

### 消息架构

```
网络层 (WeChatWin.dll)
  │ 服务器响应 → 创建 0x2d8 MessageNode 数组
  │
  ├── FUN_185b91d80 (跨模块调度器)
  │   └── FUN_1835c4db0 (分发器)
  │
  ├── FUN_181bc3b00 ★ 0x2d8 Creator (alloc ×6)
  │   └── FUN_183c0fd10 (初始化 vtable + 字段)
  │
  ├── FUN_1816f3b30 (GetMessageListBySvrIds)
  │   ├── FUN_1816c2a20 (0x2d8 步长过滤)
  │   └── FUN_1816f3510 (0x2f0 缓存, FNV-1a)
  │
  └── GetPagedMessages (FUN_1816ff6b0, 翻页入口)
```

### 0x2d8 MessageNode 字段布局

| 偏移 | 字段 | 说明 |
|------|------|------|
| +0x000 | vtable | 虚表指针 |
| +0x120 | **receiver** | 聊天对象 ID (std::string) |
| +0x268 | **content_ptr** | 消息内容指针 |
| +0x288 | content_ptr2 | 备用内容指针 |

### 关键函数地址 (v4.1.10.29)

| 函数 | DLL 偏移 | 角色 |
|------|---------|------|
| **FUN_181bc3b00** | +0x01bc3b00 | **0x2d8 Creator (消息节点工厂)** |
| FUN_1816ff6b0 | +0x016ff6b0 | GetPagedMessages |
| FUN_1816c2a20 | +0x016c2a20 | 0x2d8 消息过滤/遍历 |
| FUN_1816f3b30 | +0x016f3b30 | GetMessageListBySvrIds |
| FUN_1816f3510 | +0x016f3510 | 0x2f0 缓存 (FNV-1a) |
| FUN_181482400 | +0x01482400 | 0x2d8→0x2f0 字段拷贝 |
| FUN_181771eb0 | +0x01771eb0 | 消息管理事件入口 |

### 关键常量

| 值 | 含义 |
|-----|-------|
| **0x2d8** (728) | MessageNode 结构体大小 |
| **0x2f0** (752) | 缓存节点大小 |
| **0x2e8** (744) | 回调包装节点大小 |
| **FNV-1a** | 哈希表算法 |

---

## 实验索引

### 早期实验 (M1-M30)

| 编号 | 脚本 | 报告 | 内容 |
|------|------|------|------|
| M1-M5 | — | — | 存储定位：消息不在磁盘 |
| M6 | [m6_retval_analysis.py](research/scripts/m6_retval_analysis.py) | — | 返回值分析 |
| M7 | [m7_deep_dive.py](research/scripts/m7_deep_dive.py) | — | 深度分析 |
| M8 | [m8_boundary.py](research/scripts/m8_boundary.py) | [离线翻页边界测试](research/reports/offline_history_boundary_test.md) | 离线翻页边界测试 |
| M9 | [m9_file_trace.py](research/scripts/m9_file_trace.py) | — | 文件追踪 |
| M10 | [m10_initial_load.py](research/scripts/m10_initial_load.py) | — | 初始加载 |
| M11 | [m11_find_func.py](research/scripts/m11_find_func.py) | — | 函数定位 |
| M12 | [m12_b_line.py](research/scripts/m12_b_line.py) | — | 基线测试 |
| M13 | [m13_caller1_analysis.py](research/scripts/m13_caller1_analysis.py) | [Caller1 分析](research/reports/caller1_analysis.md) | Caller1 分析 |
| M14 | [m14_delta.py](research/scripts/m14_delta.py) | [PagingContext 差异](research/reports/pagingcontext_delta_report.md) | PagingContext 差异 |
| M15 | [任务](research/ghidra/tasks/m15_ghidra_calltree.md) | [Call Tree 报告](research/ghidra/reports/GetPagedMessages_CallTree_Analysis.md) | GetPagedMessages Call Tree |
| M16 | [m16_struct.py](research/scripts/m16_struct.py) | [消息结构报告](research/reports/message_struct_v1.md) | 消息结构体分析 |
| M17 | [m17_marker_test.py](research/scripts/m17_marker_test.py) | [Marker 测试报告](research/reports/m17_marker_test_report.md) | Marker 测试 |
| M18 | [m18_pointer_chain.py](research/scripts/m18_pointer_chain.py) | [指针链报告](research/reports/m18_pointer_chain_report.md) | 指针链分析 |
| M19 | — | [紧凑导出器报告](research/reports/m19A_compact_exporter_report.md) | 紧凑导出器 |
| M21 | [m21_runtime_exporter.py](research/scripts/m21_runtime_exporter.py) | — | 运行时导出 |
| M22 | [m22b_c2b30_params.py](research/scripts/m22b_c2b30_params.py) | — | 参数分析 |
| M23 | [m23_array_check.py](research/scripts/m23_array_check.py) | [报告](research/reports/M23_MessageNode_Creator_Hunt.md) · [任务](research/ghidra/tasks/m23_ghidra_creator_hunt.md) | 0x2f0 缓存层 |
| M24 | — | [报告](research/reports/M24_5_MessageManager_Validation.md) · [任务](research/ghidra/tasks/m24_ghidra_upstream.md) | 消息管理链路 |
| M25 | — | [报告](research/reports/M25_Creator_Hunt_V2_Report.md) · [任务](research/ghidra/tasks/m25_creator_hunt_v2.md) | Creator 上游追踪 |
| M27 | — | [报告](research/reports/M27_Creator_Upstream.md) · [任务](research/ghidra/tasks/m27_ghidra_creator_upstream.md) | 跨模块分析 |
| M28 | — | — | [容器分析](research/ghidra/tasks/m28_task.md) |

### 导出器开发 (M30-M66)

| 编号 | 脚本 | 报告/任务 | 内容 |
|------|------|----------|------|
| M30 | [m30_field_recovery.py](research/scripts/m30_field_recovery.py) | — | 字段恢复 |
| M31 | [m31_loop_hook.py](research/scripts/m31_loop_hook.py) | — | 循环 Hook |
| M32 | [m32_exporter_v01.py](research/scripts/m32_exporter_v01.py) | — | 导出器 V0.1 |
| M33 | [m33_text_materialization.py](research/scripts/m33_text_materialization.py) | — | 文本物化 |
| M34 | [m34_cache_investigation.py](research/scripts/m34_cache_investigation.py) | — | 缓存调查 |
| M36 | [m36_compact_exporter.py](research/scripts/m36_compact_exporter.py) | — | **紧凑导出器** |
| M42 | — | [报告](research/reports/M42_M45_Upstream_Report.md) · [任务](research/ghidra/tasks/m42_ghidra_upstream_source.md) | 全链路分析 |
| M44 | — | [任务](research/ghidra/tasks/m44_ghidra_cache_producer.md) | 缓存 Producer |
| M45 | — | [任务](research/ghidra/tasks/m45_ghidra_0x2d8_creator.md) | 0x2d8 Creator 搜索 |
| M46 | — | [报告](research/reports/M46_M48_Creator_Final.md) · [任务](research/ghidra/tasks/m46_ghidra_allocator.md) | **Creator 定位** |
| M49 | [m49_verify_creator.py](research/scripts/m49_verify_creator.py) | — | Creator 验证 |
| M50 | — | [报告](research/reports/M50_HistoryLayer_Report.txt) · [任务](research/ghidra/tasks/m50_ghidra_history_layer.md) | 历史层搜索 |
| M51 | [m51_hook_f3b30.py](research/scripts/m51_hook_f3b30.py) | — | Hook f3b30 |
| M52 | [m52_hook_svrids.py](research/scripts/m52_hook_svrids.py) | — | Hook SvrIds |
| M53 | [m53_cold_start_monitor.py](research/scripts/m53_cold_start_monitor.py) | — | 冷启动监控 |
| M57 | [m57_monitor.py](research/scripts/m57_monitor.py) | — | 实时监控 |
| M59 | [m59_leveldb_parser.py](research/scripts/m59_leveldb_parser.py) | — | LevelDB 解析 |
| M61 | [m61_final_export.py](research/scripts/m61_final_export.py) | — | 最终导出器 |
| M64 | [m64_fast_capture.py](research/scripts/m64_fast_capture.py) | — | 快速捕获 |
| M65 | [m65_final_chat.py](research/scripts/m65_final_chat.py) | — | 聊天重构 |
| M66 | [m66_chat_reconstruction.py](research/scripts/m66_chat_reconstruction.py) | [项目总结](research/reports/final_project_report.md) | **最终重构** |

### 数据库解密阶段 (M73-M112)

| 编号 | 脚本 | 实验数据 | 内容 |
|------|------|---------|------|
| M73 | [m73_capture_verify.py](research/scripts/m73_capture_verify.py) | — | 捕获验证 |
| M74 | [m74_fresh_capture.py](research/scripts/m74_fresh_capture.py) | [数据](research/experiments/m74_fresh/) | 新鲜捕获 |
| M75 | [m75_arg0.py](research/scripts/m75_arg0.py) | — | 参数分析 |
| M80 | [M80 验证指南](research/reports/M80_DB_Verification_Guide.md) | — | 数据库验证 |
| M81 | [m81_check_appex.py](research/scripts/m81_check_appex.py) | — | AppEx 检查 |
| M84-M87 | — | [m84](research/experiments/m84/) · [m85](research/experiments/m85/) · [m86](research/experiments/m86/) · [m87](research/experiments/m87/) | 堆/节点分析 |
| M88 | — | [数据](research/experiments/m88/) | Schema 分析 |
| M89 | [m89_analyze_schema.py](research/experiments/m89_analyze_schema.py) | [数据](research/experiments/m89/) | 表结构分析 |
| M90 | [m90_watch.py](research/scripts/m90_watch.py) | [数据](research/experiments/m90/) | Sender 映射 |
| M91 | [m91_capture.py](research/scripts/m91_capture.py) | [数据](research/experiments/m91/) | 紧凑捕获 |
| M92 | [m92_handle_monitor.py](research/scripts/m92_handle_monitor.py) | [数据](research/experiments/m92/) | Handle 监控 |
| M93 | [m93_vector_scan.py](research/scripts/m93_vector_scan.py) | [数据](research/experiments/m93/) | Vector 扫描 |
| M94 | [m94_growth.py](research/scripts/m94_growth.py) | [数据](research/experiments/m94/) | 缓存增长 |
| M95 | [m95_capture_wrapper.py](research/scripts/m95_capture_wrapper.py) | [数据](research/experiments/m95/) | 捕获封装 |
| M97 | — | [数据](research/experiments/m97/) | 日志分析 |
| M100 | — | [数据](research/experiments/m100/) | MessagePageResult |
| M104 | — | [数据](research/experiments/m104/) | 最终确认 |
| M105 | — | [数据](research/experiments/m105/) | 加密路径分析 |
| M112 | [Route A 脚本集](research/scripts/m112_routeA/) | [数据](research/experiments/m112/) | **数据库解密** |

---

## Ghidra 逆向分析

共 50 轮分析 (M15-M50)：

| 报告 | 内容 |
|------|------|
| [GetPagedMessages Call Tree](research/ghidra/reports/GetPagedMessages_CallTree_Analysis.md) | 28 子函数完整调用树 |
| [M23: 0x2f0 缓存层](research/ghidra/reports/M23_MessageNode_Creator_Hunt.md) | FUN_1816f3510 缓存分析 |
| [M24: 消息管理链路](research/ghidra/reports/M24_5_MessageManager_Validation.md) | 调用链验证 |
| [M25: Creator 上游追踪](research/ghidra/reports/M25_Creator_Hunt_V2_Report.md) | 3 层调用链 |
| [M27: 跨模块分析](research/ghidra/reports/M27_Creator_Upstream.md) | FUN_185b91d80 分析 |
| [M42-M45: 全链路](research/ghidra/reports/M42_M45_Upstream_Report.md) | 端到端数据流 |
| **[M46-M48: Creator 定位](research/ghidra/reports/M46_M48_Creator_Final.md)** | **FUN_181bc3b00 确认** |
| [M50: 历史层搜索](research/ghidra/reports/M50_HistoryLayer_Report.txt) | 存储层分析 |

所有任务指令: [`ghidra/tasks/`](research/ghidra/tasks/)

---

## 研究日志

| 日期 | 日志 |
|------|------|
| 6.4 | [research-6.4.md](research/dailylog/research-6.4.md) |
| 6.5 | [research-6.5.md](research/dailylog/research-6.5.md) |
| 6.6 | [research-6.6.md](research/dailylog/research-6.6.md) |
| 6.7 | [research-6.7.md](research/dailylog/research-6.7.md) |
| 6.8 | [research-6.8.md](research/dailylog/research-6.8.md) |
| 6.10-11 | [research-6.10-11.md](research/dailylog/research-6.10-11.md) |
| 全局 | [HANDOVER.md](research/dailylog/HANDOVER.md) |

---

## 参考文献

| 文档 | 链接 |
|------|------|
| 数据库解密验证 | [M80_DB_Verification_Guide.md](research/reports/M80_DB_Verification_Guide.md) |
| 微信业务对象映射 | [Weixin_Business_Object_Map_V1.md](research/ghidra/reports/Weixin_Business_Object_Map_V1.md) |
| 历史层存储策略 | [m52_strategy.md](research/references/m52_strategy.md) |
| 监控指南 | [m57_history_monitoring_guide.md](research/references/m57_history_monitoring_guide.md) |
| 存储映射总览 | [storage_map.md](research/references/storage_map.md) |
| 完整导出指南 | [full_history_export_guide.md](research/references/full_history_export_guide.md) |
| 工具集 | [tools/](research/tools/) |

---

## 设计文档

| 文档 | 链接 |
|------|------|
| 消息模型设计 | [docs/04_message_model.md](research/docs/04_message_model.md) |
| 导出架构设计 | [docs/05_export_architecture.md](research/docs/05_export_architecture.md) |
| 导出器架构 V1 | [design/v0.1_design/](research/design/v0.1_design/) |
| 项目骨架代码 | [design/v0.1_skeleton/](research/design/v0.1_skeleton/) |

---

## 技术栈

| 工具 | 版本 | 用途 |
|------|------|------|
| Python | 3.13 | 导出器开发 |
| Ghidra | 12.1 | 反汇编分析 |
| Frida | 17.10 | 动态 Hook |
| pymem | 1.14 | 进程内存读写 |
| 目标 | Weixin.dll (175MB) | v4.1.10.29 |

---

## 链接

- **GitHub 仓库**: https://github.com/Ray0612/WeChat-v4-export-research
- **产品工具（单独仓库）**: https://github.com/Ray0612/WeChat-Export-Tool
