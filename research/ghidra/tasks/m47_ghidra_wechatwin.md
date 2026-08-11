# M47 — Enter WeChatWin.dll (Ghidra Task)

## 背景

Weixin.dll 中的 FUN_1816ef670 是 Getter（只读不创建）。0x2d8 MessageNode 数组在进入 Weixin.dll 前已存在。需要分析 WeChatWin.dll。

## 找到 WeChatWin.dll

在微信安装目录 `D:\Program Files\Tencent\Weixin\4.1.10.29\` 或 `XPlugin\Plugins\` 下找 WeChatWin.dll。如果不在这些位置，用 Everything 搜一下。

拖入 Ghidra 分析（可能需要 30-60 分钟）。

## Task 1

在 WeChatWin.dll 中搜索 `0x2d8` 常量：
- `imul ?, ?, 0x2d8` — 批量分配
- `add ?, 0x2d8` — 步进
- `0x5b00` (20×) / `0x8a18` (30×) / `0xb600` (40×)

## Task 2

搜索 `malloc` / `new` 附近出现 `0x2d8` 或上述倍数的代码。

## Task 3

在 Weixin.dll 的 Ghidra 中，打开 FUN_185b91d80，找 References to Address，找出从 WeChatWin.dll 来的调用者。

## Task 4

找到分配点后，检查是否立即写入 +0x120(receiver)、+0x268(content_ptr)、+0x288。

## 输出

```
Module: WeChatWin.dll
Allocator: FUN_XXXXXXXX
分配方式: [new / malloc / imul 批量]
字段写入: [+0x120 / +0x268] [是/否]
```
