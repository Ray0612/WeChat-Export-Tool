# WeChat V4 Memory Exporter V0.1

从微信 4.1.9.56（Weixin.exe）进程内存中导出聊天消息。

## 项目目标

在**不依赖逆向、不依赖 Hook、不依赖 Frida** 的前提下，直接从 Weixin.exe 的堆内存中扫描并导出聊天消息。

## 当前能力

- 连接 Weixin.exe 进程
- 定位紧凑结构缓存页（搜索 `1b 02 05 09 01 01 04`）
- 按 34 字节步长遍历消息
- 提取：消息内容、序列号、会话标识
- 输出：JSON / Markdown

## 已知限制

| 限制 | 说明 |
|------|------|
| 消息数 | 仅当前可见的 ~25 条（缓存深度有限） |
| 时间戳 | 暂不支持（紧凑结构不含） |
| 联系人关联 | 暂不自动关联（需额外扫描记录区） |
| 翻页 | 暂不支持（需 Hook GetPagedMessages） |
| 图片/文件 | 暂不支持 |

## 用法

```bash
pip install -r requirements.txt

# 以管理员身份运行
python src/main.py --output ./my_chat
```

## 文件结构

```
src/
├── main.py                   CLI 入口
├── engine.py                 ExporterEngine（主控流程）
├── reader/
│   └── weixin_reader.py      ProcessReader（内存读取）
├── scanner/
│   └── memory_scanner.py     MemoryScanner（缓存页定位）
├── parser/
│   └── compact_parser.py     CompactParser（34B 结构解析）
├── exporter/
│   ├── json_exporter.py      JSON 输出
│   └── markdown_exporter.py  Markdown 输出
├── models/
│   └── __init__.py           数据模型
└── utils/
    └── __init__.py           工具
```

## 依赖

- pymem >= 1.14.0（进程内存读写）

## 验证于

- Windows 11 中文版
- 微信 4.1.9.56（Weixin.exe）
- Python 3.13.5

## 路线图

| Phase | 内容 | 状态 |
|-------|------|------|
| V0.1 | 基础内存扫描 → 导出 | 设计中 |
| V0.2 | 记录区关联（联系人/群聊信息） | 计划中 |
| V0.3 | Frida Hook 翻页加载 | 计划中 |
| V0.4 | 图片/文件导出 | 计划中 |
