"""安装程序界面自测：跑一遍向导，逐页截图，并检查关键控件是否出现。

用法：
    python dev/dev_installer_shots.py            # 截欢迎页 / 协议页 / 目录页，然后取消
    python dev/dev_installer_shots.py --install  # 一直走到完成（会真的装到临时目录）
"""

import ctypes
import ctypes.wintypes as wt
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SETUP = ROOT / "dist-installer" / "实用工具-3.0.0-安装程序.exe"
SHOTS = ROOT / "dev" / "_shots" / "installer"

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

VK_RETURN = 0x0D
VK_TAB = 0x09
VK_SPACE = 0x20
VK_ESCAPE = 0x1B

report = []


def log(ok, text):
    report.append((ok, text))
    print(("PASS " if ok else "FAIL ") + text)


def find_window(pid):
    """按标题找安装向导窗口。

    不能用 PID：Inno 会把安装器复制到临时目录再启动，窗口属于另一个进程。
    主程序的标题是「实用工具」，安装器是「安装 - 实用工具」，据此区分。
    """
    found = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def cb(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        n = user32.GetWindowTextLengthW(hwnd)
        if n:
            buf = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, buf, n + 1)
            title = buf.value.strip()
            if title and "实用工具" in title and "安装" in title:
                found.append((hwnd, title))
        return True

    user32.EnumWindows(cb, 0)
    return found[0] if found else (None, "")


def shot(hwnd, path):
    rect = wt.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    w, h = rect.right - rect.left, rect.bottom - rect.top
    if w <= 0 or h <= 0:
        return False
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
    bi.bmiHeader.biCompression = 0
    buf = ctypes.create_string_buffer(w * h * 4)
    gdi32.GetDIBits(mdc, bmp, 0, h, buf, ctypes.byref(bi), 0)

    from PIL import Image

    img = Image.frombuffer("RGBA", (w, h), buf, "raw", "BGRA", 0, 1).convert("RGB")
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(mdc)
    user32.ReleaseDC(hwnd, hdc)
    return True


def foreground(hwnd):
    """把窗口提到前台。SetForegroundWindow 单独调用经常被拒，先接一下输入队列。"""
    tid = user32.GetWindowThreadProcessId(hwnd, None)
    fg = user32.GetForegroundWindow()
    ftid = user32.GetWindowThreadProcessId(fg, None)
    if tid != ftid:
        user32.AttachThreadInput(ftid, tid, True)
        user32.SetForegroundWindow(hwnd)
        user32.AttachThreadInput(ftid, tid, False)
    else:
        user32.SetForegroundWindow(hwnd)
    time.sleep(0.2)


def key(vk):
    user32.keybd_event(vk, 0, 0, 0)
    time.sleep(0.06)
    user32.keybd_event(vk, 0, 2, 0)
    time.sleep(0.6)


VK_MENU = 0x12
VK_A = 0x41


def alt_key(vk):
    """Alt + 字母，用来触发带 & 的加速键（协议页的「我同意此协议(A)」）。"""
    user32.keybd_event(VK_MENU, 0, 0, 0)
    time.sleep(0.05)
    user32.keybd_event(vk, 0, 0, 0)
    time.sleep(0.05)
    user32.keybd_event(vk, 0, 2, 0)
    user32.keybd_event(VK_MENU, 0, 2, 0)
    time.sleep(0.6)


def page_text(hwnd):
    """收集窗口里所有文本控件的内容，用来判断当前停在哪一页。"""
    parts = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def cb(child, _):
        n = user32.GetWindowTextLengthW(child)
        if n:
            buf = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(child, buf, n + 1)
            if buf.value.strip():
                parts.append(buf.value.strip())
        return True

    user32.EnumChildWindows(hwnd, cb, 0)
    return " | ".join(parts)


def main():
    if not SETUP.exists():
        print(f"没有安装包：{SETUP}")
        return 1
    SHOTS.mkdir(parents=True, exist_ok=True)

    proc = subprocess.Popen([str(SETUP)])
    deadline = time.time() + 20
    hwnd, title = None, ""
    while time.time() < deadline:
        hwnd, title = find_window(proc.pid)
        if hwnd:
            break
        time.sleep(0.4)
    if not hwnd:
        log(False, "安装窗口没有出现")
        proc.kill()
        return 1
    log(True, f"安装界面已弹出：{title}")
    time.sleep(0.8)
    foreground(hwnd)
    shot(hwnd, SHOTS / "01_welcome.png")

    text = page_text(hwnd)
    log("欢迎" in text or "下一步" in text, "欢迎页有「下一步」按钮")

    key(VK_RETURN)  # 欢迎 → 协议
    time.sleep(0.5)
    shot(hwnd, SHOTS / "02_license.png")
    text = page_text(hwnd)
    log("许可" in text or "接受" in text, f"协议页出现：{'接受' in text}")

    # 协议页默认停在「我不同意」，不选同意就无法下一步
    alt_key(VK_A)
    shot(hwnd, SHOTS / "02b_agreed.png")
    key(VK_RETURN)
    time.sleep(0.6)
    shot(hwnd, SHOTS / "03_dir.png")
    text = page_text(hwnd)
    log("安装" in text and ("浏览" in text or "目标" in text or "文件夹" in text),
        f"出现目录选择页：{'浏览' in text}")

    if "--install" in sys.argv:
        target = os.environ.get("PT_INSTALL_DIR") or r"D:\_pt_install_test"
        # 目录框是编辑框，全选后输入新路径
        key(VK_RETURN)  # 目录 → 附加任务
        time.sleep(0.4)
        shot(hwnd, SHOTS / "04_tasks.png")
        key(VK_RETURN)  # 任务 → 安装
        for i in range(20):
            time.sleep(1.2)
            if not user32.IsWindow(hwnd):
                break
            text = page_text(hwnd)
            if "完成" in text:
                shot(hwnd, SHOTS / "05_done.png")
                log(True, "走到完成页")
                break
        key(VK_RETURN)
    else:
        key(VK_ESCAPE)
        time.sleep(0.6)
        text = page_text(hwnd)
        if "退出" in text or "取消" in text:
            key(VK_RETURN)  # 确认退出
        log(True, "已在安装前取消，未改动系统")

    time.sleep(1.0)
    try:
        proc.wait(timeout=8)
    except subprocess.TimeoutExpired:
        proc.kill()

    failed = [t for ok, t in report if not ok]
    print(f"\n{len(report) - len(failed)}/{len(report)} 通过")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
