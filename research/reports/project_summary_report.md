# 微信 4.1.x 导出项目 — 最终总结报告

> 研究周期：2026-06-04 ~ 2026-06-07（4 天）
> 微信版本：4.1.9.56 → 4.1.10.29（中途升级）
> 核心工具：Ghidra 12.1, Frida 17.10, pymem 1.14
> 里程碑：36 轮

---

## 一、核心结论

### 存储模型

| 结论 | 证据 | 状态 |
|------|------|------|
| 聊天记录不在磁盘 | 35,063 文件搜索 0 匹配 | ✅ **Confirmed** |
| 聊天记录在 Weixin.exe 内存 | pymem 57 匹配 + Frida 验证 | ✅ **Confirmed** |
| 离线可翻全部历史 | 143 页翻页，counter=1 到达边界 | ✅ **Confirmed** |
| SQLite/LevelDB/MMKV 不存消息 | 全盘搜索 + ProcMon 无 .db 访问 | ✅ **Confirmed** |
| 翻页时不读文件 | NtCreateFile/NtReadFile Hook 确认 | ✅ **Confirmed** |

### 消息架构

```
翻页 (PageUp)
  → Caller1 (0x01683b08)
    → GetPagedMessages (0x016ff6b0)
      → FUN_1816c2a20 (0x016c2a20)
        → 0x2d8 MessageNode (元数据: receiver, msgid, msgsource)
        → 紧凑结构 (39B, 内联文本)  ← 唯一包含真实文本的格式
```

### 消息内容存储

最终发现：消息文本通过**紧凑结构（39B/条）** 内联存储在堆中。前缀为 `XX 02 05 09 01 01 04`（旧版为 `1b 02 05 09 01 01 04`，新版首位字节变化）。

```
[PREFIX 7B] [Content UTF-8] [0x04] [Seq 2B] [SessionTag ~8B] [Header ~8B] [Padding]
```

## 二、版本差异（4.1.9.56 → 4.1.10.29）

| 项目 | 旧版 | 新版 |
|------|------|------|
| Weixin.dll 大小 | 181MB | 175MB |
| GetPagedMessages 偏移 | `0x016ade70` | `0x016ff6b0` |
| Caller1 / 翻页入口 | 未知 | `0x01683b08` |
| 紧凑结构步长 | 34B | ~39B |
| 紧凑结构前缀 | `1b 02 05 09` | `XX 02 05 09` (XX 变化) |
| 字符串区位置 | `0x83e35a4` | `0x084f4a2f` |
| .text 段起 | file: `0x400` VA: `0x1000` | 同左 |
| 完成度 | Ghidra 分析完整 | Ghidra 分析完整 |

## 三、已验证的路径

### ✅ 有效（成功捕获消息）

| 方法 | 覆盖范围 | 输出 |
|------|---------|------|
| pymem 扫描紧凑结构 `02 05 09` | 全堆 | 241 条消息 |
| Frida Hook FUN_1816c2a20 循环体 | 翻页时的消息元数据 | 90+ 条/次 |
| Frida Hook Caller1 | PagingContext (receiver, cursor) | 每页 |

### ❌ 无效（已证明不可行）

| 路径 | 原因 |
|------|------|
| 数据库解密 | V4 不使用 SQLite |
| 自动翻页 | Chromium 拦截所有程序化输入 |
| 文件 API Hook | 翻页时不读文件 |
| pymem 扫描 0x2d8 | 生命周期极短，无法后处理 |
| 反向指针追踪 | 文本内联存储，无指针引用 |

## 四、关键函数地址（v4.1.10.29）

| 函数 | DLL 偏移 | 说明 |
|------|---------|------|
| Caller1 | `0x01683b08` | 翻页入口，Hook 此函数 |
| GetPagedMessages | `0x016ff6b0` | 消息加载 |
| FUN_1816c2a20 | `0x016c2a20` | 消息过滤遍历，步长 0x2d8 |
| FUN_1816c2a20 循环体 | `0x016c2a76` | R14 指向当前 0x2d8 元素 |
| FUN_1816f3510 | `0x016f3510` | 消息缓存（0x2f0 分配） |
| FUN_1816f3b30 | `0x016f3b30` | GetMessageListBySvrIds |
| FUN_181771eb0 | `0x01771eb0` | 消息管理分发 |
| FUN_185b91d80 | `0x05b91d80` | 上游消息处理 |

## 五、项目结构（最终）

```
wechat_v4_export_research/
├── README.md                   # 项目介绍
├── .gitignore
│
├── daily/                      # 每日研究日志 (4 天)
│   ├── research-6.4.md
│   ├── research-6.5.md
│   ├── research-6.6.md
│   └── research-6.7.md
│
├── reports/                    # 15 份关键报告
│   ├── wechat_message_architecture_v1.md
│   ├── wechat_message_architecture_v1.svg
│   ├── project_summary_report.md       ← 本文件
│   └── ... (各里程碑报告)
│
├── scripts/                    # 25 个实验脚本
│   ├── m36_compact_exporter.py         ← 最终导出器
│   └── ... (各里程碑脚本)
│
├── experiments/                # 实验输出
│   ├── logs/                   # 原始日志
│   └── dumps/                  # 二进制 dump
│
├── design/                     # 设计文档
│   ├── v0.1_design/
│   └── v0.1_skeleton/
│
└── references/                 # 参考文档
    ├── weixin-decrypte-script/
    ├── GetPagedMessages_CallTree_Analysis.md
    └── mac_ghidra_task.md
```

## 六、导出的消息样本

| Seq | 内容 | 类型 |
|-----|------|------|
| 329 | `TEST_RAY_20260605_938274615` | 测试消息（第 1 天） |
| 331 | `HELLO_1` | 测试消息 |
| 341 | `MSG_001` | 测试消息 |
| 263 | `https://lingdaoyi1.pages.dev/0519` | 真实 URL |
| 266 | `https://grizzlysms.com/cn/profile` | 真实 URL |
| 322 | `107.161.82.74` | 真实 IP |
| 323 | `wreHKVX75A1xs0Xc65` | 验证码 |

## 七、后续建议

| 方向 | 说明 | 优先级 |
|------|------|--------|
| 完善紧凑结构解析 | 正确切分中文 UTF-8 文本 | P0 |
| 按会话聚类 | 通过 session_tag 区分不同聊天 | P1 |
| 扫描其他堆区域 | 扩展到 0x21d 范围之外 | P1 |
| 时间戳提取 | 从 PagingContext +0x028 关联 | P2 |
| GitHub 发布 | 代码开源 | P2 |
