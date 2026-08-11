# -*- coding: utf-8 -*-
"""日志记录系统 — 写入 txt 文件，同时支持控制台输出"""
import os, datetime, traceback, sys

_LOG_FILE = None
_LOG_TO_CONSOLE = False


def init(log_dir: str):
    """初始化日志文件，在 log_dir 下创建 logs/ 目录"""
    global _LOG_FILE
    try:
        log_path = os.path.join(log_dir, 'logs')
        os.makedirs(log_path, exist_ok=True)
        ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        _LOG_FILE = os.path.join(log_path, f'export_{ts}.log')
        # 写入头部
        with open(_LOG_FILE, 'w', encoding='utf-8') as f:
            f.write(f"=== 微信导出工具 日志 {ts} ===\n")
            f.write(f"Python: {sys.version}\n\n")
        info("日志系统初始化", f"日志文件: {_LOG_FILE}")
    except Exception as e:
        _LOG_FILE = None
        print(f"[日志初始化失败] {e}")


def info(tag: str, msg: str = ''):
    """记录 info 级别日志"""
    _write('INFO', tag, msg)


def error(tag: str, msg: str = ''):
    """记录 error 级别日志"""
    _write('ERROR', tag, msg)


def _write(level: str, tag: str, msg: str):
    global _LOG_FILE
    ts = datetime.datetime.now().strftime('%H:%M:%S')
    line = f"[{ts}] [{level}] [{tag}] {msg}\n"
    # 写入文件
    if _LOG_FILE:
        try:
            with open(_LOG_FILE, 'a', encoding='utf-8') as f:
                f.write(line)
        except:
            pass
    # 控制台
    if _LOG_TO_CONSOLE:
        print(line.rstrip())


def except_hook(exc_type, exc_value, exc_tb):
    """全局未捕获异常钩子"""
    if exc_type is KeyboardInterrupt:
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return
    tb = ''.join(traceback.format_exception(exc_type, exc_value, exc_tb))
    _write('FATAL', '未捕获异常', tb[:2000])
    # 也崩溃到控制台
    sys.__excepthook__(exc_type, exc_value, exc_tb)


def get_log_path() -> str:
    return _LOG_FILE or ''
