# 前台窗口诊断工具
import ctypes
from ctypes import wintypes
import time

user32 = ctypes.windll.user32

def get_window_info():
    hwnd = user32.GetForegroundWindow()
    length = user32.GetWindowTextLengthW(hwnd) + 1
    buf = ctypes.create_unicode_buffer(max(length, 1))
    user32.GetWindowTextW(hwnd, buf, max(length, 1))
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return hwnd, buf.value, rect

# 第一步：当前前台窗口
hwnd1, title1, rect1 = get_window_info()
print(f"[1] 当前前台: [{title1}] 0x{hwnd1:x} {rect1.right-rect1.left}x{rect1.bottom-rect1.top}")

# 等待 5 秒，让你点微信
print("[2] 请在 5 秒内点击微信聊天窗口...")
time.sleep(5)

# 第二步：点完之后的前台窗口
hwnd2, title2, rect2 = get_window_info()
print(f"[3] 点击后前台: [{title2}] 0x{hwnd2:x} {rect2.right-rect2.left}x{rect2.bottom-rect2.top}")

# 判断
if "Weixin" in title2 or "微信" in title2 or title2 == "Weixin":
    print("✅ 前台窗口已切换到微信")
else:
    print("⚠ 前台窗口不是微信！可能是终端本身")

# 第三步：发 PageDown（向下翻页，效果更明显）
print("\n[4] 发送 PageDown...")
user32.keybd_event(0x22, 0, 0, 0)
time.sleep(0.05)
user32.keybd_event(0x22, 0, 2, 0)
print("    发送完成")

# 第四步：再等一下看结果
time.sleep(0.5)
hwnd3, title3, rect3 = get_window_info()
print(f"[5] 最终前台: [{title3}] 0x{hwnd3:x}")

# 保存结果到文件
import os
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fg_debug_result.txt")
with open(out, "w", encoding="utf-8") as f:
    f.write(f"1. 当前前台: [{title1}] 0x{hwnd1:x}\n")
    f.write(f"2. 点击后前台: [{title2}] 0x{hwnd2:x}\n")
    f.write(f"3. 最终前台: [{title3}] 0x{hwnd3:x}\n")
print(f"\n结果已保存到: {out}")
