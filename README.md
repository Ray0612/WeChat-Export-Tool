# WeChat Export Tool

微信聊天记录导出工具，支持按联系人浏览和导出聊天记录。

## 功能

- 解密微信本地数据库，读取聊天记录
- 按联系人查看历史消息
- 导出聊天记录
- 支持微信 4.1.10.29 版本

## 使用

从 [Releases](https://github.com/Ray0612/WeChat-Export-Tool/releases) 下载最新版本，解压后：

1. 双击 `启动工具.bat` 或 `WeChatExport.exe`
2. 点击 **"🔑 获取密钥"** — 会提示关闭微信，关掉后它会自动捕获解密密钥
3. 密钥获取成功后，点击 **"🗄️ 连接数据库"**
4. 连接成功后再点 **"📤 浏览会话"** — 即可查看所有聊天记录

> 详细操作步骤见[使用教程]()

### 源码运行

```bash
pip install -r requirements.txt
python run_gui.py
```

## 构建

```bash
python build_dist.py
```

## 技术栈

- Python 3.13 — 后端解密与导出
- Electron — GUI 界面
- WCDB — 微信数据库解密

## 许可证

GPL v3

## 相关

- 研究仓库: [WeChat-v4-export-research](https://github.com/Ray0612/WeChat-v4-export-research)
- 国内的朋友可以访问我的博客网站使用[github高速下载工具](https://blog.ray2.asia/tools/download-relay/)，将这个(release)网址复制进来高速下载 [Releases v1.1](https://github.com/Ray0612/WeChat-Export-Tool/releases)

## ToDoList

- 现在正在着手开发QQ聊天记录导出的开源工具，为之后充实语料库做基础，后续会把两个工具的仓库合并
- v1.2 支持多种类型的消息的导出
- v1.3 更美观的gui，更轻量的release

## v1.1

- 新增导出格式：PDF，CSV，Excel，HTML（最美观，支持搜索）
- 修复启动时检测企业微信作为微信进程的bug
- 修复关闭程序时临时文件清理不完全
- 修复txt格式中时间戳显示错误

## v1.0.0

- 支持本地导出微信聊天记录
- 支持导出文字聊天记录
- 支持以txt和json格式导出
- 支持搜索联系人指定会话导出
