#!/usr/bin/env python
"""
WeChat V4 Memory Exporter V0.1
从 Weixin.exe 进程内存中导出聊天消息（基于 0x2d8 消息结构体）。
"""
import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.reader.weixin_reader import WeixinReader
from src.scanner.memory_scanner import MemoryScanner
from src.parser.compact_parser import CompactParser
from src.exporter.json_exporter import JsonExporter
from src.exporter.markdown_exporter import MarkdownExporter
from src.engine import ExporterEngine


def main():
    parser = argparse.ArgumentParser(description='WeChat V4 Memory Exporter V0.1')
    parser.add_argument('--output', '-o', default='./output',
                        help='输出目录 (默认: ./output)')
    parser.add_argument('--format', '-f', choices=['json', 'md', 'both'],
                        default='both', help='输出格式 (默认: both)')
    args = parser.parse_args()

    output_dir = os.path.abspath(args.output)
    os.makedirs(output_dir, exist_ok=True)

    print("=" * 50)
    print("  WeChat Memory Exporter V0.1")
    print("  Target: v4.1.10.29 (0x2d8 struct)")
    print("=" * 50)
    print()

    reader = WeixinReader()
    scanner = MemoryScanner(reader)
    parser = CompactParser(reader=reader)

    exporters = []
    if args.format in ('json', 'both'):
        exporters.append(JsonExporter(pretty=True))
    if args.format in ('md', 'both'):
        exporters.append(MarkdownExporter())

    engine = ExporterEngine(reader, scanner, parser, exporters)
    result = engine.run(output_dir)

    print()
    print("-" * 50)
    print(f" 结果:")
    print(f"   消息页:    {result.cache_pages_found}")
    print(f"   消息数:    {result.total_messages}")
    print(f"   会话数:    {len(result.sessions)}")
    print(f"   解析失败:  {result.failed_parses}")
    for w in result.warnings:
        print(f"   警告:      {w}")
    print("-" * 50)

    if result.sessions:
        for s in result.sessions:
            print(f"  [{s.session_tag}] {s.message_count} 条消息")
            for m in s.messages[:3]:
                print(f"    #{m.sequence} - {m.content[:60]}")
        print(f"\n  输出目录: {output_dir}")
    else:
        print("  没有消息被导出。请确认:")
        print("  - 微信正在运行 (Weixin.exe)")
        print("  - 已打开一个聊天窗口")
        print("  - 以管理员权限运行此脚本")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
