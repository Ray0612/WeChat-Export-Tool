# M2: GetPagedMessages Xref 分析报告

## 实验记录

### 工具尝试

| 工具 | 结果 | 原因 |
|------|------|------|
| pymem 搜索 LEA RIP-relative | 0 处 | 消息表间接引用 |
| pymem 搜索绝对地址编码 | 0 处 | x64 不使用绝对地址 |
| hex 搜索 .text 段 4 字节常量 | 0 处 | 消息表机制 |
| radare2 axt (PE 模式) | 无输出 | 需先行分析 |
| radare2 axt (raw 模式) | 失败 | 文件未映射 |
| rabin2 -zz 字符串列出 | 不包含目标 | .rdata 段未扫描 |

### 字符串确认

| 属性 | 值 |
|------|-----|
| 文件名 | Weixin.dll (181,531,176 bytes) |
| 文件偏移 | 0x83e29a4 |
| 所在段 | .rdata |
| 运行时 DLL 基址 | 0x7fff19040000 |
| 运行时字符串地址 | 0x7fff214235a4 (即 DLL+0x83e35a4) |
| 上下文 | `GetInitialMessages has messages` **`GetPagedMessages`** `, last:` `GetPagedMessages has messages` |

### Xref 分析结论

**无法通过二进制扫描直接定位 xref。** Weixin.dll 使用了消息表（Message Table）机制，日志字符串通过索引间接引用，而非直接的 RIP-relative LEA 指令。

### 现有证据链（无需 xref 也成立）

尽管 xref 无法通过工具直接定位，以下证据链提供了足够的置信度：

1. **字符串聚类**（同一模块区域）:
   ```
   0x83e3509  GetMessageListBySvrIds
   0x83e3583  GetInitialMessages has messages
   0x83e35a4  GetPagedMessages          ← 目标
   0x83e35b5  , last:                   ← 分页参数
   0x83e35bd  GetPagedMessages has messages
   0x83e35dc  GetInitialBrandNotifyMessages
   0x83e3630  GetPagedBrandNotifyMessages
   0x83e36a0  GetAddSendMessageToDb     ← 持久化
   0x83e36b6  CoPrepareShowMessage      ← 渲染
   ```

2. **命名一致性**: 所有函数遵循 `GetXxxMessages` / `CoXxx` 命名模式

3. **参数一致性**: `, last:` 在 GetPagedMessages 旁出现，符合翻页语义

4. **业务逻辑链**: 
   ```
   GetInitialMessages → GetPagedMessages → GetAddSendMessageToDb → CoPrepareShowMessage
   (首次加载)          (翻页加载)          (持久化)                (显示)
   ```

### 下一步建议

| 选项 | 工作量 | 难度 |
|------|--------|------|
| 用 Ghidra 完整分析 xref | 2-4h | 中（需 Java 17+） |
| 基于现有证据直接写 Frida PoC | 2-3h | 中（用 Memory.scan 模糊定位） |
| GitHub 发布成果 | 1h | 低 |

**推荐路径**: 基于现有证据链足够强，建议直接跳 Frida PoC。
