"""
MemoryScanner — 0x2d8 消息结构体扫描器。
v4.1.10.29 不再使用 34B 紧凑结构，改用完整的 0x2d8 消息结构体。
"""
from __future__ import annotations
import struct
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from src.reader.weixin_reader import WeixinReader


class MemoryScanner:
    """扫描进程内存，定位 0x2d8 消息结构体。"""

    ENTRY_SIZE = 0x2d8

    def __init__(self, reader: WeixinReader):
        self._reader = reader

    def find_candidate_pages(self) -> list[tuple[int, list[bytes]]]:
        """
        扫描 0x2d8 消息结构体。
        搜索策略：在堆中找包含 'filehelper' 或 'wxid_' 的 0x2d8 对齐块。
        """
        import pymem.memory
        pm = self._reader._pm
        if not pm:
            return []

        # Use pymem's pattern_scan_all to find filehelper/wxid references
        pages = []
        found_blocks = set()

        for pattern in [b'filehelper', b'wxid_']:
            try:
                addrs = pm.pattern_scan_all(pattern, return_multiple=True)
            except:
                addrs = []

            for addr in addrs[:200]:  # Limit
                # Check if this address is at +0x120 within a 0x2d8 block
                off_in_block = addr % self.ENTRY_SIZE
                if off_in_block != 0x120:
                    # Try nearby: filehelper might be at slightly different offsets
                    if addr % 8 != 0:  # Must be aligned
                        continue

                block_start = addr - 0x120  # Assume filehelper at +0x120
                # Align to 0x2d8 boundary
                block_start = block_start - (block_start % self.ENTRY_SIZE)

                if block_start in found_blocks:
                    continue
                found_blocks.add(block_start)

                try:
                    data = pm.read_bytes(block_start, self.ENTRY_SIZE)
                    if len(data) != self.ENTRY_SIZE:
                        continue

                    # Verify: should have a content pointer at +0x268 or +0x288
                    has_content = False
                    for coff in [0x268, 0x288]:
                        if coff + 8 <= len(data):
                            cv = struct.unpack_from('<Q', data, coff)[0]
                            if 0x100000 < cv < 0x7fffffffffff:
                                has_content = True
                                break

                    if has_content:
                        entries = [data]
                        # Check adjacent blocks
                        for delta in range(1, 30):
                            next_block = block_start + delta * self.ENTRY_SIZE
                            try:
                                nd = pm.read_bytes(next_block, self.ENTRY_SIZE)
                                if len(nd) == self.ENTRY_SIZE:
                                    # Check for content ptr
                                    valid = False
                                    for coff in [0x268, 0x288]:
                                        cv = struct.unpack_from('<Q', nd, coff)[0]
                                        if 0x100000 < cv < 0x7fffffffffff:
                                            valid = True
                                            break
                                    if valid:
                                        entries.append(nd)
                                    else:
                                        break
                                else:
                                    break
                            except:
                                break

                        if len(entries) >= 1:
                            pages.append((block_start, entries))
                except:
                    continue

        # Deduplicate overlapping pages
        unique_pages = []
        seen_starts = set()
        for start, entries in sorted(pages, key=lambda x: x[0]):
            if start not in seen_starts:
                seen_starts.add(start)
                unique_pages.append((start, entries))

        return unique_pages
