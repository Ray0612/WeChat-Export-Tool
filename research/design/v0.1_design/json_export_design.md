# JsonExporter 设计

## 职责

将 ExportResult 对象输出为 JSON 文件。

## 接口

```python
class JsonExporter:
    """
    JSON 格式导出器。
    输出 UTF-8 编码的 JSON 文件，包含所有会话和消息。
    """
    
    def export(self, result: ExportResult, output_path: str) -> str:
        """
        导出为 JSON 文件。
        output_path: 输出目录
        返回：输出文件路径
        """
```

## JSON Schema (V0.1)

```json
{
  "$schema": "v0.1",
  "exporter": {
    "version": "0.1.0",
    "name": "wechat_memory_exporter"
  },
  "export_info": {
    "time": "2026-06-05T22:00:00",
    "data_source": "memory_scan_v0.1",
    "wechat_version": "4.1.9.56",
    "cache_pages_found": 2,
    "total_messages": 25,
    "failed_parses": 0
  },
  "sessions": [
    {
      "session_tag": "9e9640",
      "name": "session_9e9640",
      "message_count": 20,
      "first_sequence": 341,
      "last_sequence": 360,
      "messages": [
        {
          "sequence": 341,
          "content": "MSG_001"
        },
        {
          "sequence": 342,
          "content": "MSG_002"
        }
      ]
    }
  ],
  "warnings": [
    "时间戳字段未包含（V0.1 暂不支持）",
    "联系人信息未关联"
  ]
}
```

## 字段说明

| JSON 字段 | 来源 | 说明 |
|-----------|------|------|
| session_tag | 紧凑结构 `9e 96 xx` | 用于区分不同会话 |
| sequence | 紧凑结构序号 | 同会话内排序依据 |
| content | 紧凑结构内容 | 消息文本 |

## 文件路径

```
output/
└── export_20260605_220000/
    ├── messages.json          ← 完整导出
    └── export_summary.json    ← 仅汇总信息（快速预览）
```

## 选项

```python
class JsonExporter:
    def __init__(self, pretty: bool = True, include_raw: bool = False):
        self.pretty = pretty          # 是否格式化输出
        self.include_raw = include_raw  # 是否包含原始二进制（调试用）
```
