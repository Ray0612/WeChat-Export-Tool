"""
CompactParser — 0x2d8 消息结构体解析器。
v4.1.10.29 使用 0x2d8 字节完整消息结构。
"""
from __future__ import annotations
import struct
from typing import Optional, Any
from src.models import Message


ENTRY_SIZE = 0x2d8


class CompactParser:
    """解析 0x2d8 消息结构体为 Message 对象。"""

    def __init__(self, reader: Optional[Any] = None):
        self._reader = reader  # pymem reader for pointer resolution

    def _resolve_ptr(self, ptr: int) -> str:
        """将内存地址解析为字符串。"""
        if not ptr or not self._reader:
            return ""
        try:
            raw = self._reader.read_bytes(ptr, 200)
        except:
            return ""
        end = raw.find(b'\x00')
        if end > 0:
            raw = raw[:end]
        try:
            return raw.decode('utf-8', errors='replace')
        except:
            return raw.hex()

    def extract_content(self, data: bytes) -> str:
        """从 +0x268 或 +0x288 读取内容字符串。"""
        for offset in (0x268, 0x288):
            if offset + 8 > len(data):
                continue
            ptr = struct.unpack_from('<Q', data, offset)[0]
            if 0x100000 < ptr < 0x7fffffffffff:
                text = self._resolve_ptr(ptr)
                if text and len(text) >= 2:
                    return text
        return ""

    def extract_receiver(self, data: bytes) -> str:
        """从 +0x120 读取接收者名称（内联字符串）。"""
        recv_data = data[0x120:0x150]
        end = recv_data.find(b'\x00')
        if end > 0:
            try:
                return recv_data[:end].decode('utf-8', errors='replace')
            except:
                pass
        return ""

    def extract_sequence(self, data: bytes) -> int:
        """读取可能的序号字段。"""
        for offset in (0x028, 0x030):
            if offset + 4 > len(data):
                continue
            val = struct.unpack_from('<I', data, offset)[0]
            if 0 < val < 100000:
                return val
        return 0

    def parse_one(self, data: bytes) -> Message | None:
        if len(data) < ENTRY_SIZE:
            return None

        content = self.extract_content(data)
        receiver = self.extract_receiver(data)

        if not receiver and not content:
            return None

        return Message(
            sequence=self.extract_sequence(data),
            content=content,
            session_tag=receiver or "unknown",
            receiver=receiver,
        )

    def parse_batch(self, data_list: list[bytes]) -> list[Message]:
        return [self.parse_one(d) for d in data_list if len(d) >= ENTRY_SIZE]
