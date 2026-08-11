# 项目目录结构

## 顶层布局

```
wechat_exporter/
├── pyproject.toml              ← 项目配置 & 依赖
├── main.py                     ← CLI 入口
├── config.yaml                 ← 默认配置
├── README.md
│
├── src/
│   ├── __init__.py
│   ├── models.py               ← 数据模型 (Message, Session, ...)
│   ├── engine.py               ← ExporterEngine (主控流程)
│   ├── context.py              ← ExporterContext
│   │
│   ├── reader/
│   │   ├── __init__.py
│   │   ├── base.py             ← ProcessReader 接口
│   │   └── weixin_reader.py    ← Weixin ProcessReader
│   │
│   ├── parser/
│   │   ├── __init__.py
│   │   ├── base.py             ← Parser 接口
│   │   └── compact_parser.py   ← 34B 紧凑结构解析器
│   │
│   ├── scanner/
│   │   ├── __init__.py
│   │   ├── base.py             ← Scanner 接口
│   │   ├── memory_scanner.py   ← 进程内存扫描
│   │   └── cache_scanner.py    ← 缓存页定位（34B 前缀搜索）
│   │
│   └── exporter/
│       ├── __init__.py
│       ├── base.py             ← Exporter 接口
│       ├── json_exporter.py    ← JSON 输出
│       └── markdown_exporter.py ← Markdown 输出
│
├── tests/
│   ├── test_compact_parser.py  ← Parser 单元测试
│   ├── test_memory_scanner.py  ← Scanner 测试
│   └── test_exporter.py        ← Exporter 测试
│
└── output/                     ← 导出结果输出目录
```

## 各目录职责

| 目录 | 职责 | 未来扩展 |
|------|------|----------|
| `reader/` | 连接进程、读取内存 | HookReader、FileReader |
| `scanner/` | 在原始数据中定位结构 | 其他缓存格式扫描器 |
| `parser/` | 将二进制解析为 Message 对象 | ProtoBufParser、DBParser |
| `exporter/` | 将 Message 输出为文件 | CSVExporter、HTMLExporter |

## 依赖树

```
main.py
  └── engine.py
        ├── reader/weixin_reader.py   → pymem
        ├── scanner/memory_scanner.py → 扫描缓存页
        ├── parser/compact_parser.py  → 解析 34B 结构
        └── exporter/json_exporter.py → 输出 JSON
```

## 核心原则

1. `scanner` 不直接调用 `parser`，`scanner` 返回原始字节，`parser` 负责解析
2. `parser` 不直接调用 `reader`，parser 只接收 bytes，不关心来源
3. `exporter` 只接收 Message 对象列表，不关心如何获取
4. 每个模块都可以独立测试
