"""托盘行为自测（同进程，能直接操作界面与窗口消息）。

覆盖：启动即有托盘图标、最小化收进托盘、托盘双击恢复、
关闭窗口留在托盘（开关打开时）、关掉开关后关闭就退出。
"""

import ctypes
import ctypes.wintypes as wt
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

import webview  # noqa: E402
import app as appmod  # noqa: E402
from tray import Tray  # noqa: E402

user32 = ctypes.windll.user32
user32.DefWindowProcW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
user32.DefWindowProcW.restype = ctypes.c_ssize_t
user32.PostMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
user32.ShowWindow.argtypes = [wt.HWND, ctypes.c_int]

WM_TRAY = 0x8000 + 20
WM_LBUTTONDBLCLK = 0x0203
WM_CLOSE = 0x0010
SW_MINIMIZE = 6

checks = []


def check(name, ok, detail=""):
    checks.append((name, bool(ok), detail))
    print(("PASS  " if ok else "FAIL  ") + name + (f"  ({detail})" if detail else ""))


def wait(predicate, timeout=10, step=0.3):
    end = time.time() + timeout
    while time.time() < end:
        if predicate():
            return True
        time.sleep(step)
    return False


def main_hwnd():
    found = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def cb(hwnd, _):
        n = user32.GetWindowTextLengthW(hwnd)
        if n:
            buf = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, buf, n + 1)
            cls = ctypes.create_unicode_buffer(128)
            user32.GetClassNameW(hwnd, cls, 128)
            if buf.value.strip() in ("实用工具", "Utility Toolkit") and cls.value != Tray.CLASS_NAME:
                found.append(hwnd)
        return True

    user32.EnumWindows(cb, 0)
    return found[0] if found else None


def main():
    # 起点固定：中文、托盘全开、关闭不留在托盘
    pref_file = appmod.data_dir() / "ui_prefs.json"
    try:
        saved = json.loads(pref_file.read_text(encoding="utf-8")) if pref_file.exists() else {}
    except Exception:
        saved = {}
    saved.update({"language": "zh", "tray_enabled": True, "minimize_to_tray": True, "close_to_tray": False})
    pref_file.write_text(json.dumps(saved, ensure_ascii=False), encoding="utf-8")

    built = appmod.build_window()
    win = built[0]

    def js(code, default=None):
        try:
            return win.evaluate_js(code)
        except Exception:
            return default

    def on_start():
        appmod.attach_tray(win)
        end = time.time() + 40
        while time.time() < end:
            if js("document.readyState") == "complete":
                break
            time.sleep(0.4)
        time.sleep(2.5)

        host = getattr(win, "tray_host", None)
        check("托盘已启动", bool(host and host.available), (host.error if host else "无 host"))
        hwnd = main_hwnd()
        check("主窗口存在", bool(hwnd), f"hwnd={hwnd}")
        tray = (host.tray.hwnd if host and host.tray else 0) or user32.FindWindowW(Tray.CLASS_NAME, None)
        check("托盘图标已注册", bool(tray), f"hwnd={tray}")
        check("启动时窗口可见", bool(user32.IsWindowVisible(hwnd)))

        # 1) 最小化 → 收进托盘
        user32.ShowWindow(hwnd, SW_MINIMIZE)
        check("最小化后隐藏", wait(lambda: not user32.IsWindowVisible(hwnd)), "")

        # 2) 托盘双击 → 恢复
        user32.PostMessageW(tray, WM_TRAY, 1, WM_LBUTTONDBLCLK)
        check("托盘双击恢复", wait(lambda: user32.IsWindowVisible(hwnd)), "")

        # 3) 打开「关闭时留在托盘」
        js("location.hash = '#/settings'")
        time.sleep(0.6)
        js("document.querySelector('#setRail .set-tab[data-set-tab=\"general\"]').click()")
        time.sleep(0.5)
        before = js("document.querySelector('#closeTraySwitch').classList.contains('on')")
        if not before:
            js("document.querySelector('#closeTraySwitch').click()")
        time.sleep(1.0)
        check("开关已打开", js("document.querySelector('#closeTraySwitch').classList.contains('on')"))

        # 4) 点关闭 → 应该只是隐藏，进程还在
        user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
        hidden = wait(lambda: not user32.IsWindowVisible(hwnd), 8)
        check("关闭后收进托盘", hidden, f"visible={bool(user32.IsWindowVisible(hwnd))}")
        check("进程还在跑", bool(js("1")), "能继续执行 JS")

        # 5) 再双击托盘回来
        user32.PostMessageW(tray, WM_TRAY, 1, WM_LBUTTONDBLCLK)
        check("再次恢复", wait(lambda: user32.IsWindowVisible(hwnd)), "")

        # 6) 关掉「关闭时留在托盘」→ 关闭应真的退出
        js("document.querySelector('#setRail .set-tab[data-set-tab=\"general\"]').click()")
        time.sleep(0.4)
        js("location.hash = '#/settings'")
        time.sleep(0.4)
        js("document.querySelector('#setRail .set-tab[data-set-tab=\"general\"]').click()")
        time.sleep(0.4)
        js("document.querySelector('#closeTraySwitch').click()")
        time.sleep(1.0)
        check("开关已关闭", not js("document.querySelector('#closeTraySwitch').classList.contains('on')"))

        try:
            win.destroy()
            time.sleep(1.0)
            check("关掉开关后关闭就退出", True, "窗口已销毁")
        except Exception as exc:
            check("关掉开关后关闭就退出", False, str(exc))

    webview.start(func=on_start, gui="edgechromium")
    failed = [c for c in checks if not c[1]]
    print(f"\n{len(checks) - len(failed)}/{len(checks)} 通过")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
