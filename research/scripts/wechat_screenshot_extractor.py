#!/usr/bin/env python
# wechat_screenshot_extractor.py - 截图+OCR 导出微信聊天记录
# 依赖: pip install pillow pytesseract
# 需要: Tesseract OCR (已安装)

import time
import os
import re
import hashlib
import subprocess
import ctypes
from ctypes import wintypes
from datetime import datetime
from PIL import Image, ImageGrab

# 检查是否以管理员身份运行（管理员权限会阻止 SendInput 发送给非管理员程序）
try:
    is_admin = ctypes.windll.shell32.IsUserAnAdmin()
    if is_admin:
        print("  ⚠ 检测到以管理员身份运行！")
        print("  管理员权限会阻止 SendInput 发送按键到普通权限的微信")
        print("  请关闭窗口，以普通用户身份重新运行")
        print("  或直接双击 wechat_screenshot_extractor.py")
        print()
except Exception:
    pass

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "导出结果_截图")
SCROLL_DELAY = 1.2
MAX_SCROLLS = 500
DUPLICATE_STOP = 2   # 连续2张重复就停
TASKBAR_H = 50       # 底部任务栏高度(px)
BOTTOM_CROP = 70     # 底部额外裁剪(输入框等)

# OCR 初始化
OCR_AVAILABLE = False
try:
    import pytesseract
    for p in [r"C:\Program Files\Tesseract-OCR\tesseract.exe"]:
        if os.path.exists(p):
            pytesseract.pytesseract.tesseract_cmd = p
            break
    user_tess = os.path.join(os.environ.get("USERPROFILE", "C:"), "AppData", "Local", "tessdata")
    os.environ["TESSDATA_PREFIX"] = user_tess
    ver = pytesseract.get_tesseract_version()
    langs = pytesseract.get_languages()
    has_cn = "chi_sim" in langs
    OCR_AVAILABLE = has_cn
    print(f"  ✅ Tesseract: {ver}")
    print(f"  📚 语言包: {langs} {'✅' if has_cn else '❌ chi_sim缺失，中文OCR不可用'}")
except Exception as e:
    print(f"  ⚠ OCR 不可用: {e}")

all_messages = []


def safe_name(name):
    return re.sub(r'[\\/:*?"<>|]', "_", name).strip()[:60] or "unknown"


def find_chat_window():
    """找到微信独立聊天窗口（小窗口 300~700px）"""
    results = []
    def enum_proc(hwnd, _):
        if ctypes.windll.user32.IsWindowVisible(hwnd):
            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd) + 1
            tb = ctypes.create_unicode_buffer(max(length, 1))
            ctypes.windll.user32.GetWindowTextW(hwnd, tb, max(length, 1))
            if tb.value == "Weixin":
                rect = wintypes.RECT()
                ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
                w = rect.right - rect.left
                h = rect.bottom - rect.top
                if 300 < w < 700 and 300 < h < 700:
                    results.append(hwnd)
        return True

    ctypes.windll.user32.EnumWindows(
        ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)(enum_proc), 0
    )
    return results[0] if results else None


def find_render_window(main_hwnd):
    """找到微信窗口中的渲染子窗口（MMUIRenderSubWindowHW）"""
    children = []
    def enum_child(child, _):
        cb = ctypes.create_unicode_buffer(260)
        ctypes.windll.user32.GetClassNameW(child, cb, 260)
        children.append((child, cb.value))
        return True
    ctypes.windll.user32.EnumChildWindows(
        main_hwnd,
        ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)(enum_child),
        0
    )
    for child, cls in children:
        if cls == "MMUIRenderSubWindowHW":
            return child
    return main_hwnd  # 找不到就发到主窗口


def scroll_up():
    """用原生 C# EXE 发 PageUp"""
    exe = os.path.join(os.path.dirname(os.path.abspath(__file__)), "send_pgup.exe")
    if os.path.exists(exe):
        subprocess.run([exe], capture_output=True, timeout=10)


def screenshot_right_half():
    """截取屏幕右半边，去掉底部任务栏和输入框"""
    full = ImageGrab.grab()
    sw, sh = full.size
    half_x = sw // 2
    # 只取聊天消息区域（去掉底部任务栏 + 输入框）
    crop_bottom = sh - TASKBAR_H - BOTTOM_CROP
    img = full.crop((half_x, 0, sw, crop_bottom))
    return img


def image_similarity(img1, img2):
    if img1.size != img2.size:
        return 0.0
    s1 = img1.resize((80, 80)).convert("L")
    s2 = img2.resize((80, 80)).convert("L")
    d = 0
    p1, p2 = list(s1.getdata()), list(s2.getdata())
    for a, b in zip(p1, p2):
        d += abs(a - b)
    return 1.0 - d / (255 * 80 * 80)


def analyze_screenshot(img):
    """OCR 识别并标注发送者（简化版：只认文字，不区分颜色）"""
    if not OCR_AVAILABLE:
        return []

    try:
        data = pytesseract.image_to_data(
            img, lang="chi_sim+eng",
            output_type=pytesseract.Output.DICT,
            config="--psm 6 --oem 3"
        )
        texts = []
        prev_y = None
        cur_line = ""
        for i in range(len(data["text"])):
            t = data["text"][i].strip()
            if not t:
                continue
            y = data["top"][i]
            if prev_y is not None and abs(y - prev_y) > 15:
                if cur_line:
                    texts.append(cur_line)
                cur_line = t
            else:
                cur_line = (cur_line + t).strip()
            prev_y = y
        if cur_line:
            texts.append(cur_line)

        # 所有文字先标记为对方（因为无法可靠区分颜色）
        # 可以在输出后手动标注
        return [("other", t) for t in texts if t]
    except Exception as e:
        print(f"    OCR错误: {e}")
        return []


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("=" * 60)
    print("  微信聊天记录导出 (截图)")
    print("=" * 60)
    print()
    print("  【操作】")
    print("  1. 双击联系人 → 弹出聊天窗口")
    print("  2. 把窗口拖到屏幕**右边**")
    print("  3. 输完信息后脚本自动截图+翻页")
    print()

    other_name = input("对方名称: ").strip() or "对方"
    my_name = input("你的名称(如RAY): ").strip() or "我"

    input(f"\n将窗口放在屏幕右边，按 Enter 开始 > ")

    print("\n开始...")
    time.sleep(1)

    # 先截一张预览看看尺寸
    test_img = screenshot_right_half()
    print(f"📐 截图尺寸: {test_img.size[0]}x{test_img.size[1]}")
    test_img.save(os.path.join(OUTPUT_DIR, "_preview.png"))
    print(f"📁 预览图已保存: {os.path.join(OUTPUT_DIR, '_preview.png')}")
    print(f"  看看截图范围对不对，不对按 Ctrl+C 取消")
    input("按 Enter 继续翻页导出 > ")

    print()
    print("=" * 60)
    print("  准备开始")
    print("=" * 60)
    print()
    print("  ⚠ 请在倒计时内点击微信聊天窗口聚焦")
    for i in range(3, 0, -1):
        print(f"    {i}...")
        time.sleep(1)
    print("  开始导出!")

    screenshots_dir = os.path.join(OUTPUT_DIR, "screenshots")
    os.makedirs(screenshots_dir, exist_ok=True)

    scroll_count = 0
    no_new = 0
    last_img = None

    while scroll_count < MAX_SCROLLS:
        img = screenshot_right_half()
        if not img:
            break

        if last_img and image_similarity(img, last_img) > 0.9:
            no_new += 1
        else:
            no_new = 0

        if no_new >= DUPLICATE_STOP:
            print(f"\n✅ 到顶了")
            break

        img.save(os.path.join(screenshots_dir, f"p{scroll_count:04d}.png"))

        msgs = analyze_screenshot(img)
        for who, text in msgs:
            all_messages.append((who, text))

        if scroll_count % 5 == 0:
            print(f"  #{scroll_count} | {len(all_messages)} 条文字")

        last_img = img.copy()

        # 发 PageUp 到前台窗口（用户已在倒计时期间点击了微信）
        scroll_up()

        time.sleep(SCROLL_DELAY)
        scroll_count += 1

    # 保存
    safe = safe_name(other_name)
    path = os.path.join(OUTPUT_DIR, f"{safe}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"聊天记录 - {other_name}\n")
        f.write(f"导出: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"截图 {scroll_count} 张, 识别 {len(all_messages)} 条\n")
        f.write("=" * 50 + "\n\n")
        # 全部标记为 "(文字)" 因为颜色区分暂不可靠
        for who, text in reversed(all_messages):
            f.write(f"{text}\n")

    print(f"\n{'=' * 60}")
    print(f"  ✅ 导出完成!")
    print(f"  📁 {path}")
    print(f"  📊 {scroll_count} 张截图, {len(all_messages)} 条文字")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  中断")
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
    input("按 Enter 退出...")
