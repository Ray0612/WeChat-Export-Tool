# M16 — Message Struct V1

> 实验时间：2026-06-06
> 方法：Frida Hook FUN_1816c2a20 onEnter，dump a1 指向的 0x2d8 字节
> 样本：18 条消息结构体（群聊 49622797405@chatroom）

---

## 消息结构体总览

| 项目 | 值 |
|------|-----|
| 结构体总大小 | **0x2d8 (728 字节)** |
| 验证方式 | FUN_1816c2a20 循环遍历，步长 0x2d8 |
| 调用频率 | ~8 次/翻页（每页 ~30 条消息，每次调用处理 ~4 条） |
| Ghidra 确认 | 结构体步长与 4.1.9.56 一致 |

## 已识别的字段

| 偏移 | 大小 | 内容 | 示例 |
|------|------|------|------|
| +0x000 | 8 | 发送者 wxid 指针 | → `"wxid_22e48sxjw2c222"` |
| +0x030 | ~30B | 发送者 wxid（内联副本） | `"wxid_22e48sxjw2c222"` |
| +0x090 | ~30B | 其他用户 wxid（如群聊中其他成员） | `"wxid_caccoealsdbj12"` |
| +0x120 | var | URL/服务器地址 | `"/cgi-bin/micromsg-bin/heartbeat"` |
| +0x150 | var | 短域名 | `"shshort.weixin.qq.com"` |
| +0x180 | var | 短域名 | `"sgshort.wechat.com"` |
| +0x1b0 | var | 域名 | `"long.weixin.qq.com"` |
| +0x210 | var | 域名 | `"szlong.weixin.qq.com"` |
| 0x120-0x240 | var | 多个 URL/配置字符串 | 微信服务器地址、CDN 等 |
| +0x288 | var | UI 渲染提示 | `"mmui::XTextView"`, `"_q_no_animation"` |
| 0x090-0x1e0 | var | 消息内容（UTF-8 中文，非内联） | 通过指针引用，实际内容在堆上 |

## 消息内容字段

消息文本内容（中文聊天消息）在 dump 中出现在不同偏移（0x090, 0x120, 0x1b0, 0x1e0, 0x1e8, 0x270），说明**文本内容是通过指针/偏移引用的，非固定内联字段**。

可能的存储方式：
1. **指针 + 长度** — +0x?? 处存 char* 指针，指向堆上的 UTF-8 字符串
2. **偏移量 + 长度** — 相对于结构体起始的偏移
3. **嵌入在变长字段中** — 部分消息内容可能内联在结构体末尾的变长区域

## 已知字段模型

```
+0x000  sender_wxid_ptr    (8B ptr → "wxid_xxx")
+0x008  unknown             (padding/field)
+0x010  marker_13           (8B, 值 0x13)
+0x018  marker_1f           (8B, 值 0x1f)
+0x020  inner_ptr           (8B ptr → 某对象)
+0x028  sequence / msg_id   (8B, 推测)
+0x030  sender_wxid_copy    (字符串内联)
...
+0x090  other_wxid          (如群聊中不同发送者)
...
+0x120  url_fields          (服务器地址等)
...
+0x1e0  content_area        (消息文本/内容)
...
+0x288  ui_hints            (渲染提示字符串)
...
0x2d8   END
```

## 未确认字段

| 字段 | 重要性 | 当前状态 |
|------|--------|---------|
| timestamp | **P0** | 未定位（应在 +0x028 附近） |
| content pointer | **P0** | 未定位（文本通过指针引用） |
| msg_type | **P1** | 未定位（文本/图片/系统消息） |
| sequence (同会话) | **P1** | 旧版在 +0x?? 紧凑结构中 |

## 下一步

1. 发送带唯一标记的测试消息 → 翻页 → 在 dump 中搜标记 → 确定 content 指针位置
2. 在 Ghidra 中追踪 FUN_1816c2a20 内部，找到读取 content 字段的指令
3. 分析 +0x028 的值变化规律，确认是 timestamp 还是 msg_id
