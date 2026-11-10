"""打包版实测：托盘图标、最小化收托盘、语言切换、关于页版本。

直接跑安装目录里的 exe，验证的是最终产物而不是源码。
用法：python dev/dev_packaged_v10.py [安装目录]
"""

import ctypes
import ctypes.wintypes as wt
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "dev"))
from shot_util import shot  # noqa: E402

TARGET = Path(sys.argv[1] if len(sys.argv) > 1 else r"D:\_pt_v10_test")
EXE = TARGET / "实用工具.exe"
SHOTS = ROOT / "dev" / "_shots" / "v10pkg"
TRAY_CLASS = "PracticalToolsTrayWnd"
WM_TRAY = 0x8000 + 20
WM_LBUTTONDBLCLK = 0x0203
SW_MINIMIZE = 6

user32 = ctypes.windll.user32
user32.DefWindowProcW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
user32.DefWindowProcW.restype = ctypes.c_ssize_t
user32.PostMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
user32.ShowWindow.argtypes = [wt.HWND, ctypes.c_int]

checks = []


def check(name, ok, detail=""):
    checks.append((name, bool(ok), detail))
    print(("PASS  " if ok else "FAIL  ") + name + (f"  ({detail})" if detail else ""))


def windows():
    out = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def cb(hwnd, _):
        n = user32.GetWindowTextLengthW(hwnd)
        if n:
            buf = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, buf, n + 1)
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, cls, 256)
            pid = wt.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            out.append((hwnd, buf.value, cls.value, pid.value, bool(user32.IsWindowVisible(hwnd))))
        return True

    user32.EnumWindows(cb, 0)
    return out


def wait(predicate, timeout=30, step=0.5):
    end = time.time() + timeout
    while time.time() < end:
        value = predicate()
        if value:
            return value
        time.sleep(step)
    return None


def main():
    if not EXE.exists():
        print("找不到 exe:", EXE)
        return 2
    SHOTS.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen([str(EXE)])
    try:
        # onefile 会解压后另起子进程，父 pid 不等于窗口所属 pid，按标题找
        hwnd = wait(lambda: next((h for h, t, c, p, v in windows()
                                  if t.strip() in ("实用工具", "Utility Toolkit")
                                  and c != TRAY_CLASS and v), None), 50)
        check("打包版启动", bool(hwnd), f"hwnd={hwnd}")
        if not hwnd:
            return 1
        time.sleep(4)

        tray = wait(lambda: user32.FindWindowW(TRAY_CLASS, None), 10)
        check("托盘图标已出现", bool(tray), f"hwnd={tray}")

        shot(hwnd, SHOTS / "home.png")

        # 最小化 → 收进托盘
        user32.ShowWindow(hwnd, SW_MINIMIZE)
        hidden = wait(lambda: not user32.IsWindowVisible(hwnd), 10)
        check("最小化后窗口隐藏", bool(hidden))

        user32.PostMessageW(tray, WM_TRAY, 1, WM_LBUTTONDBLCLK)
        check("托盘双击恢复窗口", bool(wait(lambda: user32.IsWindowVisible(hwnd), 10)))

        # 关于页版本
        print("提示：接下来需要界面自动跳到设置页，这一步靠窗口截图人工确认")
        time.sleep(1)
        shot(hwnd, SHOTS / "restored.png")
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=10)
        except Exception:
            proc.kill()

    failed = [c for c in checks if not c[1]]
    print(f"\n{len(checks) - len(failed)}/{len(checks)} 通过")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
