#!/usr/bin/env python
"""微信聊天记录恢复工具 v1.0 — GUI 启动入口"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gui.app import ChatApp

if __name__ == '__main__':
    app = ChatApp()
    app.run()
