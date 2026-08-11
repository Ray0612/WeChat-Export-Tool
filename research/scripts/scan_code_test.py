# 硬件扫描码模式测试（最后一个方法）
# 用 KEYEVENTF_SCANCODE 替代虚拟键码，绕过 Chromium 的输入检测
import ctypes, time
from ctypes import wintypes

user32 = ctypes.windll.user32

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [('wVk', wintypes.WORD), ('wScan', wintypes.WORD),
                 ('dwFlags', wintypes.DWORD), ('time', wintypes.DWORD),
                 ('dwExtraInfo', ctypes.c_ulonglong)]

class INPUT_UNION(ctypes.Union):
    _fields_ = [('ki', KEYBDINPUT)]

class INPUT(ctypes.Structure):
    _fields_ = [('type', wintypes.DWORD), ('u', INPUT_UNION)]

INPUT_KEYBOARD = 1
KEYEVENTF_SCANCODE = 0x0008
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002

print('倒计时期间请点击微信聊天窗口')
for i in range(3, 0, -1):
    print(f'  {i}...')
    time.sleep(1)

print('发送 PageUp（硬件扫描码）...')

kd = INPUT(INPUT_KEYBOARD, INPUT_UNION(ki=KEYBDINPUT(
    0, 0x49, KEYEVENTF_SCANCODE | KEYEVENTF_EXTENDEDKEY, 0, 0)))
ku = INPUT(INPUT_KEYBOARD, INPUT_UNION(ki=KEYBDINPUT(
    0, 0x49, KEYEVENTF_SCANCODE | KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP, 0, 0)))

for _ in range(5):
    user32.SendInput(1, ctypes.byref(kd), ctypes.sizeof(INPUT))
    time.sleep(0.03)
    user32.SendInput(1, ctypes.byref(ku), ctypes.sizeof(INPUT))
    time.sleep(0.05)

print('完成')
