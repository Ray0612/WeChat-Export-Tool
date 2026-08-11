# M112 — 路线 A：vtable 消息对象扫描 + 裸文本提取

> 日期: 2026-06-10
> 微信版本: 4.1.10.29
> PID: 19796
> weixin.dll: 0x7ffa80e00000

---

## 背景

前阶段 (M100-M111) 确认了：
- `CoGetSessionMessageListWithPageFromDB` (weixin.dll+0x360c210) 的完整调用链
- MessagePageResult 结构 (0xA0 bytes, page_size=1000)
- C++ 消息对象结构 (0x80 bytes, +0x28=message_content)
- 21241 个共享 vtable weixin.dll+0x1b4158 的对象

M112 的目标：**通过 vtable 扫描直接从内存提取全量消息**，绕过 SQLCipher 加密。

---

## 尝试 1: vtable 扫描 (失败)

### 方法
扫描 Weixin.exe 的所有私有堆区域 (MEM_PRIVATE, ≥1MB)，寻找 8 字节对齐的 vtable = `weixin.dll+0x1b4158` 的值。

### 结果
- 0 个命中。vtable 偏移 0x1b4158 验证失败 — 该地址处实际是函数体 (`push r14; push r13; ...`)，不是 vtable。
- 交接文档记录的 vtable 地址不正确，实际 vtable 在 `.rdata` 段有 ~109454 个候选。

### 诊断
- weixin.dll 基址: 0x7ffa80e00000
- 目标地址 0x7ffa80fb4158 是代码，不是 vtable
- 最近的 vtable 候选在 weixin.dll+0x81796d0 (距离 134MB)

---

## 尝试 2: weixin.dll .rdata vtable 枚举 (部分成功)

### 方法
在 .rdata 段搜索所有 8 字节指针指向代码段 (weixin.dll base ~ base+0xaf0e000) 的地址，要求连续 3+ 个函数指针。

### 结果
- 找到 301131 个候选，去重后 109454 个唯一 vtable
- 但大部分是函数指针/回调表，不是消息对象 vtable
- 无法从 11 万候选中确定正确的消息对象 vtable

---

## 尝试 3: 中文文本回溯找对象 (失败)

### 方法
1. 在堆中搜索 3+ 连续中文 UTF-8 字符
2. 从文本位置回溯 0x80-0x200 字节找 8 字节对齐的 vtable 指针
3. 验证 vtable → 读 +0x28 的 SSO string

### 结果
**找到 34935 个中文文本**，但回溯找不到 vtable。
文本地址示例:
- 0x01a400053020: "两个小猫猫就喜欢站在路中间呀"
- 0x01a40007b6c1: "上车坐下了就说跟你说一声哦"

---

## 尝试 4: 内存结构分析 (关键发现)

### 方法
dump 文本周围 0x200 字节，分析内存布局。

### 结果
**文本不存在于 C++ 对象中**，而是存在于 WCDB 的 key-value 缓存/序列化记录中。

典型布局:
```
+0x00: 字段名 (如 "14.origin_source", "ress_content")
+0x20: 元数据 (UUID, MD5, 计数器)
+0x40: 字段分隔符 (00 00 01 00)
+0x48: 消息文本 (UTF-8 C 字符串, null 终止)
```

特征:
- 无 vtable 指针 (不是 C++ 对象)
- 文本前后有 UUID、MD5 hash、文件名等
- 类似 LevelDB/WCDB sled 存储格式
- 文本以 null 结尾的 UTF-8 C 字符串存储

---

## 尝试 5: 裸文本提取 (成功 ✅)

### 方法
扫描 0x01a400000000-0x01a600000000 范围，提取所有 3+ 连续中文字符的 C 字符串。

### 结果: 3023 条不重复文本
- **干净文本**: 2126 条 (不含乱码)
- **关联到 wxid**: 227 条 (通过附近 200 字节提取)
- **已知发送者分布**:
  - wxid_caccoealsdbj12 (自己): 98 条
  - wxid_a1n0j4x1gg8i22: 76 条
  - wxid_22e48sxjw2c222: 39 条
  - 其他: 14 条
- **未知发送者**: 2796 条

### 消息示例
```
[wxid_a1n0j4x1gg8i22] 给你了？
[wxid_caccoealsdbj12] 两万应该差不多吧
[wxid_caccoealsdbj12] 点份烧鸭
[wxid_22e48sxjw2c222] 挺好的
[(未知)] 他们很着急想要投入到这个里面
[(未知)] 一件一件解决。你能反思、能听进去我的话，
```

---

## 当前瓶颈

1. **文本不在 C++ 对象中** — 没有 vtable，无法使用对象结构 (+0x28) 提取
2. **缺少元数据** — 2126 条文本中只有 227 条有 wxid，几乎没有时间戳
3. **WCDB 缓存格式未知** — 周围的字段名 (origin_source, ress_content) 提示是 WCDB 内部缓存，但完整记录格式未逆向
4. **SQLCipher key 仍未知** — 数据库能被解密 (缓存中存在数据)，但 key 在 WeChatAppEx 内

---

## 可用的脚本 (scripts/m112_routeA/)

| 脚本 | 功能 |
|------|------|
| scan_messages_A.py | vtable 扫描 (原始方案，当前 0 命中) |
| find_vtable.py | .rdata vtable 候选枚举 |
| find_by_text.py | 中文文本 + 回溯找 vtable |
| find_objects.py / find_objects2.py | 改进版对象搜索 |
| live_monitor.py | 实时内存监控 (1s 间隔轮询) |
| extract_raw_texts.py | ✅ 裸文本成功提取 |
| scan_key.py | WeChatAppEx SQLCipher key 扫描 |
| debug_text.py / dump_text_struct.py | 内存布局调试 |
| scan_heaps.py | 堆区域枚举工具 |

---

## 提取数据位置

```
C:\Users\OK\Desktop\wx_export\
├── raw_texts_1781028614.json        — 3023 条文本 (主输出)
├── live_*.json                      — 实时监控增量保存 (92 个文件)
└── scan_round*.json                 — 早期扫描尝试
```

---

## 后续方向

### 方向 A: 继续裸文本提取
- 长时间运行 live_monitor.py，用户翻所有聊天
- 改进上下文提取算法，扩大 wxid/时间戳捕获率
- 反推 WCDB 缓存记录格式，解析完整结构化数据

### 方向 B: SQLCipher key 扫描 (推荐)
- Key 在 WeChatAppEx 内存中 (flue.dll 上下文)
- 扫描 32/64 字节高熵数据块
- 搜索 "0x" 开头的 hex key 字符串
- 在 sqlite3_key_v2 (flue.dll+0x2a9c805) 附近找参数

### 方向 C: Frida/WinDbg
- 绕过 WeChatAppEx Chromium 沙箱注入 Frida
- Hook sqlite3_key_v2 直接拦截 key
- WinDbg 内核调试断点捕获

---

## M112 Phase 2 — 深入 key 提取 (2026-06-10~11)

### 尝试 6: 批量备份 Buf 文件监控 (成功 ✅)
全量手机→电脑备份期间监控 `temp/phone/Buf` 目录，捕获 **11593 个文件**：
- 5596 JPEG (图片)
- 1793 SILK (语音)
- 893 PNG
- 445 ZIP, 204 PDF, 41 Office, 27 MP4
- 2522 wxgf (微信加密格式)
- **结论: Buf 文件中不包含文本消息，只有媒体附件**

### 尝试 7: 数据库全量写入确认
备份后数据库显著增长：
- `message_0.db`: 84KB → 2.9MB
- `message_1.db`: 3.3MB → **91.9MB** (全量数据)
- `message_2.db`: → 1.5MB
- 文本消息全部在加密数据库中

### 尝试 8: wx_key 工具分析 (结构确认 ✅)
wx_key (ycccccccy/wx_key) 源码分析：

**原理：**
1. 通过 `GetFileVersionInfoW` 获取 Weixin.dll 版本
2. 根据版本选择特征码（signature pattern）
3. 远程扫描目标进程内存匹配特征码
4. 找到后注入 shellcode 远程 hook
5. Shellcode 截获 key 并通过共享内存传递

**版本 4.1.10.29 的特征码匹配：**
```
>4.1.6.14 版本:
24 50 48 C7 45 00 FE FF FF FF 44 89 CF 44 89 C3
49 89 D6 48 89 CE 48 89
```
- ✅ 在 Weixin.dll 中找到匹配（RVA +0x55d0ef）
- 目标函数 offset = -3，即 **RVA +0x55d0f0**
- ❌ `InitializeHook` 调用失败：获取微信版本失败（权限不足 / 中文路径问题）

### 尝试 9: Frida Hook 关键函数 (部分成功)
- Frida 17.10.1 可用，能 attach 到 WeChatAppEx 进程
- 成功设置 `sqlite3_key_v2` (flue.dll+0x2a9c805) 的 hook
- 但 **调用时机已过**：sqlite3_key_v2 在进程启动毫秒级内调用完毕
- CREATE_SUSPENDED 方式：进程暂停时 Weixin.dll 未加载，恢复后 key 已调用
- Child-gating 方式：子进程 hook 正常但主进程（含 Weixin.dll）未捕获

### 当前瓶颈
1. **Key 函数位置已确定** (Weixin.dll + 0x55d0f0) ✅
2. **特征码匹配成功** ✅
3. **但 hook 时机无法提前** — 需在 Weixin.dll 加载前设置 hook
4. **wx_key.dll 调用失败** — 可能因中文路径或权限

### 下一步最佳方案
1. **将 wx_key 项目移至纯英文路径**（如 `C:\tools\wx_key\`）重新尝试
2. **或用管理员身份直接运行 wx_key Flutter 客户端**
3. **或降级微信版本至 wx_key 支持的版本**
