# 翻页测试工具 — GPT 建议的 3 种新方法
# 运行前：打开微信聊天窗口（双击联系人）
# 倒计时期间：点一下微信聊天窗口

import ctypes
from ctypes import wintypes
import pyautogui
import time

pyautogui.FAILSAFE = False
user32 = ctypes.windll.user32

def move_mouse(x, y):
    user32.SetCursorPos(x, y)
    time.sleep(0.1)
    pt = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    print(f"    鼠标: ({pt.x}, {pt.y}){' ✓' if abs(pt.x-x)<10 and abs(pt.y-y)<10 else ' ✗'}", end="")
    print()

print("打开微信聊天窗口（双击联系人），然后放在屏幕右边。")
print()
input("准备好了按 Enter 进入倒计时 > ")

# 倒计时 — 期间点微信
print("\n倒计时，请点击微信聊天窗口...")
for i in range(3, 0, -1):
    print(f"  {i}")
    time.sleep(1)

# 枚举所有可见窗口，找屏幕右边的那个（你的聊天窗口）
candidates = []
def enum_fn(h, _):
    if user32.IsWindowVisible(h):
        length = user32.GetWindowTextLengthW(h) + 1
        buf = ctypes.create_unicode_buffer(max(length, 1))
        user32.GetWindowTextW(h, buf, max(length, 1))
        title = buf.value
        if not title:
            return True
        rect = wintypes.RECT()
        user32.GetWindowRect(h, ctypes.byref(rect))
        w = rect.right - rect.left
        h_val = rect.bottom - rect.top
        # 排除小窗口(<200px)、最小化窗口(<0)、系统窗口
        if w < 200 or h_val < 200 or rect.left < 0:
            return True
        # 排除已知非微信窗口
        skip_words = ["Program Manager", "Windows 输入", "设置", "Nahimic", "cmd.exe",
                       "CASCADIA", "ConsoleWindowClass", "python"]
        if any(s in title for s in skip_words):
            return True
        # 只取屏幕右半边的窗口（你的微信聊天窗口）
        if rect.left >= 800:  # 在屏幕右侧
            candidates.append((w * h_val, h, rect, title[:20]))
    return True

user32.EnumWindows(ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)(enum_fn), 0)

if not candidates:
    print("❌ 没找到屏幕右边的窗口，请把微信窗口放到右边")
    exit()

# 取最大的
candidates.sort(key=lambda x: x[0], reverse=True)
_, hwnd, rect, title = candidates[0]
w, h = rect.right - rect.left, rect.bottom - rect.top
print(f"\n找到: 0x{hwnd:x} \"{title}\" {w}x{h} @ ({rect.left},{rect.top})")

# 聊天区（独立窗口没有侧边栏，全宽都是聊天区）
chat_mid_x = (rect.left + rect.right) // 2
chat_mid_y = rect.top + int(h * 0.4)
print(f"目标位置: ({chat_mid_x}, {chat_mid_y})")

# ===== 测试开始 =====
print("\n开始测试，不要动鼠标键盘...")

# 方法1: 大增量鼠标滚轮
print("\n[1] 大滚轮(2400)...")
move_mouse(chat_mid_x, chat_mid_y)
time.sleep(0.2)
pyautogui.scroll(2400)
time.sleep(1.5)
print("  ✅")

# 方法2: 连续小滚轮×50
print("\n[2] 连续滚轮×50...")
move_mouse(chat_mid_x, chat_mid_y)
time.sleep(0.2)
for _ in range(50):
    pyautogui.scroll(120)
    time.sleep(0.01)
time.sleep(1.5)
print("  ✅")

# 方法3: 拖滚动条
print("\n[3] 拖滚动条...")
scroll_x = rect.right - 15
move_mouse(scroll_x, chat_mid_y + 100)
time.sleep(0.2)
pyautogui.mouseDown()
time.sleep(0.05)
pyautogui.moveTo(scroll_x, chat_mid_y - 100, duration=0.3)
time.sleep(0.05)
pyautogui.mouseUp()
time.sleep(1.5)
print("  ✅")

# 方法4: 拖聊天内容（上拖=加载更早消息）
print("\n[4] 拖聊天内容...")
move_mouse(chat_mid_x, chat_mid_y)
time.sleep(0.2)
pyautogui.drag(0, -200, duration=0.3, button='left')
time.sleep(1.5)
print("  ✅")

# 方法5: 大滚轮×2
print("\n[5] 大滚轮(4800)...")
move_mouse(chat_mid_x, chat_mid_y)
time.sleep(0.2)
pyautogui.scroll(4800)
time.sleep(1)
print("  ✅")

print("\n全部完成！哪些方法翻页了？")
