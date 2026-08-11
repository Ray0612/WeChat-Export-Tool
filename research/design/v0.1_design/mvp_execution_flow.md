# MVP 执行流程

## 用户视角

```bash
pip install -r requirements.txt
python main.py --output ./my_chat
```

## 完整执行流程

```
用户执行 python main.py
    │
    ▼
[1] 解析命令行参数
    ├── --output  (输出目录)
    ├── --format  (格式: json / md / both，默认 both)
    └── --verbose (详细日志)
    │
    ▼
[2] ProcessReader.open()
    ├── 枚举所有进程
    ├── 匹配 Weixin.exe
    ├── 打开进程句柄
    ├── 获取 Weixin.dll 基址
    └── 返回 ProcessInfo
    │
    ▼
[3] MemoryScanner.scan_cache_pages()
    ├── 搜索 1b 02 05 09 01 01 04 (全进程)
    ├── 按地址聚类（每 64KB 为一页）
    ├── 过滤小聚类（< 3 条 = 噪声）
    └── 返回 cache_page_addresses[]
    │
    ▼
[4] 对每个缓存页地址:
    ├── PageReader.read_page(address)
    │   ├── 从 address 开始，每 34B 读一条
    │   └── 读满 25 条或遇到无效数据为止
    │
    ▼
[5] CompactParser.parse_batch(raw_entries)
    ├── validate(entry) → 过滤无效
    ├── extract_content → content
    ├── extract_sequence → sequence
    ├── extract_session_tag → session_tag
    ├── extract_user_id → user_id
    └── 返回 Message[]
    │
    ▼
[6] deduplicate_and_cluster(messages)
    ├── 按 session_tag 分组
    ├── 组内按 sequence 排序
    ├── 跨页去重（sequence 相同 = 重复）
    └── 返回 Session[]
    │
    ▼
[7] ExporterEngine.export(sessions)
    ├── 构建 ExportResult
    ├── JsonExporter.export() → messages.json
    ├── MarkdownExporter.export() → messages.md
    └── 打印汇总报告
    │
    ▼
    完成。输出在 ./my_chat/export_时间戳/
```

## 时序图

```
main.py          Engine         Reader        Scanner       Parser      Exporter
  │                │              │              │            │           │
  │───run()───────▶│              │              │            │           │
  │                │──open()─────▶│              │            │           │
  │                │◀─ProcessInfo─│              │            │           │
  │                │──scan()────────────────────▶│            │           │
  │                │◀────addresses───────────────│            │           │
  │                │──read(address)─────────────▶│            │           │
  │                │◀────raw_bytes───────────────│            │           │
  │                │──parse(raw)─────────────────────────────▶│           │
  │                │◀────Message──────────────────────────────│           │
  │                │──export(sessions)──────────────────────────────────▶│
  │                │◀───────────file_path───────────────────────────────│
  │◀───result─────│              │              │            │           │
  │───print()────▶│              │              │            │           │
```

## 关键决策点

| 决策 | 选项 | V0.1 选择 |
|------|------|-----------|
| 如何处理重复缓存页 | 去重 / 保留副本 | **去重**（按 sequence + content 去重）|
| 解析失败时 | 中断 / 跳过 | **跳过**（记录 failed_parses）|
| 输出目录已存在 | 覆盖 / 新建 | **新建** `export_时间戳/` |
| 编码问题 | 严格 / 容错 | **容错**（UTF-8 → GBK → ASCII 降级）|
