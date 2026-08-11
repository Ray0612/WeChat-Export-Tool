"""
ProcessReader — 微信进程内存读取器。
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import pymem
import pymem.exception


@dataclass
class ProcessInfo:
    pid: int
    name: str
    dll_base: int
    dll_size: int


class WeixinReader:
    """Weixin.exe 内存读取器。"""

    PROCESS_NAMES = ["Weixin.exe"]

    def __init__(self):
        self._pm: Optional[pymem.Pymem] = None
        self._info: Optional[ProcessInfo] = None

    def open(self) -> bool:
        # Find the correct Weixin.exe with Weixin.dll
        import psutil
        for p in sorted(psutil.process_iter(['pid', 'name']), key=lambda x: x.info['pid']):
            if p.info['name'] not in self.PROCESS_NAMES:
                continue
            try:
                pm = pymem.Pymem()
                pm.open_process_from_id(p.info['pid'])
                for mod in pm.list_modules():
                    mod_name = mod.name.split("\\")[-1].lower()
                    if "weixin.dll" == mod_name:
                        self._pm = pm
                        self._info = ProcessInfo(
                            pid=p.info['pid'],
                            name="Weixin.exe",
                            dll_base=mod.lpBaseOfDll,
                            dll_size=mod.SizeOfImage,
                        )
                        return True
                pm.close_process()
            except:
                pass
        return False

    def close(self):
        if self._pm:
            try:
                self._pm.close_process()
            except:
                pass
        self._pm = None
        self._info = None

    @property
    def info(self) -> Optional[ProcessInfo]:
        return self._info

    @property
    def is_open(self) -> bool:
        return self._pm is not None

    def read_bytes(self, address: int, size: int) -> bytes:
        return self._pm.read_bytes(address, size)

    def search_pattern(self, pattern: bytes, return_multiple: bool = False):
        return self._pm.pattern_scan_all(pattern, return_multiple=return_multiple)
