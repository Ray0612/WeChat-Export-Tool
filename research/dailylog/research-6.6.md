# 微信 4.1.9.56/4.1.10.29 研究日志 — 2026-06-06

> 第四天：全面深入探索日 — 从 M6 到 M18 共 13 个里程碑
> 微信版本从 4.1.9.56 升级到 4.1.10.29（中途）

---

## 凌晨：M6-M8 延续旧版分析

### M6：返回值分析（00:00-01:00）
- **方法**：Frida Hook onLeave 捕获 GetPagedMessages 返回值
- **覆盖**：文件传输助手(10次) + 联系人(10次) + 群聊(12次) = 32次
- **核心发现**：retval = arg1（全部 32 次调用一致）
- **结论**：GetPagedMessages 不返回消息列表，通过副作用写入内部缓存
- **文件**：`return_value_analysis_v1.md`

### M7：Global Context 差分分析（01:00-02:00）
- **方法**：dump arg1 的 0x000~0x400 范围，对比 onEnter/onLeave
- **覆盖**：30 次调用（3 个会话 × 10 次翻页）
- **核心发现**：仅有 3 个 8 字节段变化（+0x000/+0x008/+0x010），从 0xaa..aa 变为指针
- **PTR0**（+0x000）= 页面上下文对象
- **PTR8**（+0x008）= Qt 渲染缓冲区
- **结论**：arg1 3 个指针变化但都不是消息数据

### M7.5：MessageList Manager 探索（02:00-02:30）
- **方法**：dump arg0 的 0x1000 字节，翻页前后对比
- **发现**：同一会话内完全不变，切换会话后仅 28-31 字节变化
- **发现**：arg0 包含 SQL schema 引用（"create_time INTEGER"）
- **结论**：arg0 不是消息列表缓存，是会话配置管理器

### M8：离线历史边界测试（02:30-03:00）
- **方法**：Frida 监控 GetPagedMessages + 人工翻页至边界
- **覆盖**：143 次调用，319 天历史（2025-06-21 至 2026-05-06）
- **核心发现**：在线和离线最早到达时间**完全一致**
- **结论**：Case A — 本地缓存全量历史（至少 1 年）

---

## 上午：M9 — 存储路径探索

### M9：文件 API Hook（09:00-10:30）
- **方法**：Hook NtCreateFile/NtReadFile/CreateFileW/MapViewOfFile
- **覆盖**：翻页前后 120 秒，6 个 API 入口
- **核心发现**：翻页期间 **0 次消息相关文件读取**
- **结论**：数据在启动时已加载到内存，翻页不触发文件 I/O

---

## 中午：M10 — 初始加载分析 + 版本升级打击

### M10：启动阶段 Hook（11:00-12:00）
- **尝试**：Frida spawn 启动微信，监控全程文件访问
- **问题**：微信 `4.1.9.56` → `4.1.10.29` 后台自动更新
- **后果**：Weixin.dll 从 181MB → 175MB，**所有函数偏移失效**
- **旧 GetPagedMessages 地址** `0x016ade70` 在新版中变为函数尾声代码

---

## 下午：M11 — 函数重定位 + Ghidra

### M11：新版本函数搜索（13:00-15:00）
- **搜索方法**：在新 DLL 中扫描 "GetPagedMessages" 字符串
- **找到**：字符串在偏移 `0x084f4a2f`（旧版在 `0x83e35a4`）
- **xref 扫描**：找到 1 个 xref（只有旧版的 1/9）
- **问题**：Hook 候选函数不响应翻页（地址计算错误）

### 段偏移修正（15:00-15:30）
- **发现**：.text 段 file_offset → RVA 需要 +0xC00 转换
- **纠正后地址**：`0x016ff6b0`（正确 RVA）

---

## 傍晚：M11.5-M12 — 进程归属 + Mac Ghidra

### M11.5：进程归属验证（16:00-16:30）
- **方法**：CPU/内存监控 + HeapAlloc Hook
- **覆盖**：Weixin.exe + WeChatAppEx.exe（10+ 子进程）
- **结果**：翻页太过轻量，无法通过资源监控判断

### M12：Mac Ghidra 分析（16:30-18:00）
- **任务交接**：写 mac_ghidra_task.md → 用户用 U 盘拷 DLL 到 Mac Mini M4
- **Mac Ghidra 结果**：FUN_1816ff6b0（DLL 偏移 `0x016ff6b0`）
- **确认**：9 个 xref 全部指向 FUN_1816ff6b0（与旧版一致）
- **Ghidra 确认**：函数大小 ~0x3000 字节，与旧版一致

---

## 晚间：M13-M15 — 新版本函数链恢复

### M13：Caller1 分析（19:00-20:00）
- **Ghidra xref**：GetPagedMessages 有 3 个调用者
- **Frida 验证**：Caller1（DLL `0x01683b08`）翻页时 **13 次命中**
- **参数确认**：a0=Manager(恒定), a1=GlobalCtx(恒定), a2=PagingContext(变化), a3=a2+0x20
- **结论**：Caller1 是新版翻页入口

### M14：PagingContext Delta（20:00-21:00）
- **方法**：Hook Caller1，dump arg2 0x200 字节
- **覆盖**：76 次翻页，counter 从 5132 到 2912
- **确认**：PagingContext 结构完全保持（+0x028=cursor, +0x030=counter）
- **每页消息数**：30 条（counter 步长）

### M15：GetPagedMessages Call Tree（21:00-22:00）
- **Ghidra Call Tree**：内部 28 个子函数
- **关键函数**：**FUN_1816c2a20**（DLL `0x016c2a20`）
  - 以步长 `0x2d8` 遍历消息数组
  - Frida 验证：翻页时 40+ 次命中
- **文件**：`GetPagedMessages_CallTree_Analysis.md`

---

## 深夜：M16-M18 — 消息结构恢复

### M16：消息结构体捕获（22:00-23:00）
- **方法**：Hook FUN_1816c2a20，dump a1 指向的 0x2d8 字节
- **样本**：18 个消息条目
- **发现**：结构体包含 wxid、URL、UI 提示符等字段
- **文件**：`reports/message_struct_v1.md`

### M17：唯一标记测试（23:00-23:30）
- **操作**：发送 RAY_TEST_AAA/BBB/CCC 到文件传输助手
- **pymem 扫描**：全部 3 条消息在堆中找到
- **内容地址**：AAA @ 0x1df1c15a24c, BBB @ 0x1df1c15a21c, CCC @ 0x1df56f478e0

### M18：反向指针恢复（23:30-24:00）
- **方法**：以内容地址为目标，全内存扫描反向指针
- **发现**：0x20 步长的指针表
- **最终打通**：0x2d8 消息结构体 → +0x268 = 内容字符串指针
- **文件**：`reports/m18_pointer_chain_v2.md`

---

## 当日总结

### 里程碑完成情况

| 阶段 | 里程碑 | 状态 |
|------|--------|------|
| 旧版收尾 | M6 返回值、M7 GC差分、M8 离线边界 | ✅ 完成 |
| 存储定位 | M9 文件API Hook | ✅ 完成 |
| 版本升级 | M10 初始加载（中断）、M11 函数重定位 | ✅ 完成（路线修正）|
| 新版适配 | M12 Ghidra、M13 Caller1、M14 PagingContext | ✅ 完成 |
| Call Tree | M15 GetPagedMessages 内部结构 | ✅ 完成 |
| 消息结构 | M16 0x2d8 捕获、M17 标记测试、M18 指针链 | ✅ 完成 |

### 关键数据流（最终版）

```
PageUp → Caller1 (0x01683b08)
         → GetPagedMessages (0x016ff6b0)
            → FUN_1816c2a20 (0x016c2a20, 步长 0x2d8)
               0x2d8 消息结构体:
               ├── +0x000: Manager ptr
               ├── +0x120: 接收者 ("filehelper"/"wxid_xxx")
               └── +0x268: → 消息内容 (UTF-8)
```

### 文件产出

- `reports/return_value_analysis_v1.md`
- `reports/global_context_diff_v1.md`
- `reports/message_list_manager_v1.md`
- `reports/offline_history_boundary_test.md`
- `reports/storage_candidate_v1.md`
- `reports/wechat_message_architecture_v1.md`
- `reports/wechat_message_architecture_v1.svg`
- `reports/caller1_analysis.md`
- `reports/pagingcontext_delta_report.md`
- `reports/m15_call_tree_analysis.md`
- `reports/message_struct_v1.md`
- `reports/m17_marker_test_v2.md`
- `reports/m18_pointer_chain_v2.md`
- `references/GetPagedMessages_CallTree_Analysis.md`
- `references/m15_ghidra_calltree.md`
- `scripts/m13-m18.py`（多个脚本）
- 项目重构：README.md, .gitignore, 7 个目录的干净结构
