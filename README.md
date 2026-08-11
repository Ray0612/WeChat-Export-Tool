# 微信聊天记录本地导出工具 v1.2.0

Windows 微信聊天记录本地导出工具。双击即用，提取密钥 → 解密数据库 → 导出聊天记录。

> **研究资料** 见 [`research/README.md`](research/README.md) · **发布说明** 见 [`RELEASE.md`](RELEASE.md)

---

## 功能

- ✅ 一键提取微信数据库密钥（自动识别 / 手动粘贴）
- ✅ 密钥持久化，下次启动自动加载
- ✅ 浏览会话列表（支持搜索过滤）
- ✅ 查看聊天记录（文字/图片/语音/表情等类型占位符）
- ✅ 多种导出格式：**HTML / PDF / TXT / JSON / CSV / Excel**
- ✅ HTML 导出：独立文件夹 + `图片/` 子目录
- ✅ 图片解密导出
- ✅ 日志记录系统
- ✅ 导出进度窗口（后台线程，不卡界面）

## 快速开始

```bash
# 开发模式
python gui/app_v3.py

# 构建发布包
python build_dist.py
# 输出: dist/WeChatExport/ (双击 WeChatExport.exe 或 启动工具.bat)
```

### 使用流程

1. 设置 **微信数据目录**（`xwechat_files` 所在位置）
2. 设置 **导出工作目录**（导出文件存放位置，自动创建 `WeChat/` 子目录）
3. **获取密钥**（或手动粘贴已有 64 位密钥）
4. **连接数据库**
5. **浏览会话** → 选会话 → 查看消息 → 选格式 → **导出**

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

## 版本历史

- **v1.0** (2026-06-11): 文字消息导出
- **v1.2.0** (2026-07-15): 图片解密导出、多格式导出、日志系统、密钥持久化
