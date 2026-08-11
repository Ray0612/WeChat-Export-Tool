# M100 — CoGetSessionMessageListWithPageFromDB 输出结构

## 函数签名 (推测)

```cpp
// 从字符串: "index:{R8}, session:{R9}, from localid:{stack+0x30}"
undefined8 CoGetSessionMessageListWithPageFromDB(
    undefined8 this,              // RCX: Controller/Service对象
    undefined8 output,            // RDX: 输出回调/容器
    int index,                    // R8:  页码/序号
    SSOString* session_name,      // R9:  wxid/chatroom
    uint page_size,               // [RSP+0x28]: 每页条数
    uint from_localid,            // [RSP+0x30]: 分页游标(起始local_id)
    QueryConfig* config           // [RSP+0x38]: 查询配置
);
```

## QueryConfig 结构 (由 FUN_1816fa3f0 反推)

```cpp
struct QueryConfig {           // 0x70+ bytes
    int orientation;            // +0x00: 排序方向
    int sort_order;             // +0x04: 排序方式  
    // ...padding...
    uint64 types;               // +0x18: 消息类型位掩码
    SSOString sender;           // +0x30: 发送者筛选
    int query_more;             // +0x68: 加载更多标志
    byte reserve_content;       // +0x6c: 保留内容
    byte cancel_last;           // +0x6d: 取消最后一条
    byte serial_task;           // +0x6e: 串行任务
};
```

## 内部数据结构 (0xA0 bytes)

```cpp
struct MessagePageResult {     // 由 FUN_18680e0fc(0xA0) 分配
    // +0x00 ~ +0x27: 虚表/函数指针 (FUN_1800fc880 设置)
    void* vtable[5];            // +0x00~+0x27
    
    // +0x28 ~ +0x9F: 查询参数 + 结果
    QueryConfig config;         // +0x28: 查询参数副本
    // 结果部分:
    Message* message_array;     // +0x80?: 消息数组指针
    uint64 message_count;       // +0x88?: 消息数量
    // ...可能还有分页信息
};
```

## 关键函数调用链

```
CoGetSessionMessageListWithPageFromDB (FUN_18360c210)
  │
  ├── FUN_1800fc880(0xA0) → 分配结果结构体
  │
  ├── FUN_18365aa50 → 填充查询参数
  │   ├── page_size (param_5)
  │   ├── from_localid (param_6)  
  │   ├── session_name (param_4)
  │   └── config (param_7)
  │
  ├── FUN_1816f9e50 → 执行查询 (类型转换)
  │
  ├── FUN_1816fa3f0 → 日志序列化 (not result)
  │
  ├── FUN_1816f9e50 → 获取结果列表
  │   └── 返回: linked list of session objects
  │
  └── FUN_18365ac60 → 处理输出
      └── 最终结果 → param_7
```

## 实际输出流

param_2 (RDX) 很可能是 `std::function<void(MessagePageResult&)>` 或类似回调。
真正的输出容器是 `param_7`，通过 `FUN_18365ac60(param_2, &local_458)` 写入。

## 后续 Hook 建议

**最佳 Hook 点：FUN_18365ac60 (offset 0x365ac60)**

参数：
- param_1: 回调 (原始 param_2)
- param_2: 结果结构体指针 (local_458 = *local_80)

在运行时可读结果结构体：
```
local_80 + 0x80 = message_array (指针)
local_80 + 0x88 = message_count (数量)  
```
