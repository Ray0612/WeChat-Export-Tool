# Memory Exporter V0.1 — 可行性评估与最小实现方案

## 核心问题

**不依赖 Hook、不依赖 IDA、不依赖 Frida，仅用 MemoryScanDS，能不能跑通首次导出？**

**结论：能，但字段有限。**

---

## Task 1：最小功能集

```
V0.1 目标：
  [✅] 连接 Weixin.exe 进程（pymem 已验证）
  [✅] 定位紧凑结构缓存页（搜索 1b 02 05 09 01 01 04，已验证）
  [✅] 按 34 字节步长解析（已验证）
  [✅] 提取 sequence + content（已验证）
  [✅] 按 session_tag 分组
  [⚠️] 关联联系人/群聊信息（需要额外扫描记录区）
  [⚠️] 提取 timestamp（紧凑结构不含，需额外扫描）
  [✅] 输出 JSON
  [✅] 输出 Markdown
```

### 能导出的字段（紧凑结构直接提供）

| 字段 | 来源 | 确认度 | 说明 |
|------|------|--------|------|
| content | 紧凑结构偏移+7 | ✅ 30+条验证 | 文本消息明文 |
| sequence | 紧凑结构 content 后 2 字节 | ✅ 同会话+1递增 | 排序用 |
| session_tag | 紧凑结构 `9e 96 XX` | ✅ 不同联系人值不同 | 可区分会话来源 |
| user_id | 紧凑结构 `6a 22 5e` | ✅ 所有消息共有 | 当前用户标识 |

### 不能直接导出的字段（紧凑结构不含）

| 字段 | 需求 | 能否绕过 | 优先级 |
|------|------|----------|--------|
| timestamp | 时间排序 | 可以用 sequence 代替排序 | P1 |
| receiver | 区分消息给谁发的 | 用 session_tag 聚类，显示为"会话#N" | P1 |
| chatroom_name | 可读群名 | 显示为"群聊#N" | P2 |
| msg_id | 去重 | V0.1 不需要 | P3 |

---

## Task 2：字段完整性分析

**V0.1 直接可用的字段：**

```
Message {
    content:     ✅ 100% 可用
    sequence:    ✅ 100% 可用
    session_id:  ✅ 100% 可用（通过 session_tag 区分）
    user_id:     ✅ 可用
}
```

**V0.1 需要简化处理的字段：**

```
Message {
    timestamp:   ⚠️ 用 sequence 代替时间排序
    receiver:    ⚠️ 统一显示为"当前会话"
    chatroom:    ⚠️ 群聊显示为"当前群聊"
}
```

**V0.1 暂不支持的字段：**

```
Message {
    msg_id:      ❌ 紧凑结构不含，需 ProtoBuf
    source:      ❌ msgsource 仅在 ProtoBuf
    attachments: ❌ 图片/文件不在紧凑结构
}
```

**用户可接受度分析：**

即使只有 `content + sequence`，对多数用户来说**已经可以交差了**。导出的消息文本是完整的，只是没有时间戳和接收者标记。对于文件传输助手的消息（自己的消息），这种模式下效果很好；对于其他联系人，需要手动判断会话归属。

---

## Task 3：仅 MemoryScanDS 可行性评估

### 可行部分 ✅

```
1. 找进程 → pymem 已做过了
2. 搜前缀 → pattern_scan_all 已做过，稳定
3. 解析 34B → 已做过，稳定
4. 提取 content → 已做过，支持中英文
5. 提取 sequence → 已做过，准确
6. 按 session_tag 分组 → 可以区分不同会话
7. 输出 JSON/MD → 标准操作
```

### 需新增的部分

```
1. 记录区扫描 → 查找 0x73/0x76/0x77 标记的 wxid/chatroom
   难度：低，已验证能找到
   风险：记录区位置不固定，需全内存搜索

2. 多缓存页遍历 → 处理多个 34B 区域
   难度：低，已验证有 2 个副本
   风险：内容重复，需去重

3. 处理中文 UTF-8 → 从紧凑结构直接提取
   难度：低，已验证支持
   风险：无
```

### 不可行部分 ❌

```
1. 获取历史消息 → 需要翻页触发加载（无法程序化翻页）
   替代方案：仅导出当前可见消息
2. 获取时间戳 → 紧凑结构不含
   替代方案：用 sequence 排序
```

### 综合评估

```
可行性打分：7/10
核心消息文本：✅ 可导出
时间戳：       ⚠️ 缺失（用 sequence 替代）
联系人归属：   ⚠️ 需手动确认
历史深度：     ⚠️ 仅当前页（~25条）
```

---

## Task 4：开发顺序

```
Day 1 — 基础框架
  ├── 项目初始化 + 目录结构
  ├── ExporterEngine 骨架
  ├── ProcessReader 连接 Weixin.exe
  └── 验证：pattern_scan_all(prefix) 返回结果

Day 2 — CompactParser
  ├── 解析 34B 结构
  ├── 提取 content + sequence
  ├── 提取 session_tag + user_id
  └── 验证：正确解析 25 条消息

Day 3 — 记录区扫描（可选增强）
  ├── 搜索 0x73 标记（wxid）
  ├── 搜索 0x76/0x77 标记（chatroom）
  └── 关联到消息

Day 4 — Exporter 输出
  ├── Message → JSON
  ├── Session → Markdown
  └── ExporterContext → 汇总报告

Day 5 — 整合测试
  ├── 端到端流程
  ├── 错误处理
  ├── 中文编码测试
  └── 输出验证
```

**总计：5 天可跑通 V0.1**

---

## 附录：V0.1 最小输出示例

```json
{
  "exporter_version": "0.1",
  "export_time": "2026-06-05 22:00:00",
  "data_source": "memory_scan",
  "sessions": [
    {
      "session_id": "tag_9e9640",
      "type": "file_transfer",
      "messages": [
        {
          "sequence": 331,
          "content": "HELLO_1"
        },
        {
          "sequence": 332,
          "content": "HELLO_2"
        }
      ]
    }
  ]
}
```

**V0.1 的核心价值：** 即使只有 `content + sequence`，已经跑通了从"进程内存"到"结构化导出文件"的完整链路。后续所有迭代都是在补字段，而不是重新设计架构。
