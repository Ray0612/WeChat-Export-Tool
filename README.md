# 微信聊天记录本地导出工具 v1.2.0

Windows 微信聊天记录本地导出工具。双击即用，提取密钥 → 解密数据库 → 导出聊天记录。

> **研究资料** 见 [`research/README.md`](research/README.md) · **发布说明** 见 [`RELEASE.md`](RELEASE.md)

---

## 功能

- 解密微信本地数据库，读取聊天记录
- 按联系人查看历史消息
- 一键提取微信数据库密钥（自动识别 / 手动粘贴），密钥自动持久化
- 多种导出格式：**HTML / PDF / TXT / JSON / CSV / Excel**
- HTML 导出生成独立文件夹 + `图片/` 子目录
- 图片解密导出（支持 HTML、PDF 格式）
- 日志记录系统（崩溃、图片处理、导出操作）
- 导出进度窗口（后台线程，不卡界面）
- 支持微信 4.X 版本

## 使用

从 [Releases](https://github.com/Ray0612/WeChat-Export-Tool/releases) 下载最新版本，解压后：

1. 双击 `启动工具.bat` 或 `WeChatExport.exe`
2. 设置微信数据库位置和工具工作目录
3. 点击 **"🔑 获取密钥"** — 会提示关闭微信，关掉后它会自动捕获解密密钥（如果有密钥则可直接粘贴）
4. 密钥获取成功后，点击 **"🗄️ 连接数据库"**
5. 连接成功后再点 **"📤 浏览会话"** — 即可查看所有聊天记录
6. 导出对应格式

> 国内的朋友可以访问我的博客网站使用 [github高速下载工具](https://blog.ray2.asia/tools/download-relay/)，将这个（release）网址复制进来高速下载 [Releases v1.2.0](https://github.com/Ray0612/WeChat-Export-Tool/releases)

### 源码运行

```bash
pip install -r requirements.txt
python gui/app_v3.py
```

## 项目结构

```
wechat_export_project/
├── gui/
│   ├── app_v3.py              ← 主 GUI 程序 (tkinter)
│   └── icon.ico               ← 窗口图标
├── scripts/
│   ├── get_key.js              ← 密钥提取 (Node.js + koffi + wx_key.dll)
│   ├── wcdb_server.js          ← WCDB HTTP 服务 (Node.js + Electron)
│   ├── wcdb_server.py          ← WCDB 客户端 (Python)
│   ├── decrypt_image.js        ← 图片解密助手
│   └── node_modules/           ← Node.js 依赖
├── exporters/
│   ├── html_exporter.py        ← HTML 导出
│   ├── pdf_exporter.py         ← PDF 导出
│   ├── csv_exporter.py         ← CSV 导出
│   ├── excel_exporter.py       ← Excel 导出
│   ├── image_decoder.py        ← .dat 图片解密
│   ├── media_resolver.py       ← 图片解析编排器
│   ├── packed_info_parser.py   ← 图片信息提取
│   └── logger.py               ← 日志系统
├── build_dist.py               ← 打包脚本
└── APP/WeChatExport/           ← 发布包
```

## 技术方案

- **密钥提取**: `wx_key.dll` (MIT) Hook `SetDBKey` 捕获 SQLCipher 密钥
- **数据库解密**: WCDB 框架 (BSD) 通过 Electron 解密 SQLite 数据库
- **图片解密**: 从 `wx_key.dll` 获取 code → 推导 AES key → 原生模块解密 `.dat` → ffmpeg 转码 HEVC
- **导出**: 多种格式，HTML 独立图片文件夹

## 依赖

| 组件 | 许可证 | 用途 |
|------|--------|------|
| wx_key.dll | MIT | 微信内存密钥提取 |
| WCDB.dll | BSD 3-Clause | 数据库解密 |
| Electron | MIT | WCDB 运行时 |
| koffi | MIT | Node.js FFI |
| fzstd | MIT | ZSTD 解压 |
| ffmpeg | GPL | HEVC→JPG 转码 |
| fpdf2 | LGPL | PDF 生成 |
| openpyxl | MIT | Excel 生成 |

## Roadmap

- 正在着手开发 QQ 聊天记录导出的开源工具，后续会把两个工具的仓库合并
- v1.2.X 支持多种类型的消息导出（图片✅ 表情❌ 表情包❌ 视频❌ 语音❌）
- v1.3 更美观的 GUI，更轻量的 release
- v1.4 使用 AI 对多种类型的消息进行读取，提取描述文字作为纯文本大模型的语料，支持纯文本数据库的导出

## 版本历史

- **v1.0** (2026-06-11): 文字消息导出
- **v1.2.0** (2026-07-15): 图片解密导出、多格式导出、日志系统、密钥持久化
