# M90 差分实验发现

## PID 17292 (Weixin.exe 主进程)
- 持有 message_0.db 文件句柄
- 包含 WMPF host DLL (SQLCipher)
- 255 处测试字符串
- Flutter 文本渲染缓存（中文指令内容）

## 关键发现：结构化消息缓存

在 PID 17292 堆中发现消息记录格式：
```
{digit}.{wxid}{message_content}{uuid}
```

示例:
```
3.wxid_mrbjgwbhoo3y12M90_ONLY_ONCE_A7D29F4B648b-4d46-89b6-a839cedbb94a
```

检测到的 wxid:
- wxid_caccoealsdbj12 (owner)
- wxid_mrbjgwbhoo3y12 (contact)
- wxid_adrsy60kqcxr22
- wxid_hq0gm7sd01bt22
- wxid_7294432945222
- wxid_22e48sxjw2c222
- wxid_myru1g67q64u22

## 验证的死路

- sqlite3 handle: 藏在 C++ 对象深处，搜索不到
- 调试器断点: 进程重启太快
- 已解密 SQLite 页: 用完即释放，不缓存
- sqlite3_exec: 在当前进程找不到函数体
