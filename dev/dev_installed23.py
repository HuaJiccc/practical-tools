"""启动已安装的 exe，确认「图片工具」页在打包版里能正常渲染。

用法：
    python dev/dev_installed23.py              # 只截首屏
    python dev/dev_installed23.py x,y [x2,y2]  # 额外按窗口内坐标点击后截图
"""
from pathlib import Path as _P
_ROOT = _P(__file__).resolve().parent.parent

import ctypes
import ctypes.wintypes as wt
import os
import subprocess
import sys
import time

EXE = os.environ.get("PT_EXE") or str(_ROOT / "dist" / "个人工具.exe")
SHOTS = str(_ROOT / "dev/_shots/v23")
os.makedirs(SHOTS, exist_ok=True)

clicks = []
for a in sys.argv[1:]:
    x, y = a.split(",")
    clicks.append((int(x), int(y)))

env = {k: v for k, v in os.environ.items() if k != "PERSONALTOOLS_DATA"}
proc = subprocess.Popen([EXE], env=env, cwd=os.path.dirname(EXE))
print("launcher", proc.pid, flush=True)

u = ctypes.windll.user32
k32 = ctypes.windll.kernel32
time.sleep(14.0)

found = []


@ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
def cb(hwnd, lparam):
    n = u.GetWindowTextLengthW(hwnd)
    if not n:
        return True
    buf = ctypes.create_unicode_buffer(n + 1)
    u.GetWindowTextW(hwnd, buf, n + 1)
    if buf.value == "个人工具" and u.IsWindowVisible(hwnd):
        found.append(hwnd)
    return True


u.EnumWindows(cb, 0)
print("windows:", found, flush=True)
if not found:
    proc.terminate()
    sys.exit(1)


def area(hwnd):
    r = wt.RECT()
    u.GetWindowRect(hwnd, ctypes.byref(r))
    return (r.right - r.left) * (r.bottom - r.top)


hwnd = max(found, key=area)

from PIL import Image  # noqa: E402


class BMIH(ctypes.Structure):
    _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG),
                ("biPlanes", wt.WORD), ("biBitCount", wt.WORD), ("biCompression", wt.DWORD),
                ("biSizeImage", wt.DWORD), ("biXPelsPerMeter", wt.LONG), ("biYPelsPerMeter", wt.LONG),
                ("biClrUsed", wt.DWORD), ("biClrImportant", wt.DWORD)]


class BMI(ctypes.Structure):
    _fields_ = [("bmiHeader", BMIH), ("bmiColors", wt.DWORD * 3)]


def shot(path):
    rect = wt.RECT()
    u.GetWindowRect(hwnd, ctypes.byref(rect))
    w, h = rect.right - rect.left, rect.bottom - rect.top
    hdc = u.GetWindowDC(hwnd)
    mdc = ctypes.windll.gdi32.CreateCompatibleDC(hdc)
    bmp = ctypes.windll.gdi32.CreateCompatibleBitmap(hdc, w, h)
    ctypes.windll.gdi32.SelectObject(mdc, bmp)
    u.PrintWindow(hwnd, mdc, 2)
    bi = BMI()
    bi.bmiHeader.biSize = ctypes.sizeof(BMIH)
    bi.bmiHeader.biWidth = w
    bi.bmiHeader.biHeight = -h
    bi.bmiHeader.biPlanes = 1
    bi.bmiHeader.biBitCount = 32
    buf = ctypes.create_string_buffer(w * h * 4)
    ctypes.windll.gdi32.GetDIBits(mdc, bmp, 0, h, buf, ctypes.byref(bi), 0)
    Image.frombuffer("RGBA", (w, h), buf, "raw", "BGRA", 0, 1).convert("RGB").save(path)
    ctypes.windll.gdi32.DeleteObject(bmp)
    ctypes.windll.gdi32.DeleteDC(mdc)
    u.ReleaseDC(hwnd, hdc)
    return w, h


def force_focus():
    u.ShowWindow(hwnd, 9)  # SW_RESTORE
    fg = u.GetForegroundWindow()
    tid_fg = u.GetWindowThreadProcessId(fg, None)
    tid_me = k32.GetCurrentThreadId()
    u.AttachThreadInput(tid_me, tid_fg, True)
    u.BringWindowToTop(hwnd)
    u.SetForegroundWindow(hwnd)
    u.AttachThreadInput(tid_me, tid_fg, False)
    time.sleep(0.4)
    return u.GetForegroundWindow() == hwnd


print("home", shot(os.path.join(SHOTS, "installed_home.png")), flush=True)
print("focused", force_focus(), flush=True)

# 点击要用 WebView 子窗口的坐标：主窗口还带着标题栏和边框，
# 而且窗口位置每次启动都不一样，拿主窗口 rect 直接加会整体偏移。
kids = []


@ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
def cb_child(child, _lp):
    cls = ctypes.create_unicode_buffer(256)
    u.GetClassNameW(child, cls, 256)
    r = wt.RECT()
    u.GetWindowRect(child, ctypes.byref(r))
    kids.append((cls.value, r))
    return True


u.EnumChildWindows(hwnd, cb_child, 0)
target = next((item for item in kids if "Chrome_WidgetWin" in item[0]), None)
if target:
    rect = target[1]
    print("webview rect", rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top, flush=True)
else:
    rect = wt.RECT()
    u.GetWindowRect(hwnd, ctypes.byref(rect))
    print("fallback to window rect", flush=True)

if os.environ.get("PT_MAX"):
    u.ShowWindow(hwnd, 3)  # SW_MAXIMIZE
    time.sleep(1.2)
    u.GetWindowRect(hwnd, ctypes.byref(rect))
    print("maximized rect", rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top, flush=True)
    shot(os.path.join(SHOTS, "installed_max.png"))

for i, (x, y) in enumerate(clicks):
    u.SetCursorPos(rect.left + x, rect.top + y)
    time.sleep(0.2)
    u.mouse_event(0x0002, 0, 0, 0, 0)
    time.sleep(0.1)
    u.mouse_event(0x0004, 0, 0, 0, 0)
    time.sleep(1.8)
    p = os.path.join(SHOTS, f"installed_click{i + 1}.png")
    print("click", x, y, shot(p), flush=True)

proc.terminate()
time.sleep(1.0)
print("done")
