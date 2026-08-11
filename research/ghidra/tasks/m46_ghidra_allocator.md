# M46 — Find MessageNode Allocator (Ghidra Task)

找到谁分配了 0x2d8 MessageNode 数组。

## Task 1

在 **Weixin.dll** 中搜 `0x2d8` 常量。重点看：
- `imul ?, ?, 0x2d8` — 乘法指令（count * 0x2d8）
- `add ?, 0x2d8` — 加法指令（步进）
- `0x2d80` `0x5b00` `0x8a18` `0xb600` — 常见的批量大小（10/20/30/40 倍）

## Task 2

如果 Weixin.dll 中没有找到分配点，分析 **FUN_185b91d80** 的所有上游 xref，看是从哪个模块进入的。可能来自 WeChatWin.dll 或其他 DLL。

如果需要，在 Ghidra 中导入 WeChatWin.dll（通常在 Weixin.exe 同目录或 `XPlugin\Plugins\` 下）。

## Task 3

找到 `malloc(0x2d8)` 或 `operator new(0x2d8)` 或 `count * 0x2d8` 后，检查是否紧跟着写入 `+0x120`(receiver) 或 `+0x268`(content_ptr)。如果是，就是 Creator。

## 输出

```
Allocator: FUN_XXXXXXXX (DLL偏移 0xXXXXXXXX) — in [Weixin.dll/WeChatWin.dll]
分配方式: malloc(0x2d8) / imul + new / 批量
字段写入: +0x120/receiver, +0x268/content [是/否]
```
