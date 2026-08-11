# M19A — Compact Exporter PoC

> 实验时间：2026-06-07
> 版本：v0.1_skeleton 实现

---

## 结果

| 指标 | 值 |
|------|-----|
| 扫描页数 | 61 |
| 消息总数 | 100 |
| 有内容消息 | 78 |
| 会话数 | 57 |
| 导出格式 | JSON + Markdown |

## 代码位置

`design/v0.1_skeleton/` 已从骨架实现为可运行代码：

```
src/
├── main.py              # CLI 入口，已实现
├── engine.py            # 导出引擎，已实现
├── models/__init__.py   # Message/Session/ExportResult 数据模型
├── reader/weixin_reader.py  # pymem 进程读取器，已实现
├── scanner/memory_scanner.py  # 0x2d8 结构体扫描，已实现
├── parser/compact_parser.py   # 结构体解析 + 指针解析，已实现
└── exporter/
    ├── json_exporter.py      # JSON 导出，已实现
    └── markdown_exporter.py  # Markdown 导出，已实现
```

## 已知问题

| 问题 | 原因 | 优先级 |
|------|------|--------|
| content 内容乱码 | 内容指针偏移因消息类型而变化 | P0 |
| 大量空会话 | 许多 0x2d8 块没有有效接收者 | P1 |
| GBK 控制台编码 | Windows 终端限制 | P2 |

## 下一步

1. 改进内容指针偏移检测（根据消息类型动态选择 +0x268 或 +0x288）
2. 增加 receiver/timestamp 等字段的提取
3. 集成到完整 CLI 工具
