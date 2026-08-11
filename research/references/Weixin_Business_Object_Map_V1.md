# Weixin.dll Business Object Map V1

## 概述

通过字符串普查和 Qt 元对象搜索建立的微信 4.1.9.56 业务对象地图。

**方法：** 在 Weixin.dll 进程内存中搜索业务关键字，提取附近可读字符串。
**局限：** 未使用 IDA/Ghidra 反汇编，基于字符串指纹和 Qt 运行时类型信息推断。

---

## 核心架构发现

### 1. 消息加载链路（最完整）

通过 `MessageList` 附近的调试字符串还原：

```
GetSessionMessageList        → 获取某会话的消息列表
GetInitialMessages           → 首次打开会话时加载初始消息
GetPagedMessages             → **分页加载更早的历史消息** ← 关键 API
GetMessageListBySvrIds       → 按服务器 ID 拉取消息
GetInitialBrandNotifyMessages → 服务号通知消息加载

GetPagedMessages has messages:
GetInitialMessages has messages:
GetSessionMessageList for:
MessageListBySvrIds for
```

**`GetPagedMessages` 是我们需要的翻页接口。** 它在 Weixin.dll 中，是 Cocos/AppMsg 模块的一部分。

### 2. 消息持久化链路

```
MessageListToDB                  → 写入数据库
AddMessageListToDB               → 追加写入
CoBatchUpdateMessagesWithBitSetToDB → 批量更新
CoBatchUpdateMessagesWithTypeToDB   → 按类型批量更新
CoQueryMessageBySvrId           → 按服务器 ID 查询
```

这些函数可能对应未公开的本地缓存机制。消息不仅存在内存，也有可能写入了一个非标准格式的本地文件。

### 3. 会话管理

```
SessionList:
  GetMessageSessionList ret size:  → 获取消息会话列表
  SessionListDelegate              → 会话列表代理
  SearchContentPopoverDelegate     → 搜索弹窗
```

### 4. UI 渲染架构

`ChatView` 相关：
```
ChatViewModelOwner    → 聊天 ViewModel（MVVM 模式）
ChatTextViewHost      → 文本视图宿主
RecyclerListTextSelectionHelper  → RecyclerView 文本选择
```

这套架构类似 Android RecyclerView + Qt Model/View 的混合体。`RecyclerList` 控件管理消息列表的虚拟滚动。

### 5. mmui 类体系

`mmui::` 命名空间下有完整的 UI 组件体系，属于微信自定义的 Qt UI 框架：

```
mmui::ContactsManagerHBoxlayoutClickArea  → 联系人管理器
mmui::ChatStickyFoldButton                → 聊天折叠按钮
mmui::UnreadBarView                       → 未读条
mmui::ContactHeadView                     → 联系人头像
mmui::XImage / XPlayerView                → 图片/视频播放
mmui::TitleBar / SNSWindowToolBar         → 窗口管理
```

### 6. 消息缓存

```
MsgCache → micromsg.AppMsgContext → micromsg.App
```

存在一个 `MsgCache` 缓存模块，属于 `AppMsg` 子系统。

---

## 业务对象关系图（推测）

```
AppMsg 子系统 (micromsg.AppMsgContext)
   │
   ├── MsgCache
   │
   ├── MessageList
   │     ├── GetSessionMessageList(talker) → 初始消息
   │     ├── GetPagedMessages(talker, page) → 分页历史消息
   │     └── GetMessageListBySvrIds(ids) → 按ID拉取
   │
   ├── MessageListToDB (持久化)
   │
   ├── SessionList
   │     └── GetMessageSessionList → 会话列表
   │
   └── ChatView (UI层)
         ├── ChatViewModelOwner
         ├── RecyclerList
         └── ChatTextViewHost
```

---

## 导出器挂钩建议

基于发现的函数名，未来导出器的最可靠路径：

**路径A：挂钩分页加载 API（推荐）**

```
GetPagedMessages 是翻页加载历史消息的函数。
如果能在 Weixin.dll 中定位该函数的地址，
可以通过 Frida hook 拦截每一次历史消息加载。

拦截到的消息数据可能以 ProtoBuf 格式返回，
从而获得完整的消息对象（含 content, timestamp, receiver 等）
不需要解析紧凑结构。
```

**路径B：扫描紧凑结构缓存（可行）**

```
search_prefix(1b 02 05 09 01 01 04)
→ 遍历 34B 步长
→ 提取 content + sequence + session_tag
→ 通过记录区关联 receiver
```

**路径C：利用 `MessageListToDB` 寻找本地存储（需验证）**

```
GetMessageListToDB 表明消息被写入本地存储。
如果存在本地缓存文件，
其格式可能是 ProtoBuf 序列化的消息列表。
```

---

## 关键 API 地址清单

| API 名称 | DLL 偏移 | 发现方式 |
|----------|---------|----------|
| GetPagedMessages | ~0x8333e50 | 字符串调用上下文 |
| GetInitialMessages | ~0x8333e50 | 同上 |
| GetSessionMessageList | ~0x8333f56 | 同上 |
| MessageListToDB | ~0x87832e3 | 字符串上下文 |
| MsgCache | ~0x84738b4 | 字符串匹配 |
| mmui 类列表 | ~0x80c5a58 | 运行时类型信息 |
| chatmsg proto 字段 | ~0x820647c | Protobuf 定义 |

**注意：** 这些偏移是静态字符串地址，不是函数入口。函数入口需要通过 IDA/Ghidra 交叉引用定位。
