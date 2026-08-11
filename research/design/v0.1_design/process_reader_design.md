# ProcessReader 设计

## 职责

连接 Weixin.exe 进程，读取其内存。只负责"读"，不负责"解析"。

## 接口

```python
@dataclass
class ProcessInfo:
    pid: int
    name: str
    dll_base: int           # Weixin.dll 基址
    dll_size: int           # Weixin.dll 大小


class ProcessReader:
    """
    进程内存读取器。
    封装 pymem，提供进程连接和内存读取能力。
    """
    
    def open(self) -> bool:
        """
        连接 Weixin.exe 进程。
        返回 False 表示微信未运行。
        """
    
    def close(self) -> None:
        """断开连接，释放资源。"""
    
    @property
    def info(self) -> ProcessInfo:
        """获取当前进程信息。"""
    
    @property
    def is_open(self) -> bool:
        """是否已连接。"""
    
    def read_bytes(self, address: int, size: int) -> bytes:
        """
        从指定地址读取内存。
        返回原始字节。
        """
    
    def search_pattern(self, pattern: bytes, return_multiple: bool = False) -> list[int]:
        """
        全进程搜索字节模式。
        返回匹配地址列表。
        """
    
    def search_in_module(self, pattern: bytes, module_name: str) -> list[int]:
        """
        在指定模块中搜索字节模式。
        V0.1 用于在 Weixin.dll 中搜索特定模式。
        """
```

## V0.1 最小实现

```python
class WeixinReader(ProcessReader):
    """Weixin.exe 专用读取器。"""
    
    WEIXIN_PROCESS_NAMES = ["Weixin.exe"]
    
    def open(self) -> bool:
        # 1. 用 pymem 枚举进程
        # 2. 匹配 Weixin.exe
        # 3. 打开进程句柄
        # 4. 定位 Weixin.dll 基址
    
    def search_compact_prefix(self) -> list[int]:
        """搜索紧凑结构前缀 1b 02 05 09 01 01 04。"""
        return self.search_pattern(COMPACT_PREFIX)
```

## 与 Parser 解耦

```
ProcessReader 只返回 bytes:
  reader = WeixinReader()
  reader.open()
  raw_bytes = reader.read_bytes(address, 34)

Parser 接收 bytes:
  parser = CompactParser()
  msg = parser.parse(raw_bytes)

ProcessReader 不需要知道 Message 是什么。
Parser 不需要知道字节从哪来的。
```
