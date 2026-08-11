# 微信聊天记录本地导出工具 — 项目文档

> 版本: v1.2.0
> 最后更新: 2026-07-15
> 微信版本: 4.x

---

## 项目概述

Windows 微信聊天记录导出工具。双击即用，提取密钥 → 解密数据库 → 导出聊天记录。

**核心链路：**
1. `wx_key.dll` 从微信进程内存提取 SQLCipher 密钥（自动/手动）
2. `WCDB.dll` 解密 SQLite 数据库
3. Python tkinter GUI 展示会话和消息，支持多种格式导出
4. 图片通过本地原生模块解密并嵌入导出文件

---

## 项目结构

```
wechat_export_project/
├── gui/
│   ├── app_v3.py              ← 主 GUI 程序 (tkinter)
│   └── icon.ico               ← 窗口图标
├── scripts/
│   ├── get_key.js              ← 密钥提取 (Node.js + koffi + wx_key.dll)
│   ├── wcdb_server.js          ← WCDB HTTP 服务 (Node.js + Electron + WCDB.dll)
│   ├── wcdb_server.py          ← WCDB 客户端 (Python)
│   ├── decrypt_image.js        ← 图片解密助手 (原生模块 + ffmpeg)
│   └── node_modules/           ← Node.js 依赖 (koffi, fzstd)
├── exporters/
│   ├── html_exporter.py        ← HTML 导出（支持图片文件夹）
│   ├── pdf_exporter.py         ← PDF 导出
│   ├── csv_exporter.py         ← CSV 导出
│   ├── excel_exporter.py       ← Excel 导出
│   ├── image_decoder.py        ← .dat 图片解密 (V3 XOR / V4 AES+XOR)
│   ├── media_resolver.py       ← 图片解析编排器
│   ├── packed_info_parser.py   ← 图片信息提取
│   └── logger.py               ← 日志记录系统
├── resources/
│   ├── native/                 ← Rust 原生解密模块
│   └── bin/                    ← ffmpeg (HEVC→JPG)
├── build_dist.py               ← 打包脚本
└── APP/WeChatExport/           ← 发布包 (双击 WeChatExport.exe)
```

---

## 功能

### v1.2.0
- ✅ 一键提取微信数据库密钥（自动识别 / 手动粘贴）
- ✅ 密钥持久化，下次启动自动加载
- ✅ 浏览会话列表（支持搜索过滤）
- ✅ 查看聊天记录（文字/图片/语音/表情等类型占位符）
- ✅ 多种导出格式：HTML / PDF / TXT / JSON / CSV / Excel
- ✅ HTML 导出：生成独立文件夹 + `图片/` 子目录，图片单独保存
- ✅ 图片解密导出（缩略图 + 完整图）
- ✅ 昵称映射、时间格式化、左右气泡
- ✅ 日志记录系统（导出/错误/崩溃日志写入 txt）
- ✅ 导出进度窗口（后台线程，不卡界面）

---

## 构建和运行

```bash
# 构建发布包
python build_dist.py
# 输出: dist/WeChatExport/ (双击 WeChatExport.exe)

# 开发模式
python gui/app_v3.py
```

---

## 依赖的开源组件

| 组件 | 许可证 | 用途 |
|------|--------|------|
| wx_key.dll | MIT | 微信内存密钥提取 |
| WCDB.dll | BSD 3-Clause | 数据库解密 |
| SDL2.dll | zlib | WCDB 依赖 |
| Electron | MIT | WCDB 运行时 |
| koffi | MIT | Node.js FFI 库 |
| fzstd | MIT | ZSTD 解压 |
| PyInstaller | GPL 2.0 | Python 打包 |
| ffmpeg | GPL | HEVC→JPG 图片转码 |
| fpdf2 | LGPL | PDF 生成 |
| openpyxl | MIT | Excel 生成 |

---

## 版本历史

- **v1.0** (2026-06-11): 首次发布。支持密钥提取、文字消息查看和导出。
- **v1.1**: 修复若干 bug。
- **v1.2.0** (2026-07-15): 图片解密导出、多格式导出、日志系统、密钥持久化、导出进度窗口。
