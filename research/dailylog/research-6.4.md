# 微信 4.1.9.56 研究日志 — 2026-06-04

> 第一天：从零开始，全面探索

---

## 上午阶段：环境准备与初步探索

### 读取交接文档
- **内容**：阅读桌面上的 `微信导出工具交接.md` 和已有代码 `wechat_exporter.py`
- **发现**：这是一个针对微信 3.x 的工具，尝试通过 pymem 读内存提取 SQLCipher 密钥 → 解密 MSG.db
- **问题**：用户的微信是 4.1.9.56，架构完全不同

### 环境检查
- 确认 Python 3.13.5 已安装
- 依赖已齐全：pymem 1.14.0, pycryptodome 3.23.0, fpdf2 2.8.7

### 运行原有工具 — 失败
- **步骤**：以管理员身份运行 `run_export.bat`
- **结果**：能附加到 Weixin.exe 进程，但找不到核心模块 `WeChatWin.dll`
- **原因**：微信 4.x 的核心 DLL 是 `Weixin.dll`（181MB），不是 3.x 的 `WeChatWin.dll`

### 问题1：批处理编码错误
- **现象**：命令行输出乱码 `'tle' 不是内部或外部命令`
- **原因**：bat 文件 UTF-8 编码在 Windows CMD 中显示为乱码
- **修复**：改为 GBK 编码或纯 ASCII 内容

### 问题2：扫错模块
- **现象**：找不到 `WeChatWin.dll`
- **分析**：`find_wechat_module()` 匹配到了 `Weixin.exe`（3MB）而非 `Weixin.dll`（181MB）
- **修复**：修改模块查找优先级，精确匹配 `weixin.dll`

### 第一次密钥提取尝试
- **方法**：搜索 `SetDBKey` 字符串（ASCII + UTF-16LE）
- **结果**：在 173MB 的 Weixin.dll 中未找到
- **分析**：字符串可能在运行时动态构造或函数名被 strip

### 第二次密钥提取尝试
- **方法**：搜索 `applet.db`、`radium\users` 等 V4 路径特征，在附近偏移读 32 字节密钥
- **结果**：找到路径字符串但附近无有效密钥

### 第三次密钥提取尝试
- **方法**：全进程内存搜索 `x'<64hex>'` 格式（GPT 建议的 SQLCipher PRAGMA 格式）
- **结果**：使用 VirtualQueryEx + ReadProcessMemory 在堆内存中搜索，未找到

### 第四次密钥提取尝试
- **方法**：全内存 32 字节高熵数据扫描
- **结果**：扫描了所有可读内存页，未找到有效密钥

---

## 下午阶段：UI 自动化尝试

### GPT 第一次指导
- **建议**：放弃 SendInput，尝试鼠标滚轮（大增量）、拖拽滚动条、拖拽聊天内容
- **内容**：微信 4.x 的 Chromium WebView 拦截所有程序化输入

### 尝试1：pyautogui 大滚轮
- **方法**：`pyautogui.scroll(2400)`
- **结果**：微信窗口内无效（CMD 终端内有效）

### 尝试2：pyautogui 连续滚轮 50 次
- **方法**：`pyautogui.scroll(120) × 50`
- **结果**：无效

### 尝试3：pyautogui 拖拽滚动条
- **方法**：`mouseDown` + `moveTo` + `mouseUp` 在滚动条位置
- **结果**：无效

### 尝试4：拖拽聊天内容
- **方法**：`pyautogui.drag(0, -300)` 模拟触屏下拉
- **结果**：无效

### 尝试5：硬件扫描码 SendInput
- **方法**：`KEYEVENTF_SCANCODE | KEYEVENTF_EXTENDEDKEY`，扫描码 0x49
- **结果**：无效

### 尝试6：VBScript SendKeys
- **方法**：`WshShell.SendKeys "{PGUP}"` 通过 Windows Script Host
- **结果**：无效

### 尝试7：PowerShell SendKeys
- **方法**：`[System.Windows.Forms.SendKeys]::SendWait("{PGUP}")`
- **结果**：无效

### 尝试8：C# 原生 EXE SendInput
- **方法**：编译 C# 程序用 P/Invoke 调用 SendInput，先 SetForegroundWindow
- **结果**：无效

### 尝试9：前台窗口诊断
- **步骤**：`GetForegroundWindow` 确认前台是微信窗口（0x5a0e2e, 651x758）
- **结论**：按键确实发到了微信，但被拦截

---

## 傍晚阶段：数据库解密尝试

### ZedeX/weixin-decrypte-script
- **步骤**：克隆仓库 → 安装依赖 → 运行 `scan_keys.py`
- **结果**：成功提取到 21 个候选密钥，最高频出现 18 次
- **后续**：运行 `decrypt_db.py --auto`，13 个数据库全部解密失败
- **分析**：工具的数据目录结构与用户的实际目录不匹配

### chatlog (sjzar/chatlog) v0.0.31
- **步骤**：`go install github.com/sjzar/chatlog@latest`（通过 goproxy.cn）
- **密钥验证**：`chatlog server -k <key> -p windows -v 4` → 服务器启动成功，`{"status":"ok"}`
- **重要发现**：chatlog 接受密钥！说明密钥是正确的
- **解密结果**：`decrypt data success` 但 `unsupported platform: v4`
- **分析**：chatlog 的 V4 DataSource 尚未完整实现

---

## 晚间阶段：截图 + OCR 方案

### 截图工具开发
- **思路**：截取屏幕右半边 → OCR 识别文字 → 自动翻页
- **遇到问题**：
  - 窗口定位错误（FindWindowW 返回最小化窗口）
  - 屏幕尺寸不匹配（GetSystemMetrics 返回虚拟桌面尺寸 1280×800 而非实际 2560×1600）
  - 需要管理员权限运行（拦截 SendInput）
  - 控制台窗口遮挡截图区域

### OCR 配置
- 安装 Tesseract 5.4 + 中文语言包 `chi_sim`
- 设置 `TESSDATA_PREFIX` 环境变量
- 确认中英文 OCR 均可使用

### 紧凑结构发现（关键突破）
- **方法**：搜索 `1b 02 05 09 01 01 04` 前缀
- **发现**：34 字节固定步长的消息数组，倒序排列
- **验证**：HELLO_1-5 全部在缓存中，sequence 从 331-335 逐条 +1

---

## 第一日总结

| 方向 | 结果 |
|------|------|
| 数据库解密 | ❌ 密钥正确但解密算法不匹配 |
| 截图+OCR | ❌ 自动翻页被拦截 |
| UI 自动化 | ❌ 所有 19 种翻页方法全部失败 |
| 紧凑结构发现 | ✅ 34 字节消息缓存 |
| **关键结论** | 聊天消息在 Weixin.exe 内存中 |

---

## 文件产出

- `wechat_exporter.py` — 数据库解密版（修正模块查找）
- `wechat_screenshot_extractor.py` — 截图 + OCR 版
- `wechat_ui_extractor.py` — UI 自动化版（已放弃）
- `scroll_test.py` — GPT 建议方案测试
- `weixin-decrypte-script/` — ZedeX 工具（密钥提取成功）
- `found_keys.txt` — 21 个候选密钥
- `开发记录.md` — 完整失败记录
- `开发全记录.md` — 项目完整记录
