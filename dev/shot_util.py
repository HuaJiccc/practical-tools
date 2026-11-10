"""截取正在运行的程序窗口（按标题找），用于人工核对界面。"""

import ctypes
import ctypes.wintypes as wt
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32


def find(title_part):
    found = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def cb(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        n = user32.GetWindowTextLengthW(hwnd)
        if n:
            buf = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, buf, n + 1)
            if buf.value.strip() == title_part:
                found.append(hwnd)
        return True

    user32.EnumWindows(cb, 0)
    return found[0] if found else None


def shot(hwnd, path):
    rect = wt.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    w, h = rect.right - rect.left, rect.bottom - rect.top
    hdc = user32.GetWindowDC(hwnd)
    mdc = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    gdi32.SelectObject(mdc, bmp)
    user32.PrintWindow(hwnd, mdc, 2)

    class BMIH(ctypes.Structure):
        _fields_ = [
            ("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG),
            ("biPlanes", wt.WORD), ("biBitCount", wt.WORD), ("biCompression", wt.DWORD),
            ("biSizeImage", wt.DWORD), ("biXPelsPerMeter", wt.LONG),
            ("biYPelsPerMeter", wt.LONG), ("biClrUsed", wt.DWORD),
            ("biClrImportant", wt.DWORD),
        ]

    class BMI(ctypes.Structure):
        _fields_ = [("bmiHeader", BMIH), ("bmiColors", wt.DWORD * 3)]

    bi = BMI()
    bi.bmiHeader.biSize = ctypes.sizeof(BMIH)
    bi.bmiHeader.biWidth = w
    bi.bmiHeader.biHeight = -h
    bi.bmiHeader.biPlanes = 1
    bi.bmiHeader.biBitCount = 32
    buf = ctypes.create_string_buffer(w * h * 4)
    gdi32.GetDIBits(mdc, bmp, 0, h, buf, ctypes.byref(bi), 0)

    from PIL import Image

    Image.frombuffer("RGBA", (w, h), buf, "raw", "BGRA", 0, 1).convert("RGB").save(path)
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(mdc)
    user32.ReleaseDC(hwnd, hdc)


if __name__ == "__main__":
    title = sys.argv[1] if len(sys.argv) > 1 else "实用工具"
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "dev" / "_shots" / "v30" / "window.png"
    hwnd = find(title)
    if not hwnd:
        print("没有找到窗口:", title)
        sys.exit(1)
    out.parent.mkdir(parents=True, exist_ok=True)
    shot(hwnd, out)
    print("已保存:", out)
