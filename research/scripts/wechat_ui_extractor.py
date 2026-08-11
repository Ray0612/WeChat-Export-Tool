#!/usr/bin/env python
# wechat_ui_extractor.py - 自动导出微信聊天记录
# 坐标扫描 + Tab 键盘导航 双模式
# 依赖: pip install keyboard pyperclip

import ctypes
from ctypes import wintypes
import pyperclip
import keyboard
import time
import os
import re
import hashlib
from datetime import datetime

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "导出结果_UI")
KEY_DELAY = 0.08
SCROLL_DELAY = 1.0
MAX_SCROLLS = 500
DUPLICATE_STOP = 8
ROW_STEP = 30         # 行扫描步进

last_hashes = set()
all_messages = []


def safe_name(name):
    return re.sub(r'[\\/:*?"<>|]', "_", name).strip()[:60] or "unknown"


def find_wechat_window():
    user32 = ctypes.windll.user32
    for cls in ["Qt51514QWindowIcon", "Qt51514QWindowToolSaveBits"]:
        hwnd = user32.FindWindowW(cls, None)
        if hwnd:
            rect = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            if (rect.right - rect.left) > 200:
                return hwnd, rect
    for title in ["Weixin", "微信"]:
        hwnd = user32.FindWindowW(None, title)
        if hwnd:
            rect = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            return hwnd, rect
    return None, None


def click_at_window(hwnd, x, y):
    """发送鼠标点击消息到指定窗口（不移动实际鼠标）"""
    u = ctypes.windll.user32
    # 屏幕坐标 → 窗口客户区坐标
    pt = wintypes.POINT(x, y)
    u.ScreenToClient(hwnd, ctypes.byref(pt))
    lParam = (pt.y << 16) | (pt.x & 0xFFFF)
    # WM_LBUTTONDOWN = 0x0201, WM_LBUTTONUP = 0x0202
    u.PostMessageW(hwnd, 0x0201, 0x0001, lParam)
    time.sleep(0.03)
    u.PostMessageW(hwnd, 0x0202, 0, lParam)
    time.sleep(KEY_DELAY)


def copy_text():
    keyboard.send("ctrl+a")
    time.sleep(KEY_DELAY + 0.05)
    keyboard.send("ctrl+c")
    time.sleep(KEY_DELAY + 0.12)
    try:
        return pyperclip.paste().strip()
    except Exception:
        return ""


def get_message_at(hwnd, x, y, label):
    """点击位置 → 复制 → 去重 → 返回 True/False"""
    click_at_window(hwnd, x, y)
    text = copy_text()
    if not text or len(text) < 2:
        return False
    h = hashlib.md5(text.encode("utf-8")).hexdigest()
    if h in last_hashes:
        return False
    last_hashes.add(h)
    all_messages.append((label, text))
    return True


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("=" * 60)
    print("  微信聊天记录导出")
    print("=" * 60)
    print()

    other_name = input("对方名称: ").strip() or "对方"
    my_name = input("你的名称（如RAY）: ").strip() or "我"

    input(f"\n请打开「{other_name}」的聊天窗口，按 Enter 开始 > ")

    print("\n⏳ 3 秒后开始，不要动鼠标键盘...")
    for i in range(3, 0, -1):
        print(f"  {i}")
        time.sleep(1)

    # 找窗口
    hwnd, rect = find_wechat_window()
    if not hwnd:
        print("❌ 未找到微信窗口")
        return

    win_w = rect.right - rect.left
    win_h = rect.bottom - rect.top
    print(f"\n📐 窗口: {win_w}x{win_h}")

    # 激活窗口（SwitchToThisWindow 不受前台锁限制）
    user32 = ctypes.windll.user32
    user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    SWITCH_TO_THIS = ctypes.WINFUNCTYPE(None, wintypes.HWND, wintypes.BOOL)
    user32.SwitchToThisWindow(hwnd, True)
    time.sleep(0.5)

    # 计算扫描区域
    scan_top = rect.top + 90
    scan_bot = rect.bottom - 200
    scan_h = scan_bot - scan_top

    # 点击聊天区中心聚焦
    cx = rect.left + win_w // 2
    cy = (scan_top + scan_bot) // 2
    click_at_window(hwnd, cx, cy)
    time.sleep(0.3)

    print(f"📐 扫描区 Y={scan_top}→{scan_bot} 步进={ROW_STEP}px")
    print()
    print("=" * 60)
    print("  开始导出 (Ctrl+C 中断)")
    print("=" * 60)
    print()

    scroll_count = 0
    no_new_streak = 0

    while scroll_count < MAX_SCROLLS:
        found_this_page = False

        # 逐行扫描 — 多 X 位置
        for y_off in range(0, scan_h, ROW_STEP):
            y = scan_top + y_off
            win_center = rect.left + win_w // 2

            # X 位置从左到右覆盖整个窗口宽度
            # 45% → 对方消息（左侧聊天区）
            # 55% → 过渡区
            # 65% → 自己消息（右侧聊天区）
            # 80% → 自己消息（更右）
            for ratio, label in [
                (0.42, other_name),
                (0.48, other_name),
                (0.55, my_name),
                (0.65, my_name),
                (0.78, my_name),
            ]:
                x = rect.left + win_w * ratio
                if get_message_at(hwnd, x, y, label):
                    found_this_page = True

        if found_this_page:
            no_new_streak = 0
        else:
            no_new_streak += 1

        if scroll_count % 5 == 0:
            my_c = sum(1 for s, _ in all_messages if s == my_name)
            ot_c = len(all_messages) - my_c
            print(f"  翻页 {scroll_count} | 已捕获 {len(all_messages)} 条 (我:{my_c} {other_name}:{ot_c})")

        if no_new_streak >= DUPLICATE_STOP:
            print(f"\n✅ 已到顶部（连续 {DUPLICATE_STOP} 页无新内容）")
            break

        keyboard.send("page up")
        time.sleep(SCROLL_DELAY)
        scroll_count += 1

    # 保存（反转：最早→最新）
    all_messages.reverse()
    my_c = sum(1 for s, _ in all_messages if s == my_name)
    ot_c = len(all_messages) - my_c

    safe = safe_name(other_name)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(OUTPUT_DIR, f"{safe}_{ts}.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"聊天记录 - {other_name}\n")
        f.write(f"导出: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"共 {len(all_messages)} 条 (我:{my_c} {other_name}:{ot_c})\n")
        f.write("=" * 50 + "\n\n")
        for s, t in all_messages:
            f.write(f"{s}:\n{t}\n\n")

    print(f"\n{'=' * 60}")
    print(f"  ✅ 导出完成!")
    print(f"  📁 {path}")
    print(f"  📊 共 {len(all_messages)} 条 (我:{my_c} {other_name}:{ot_c})")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断")
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
    input("按 Enter 退出...")
