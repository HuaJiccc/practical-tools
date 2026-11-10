"""英文界面的截图与窗口标题校验。"""

import ctypes
import ctypes.wintypes as wt
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))
sys.path.insert(0, str(ROOT / "dev"))

import webview  # noqa: E402
import app as appmod  # noqa: E402
from shot_util import find, shot  # noqa: E402

SHOTS = ROOT / "dev" / "_shots" / "v10en"

SHOT_PLAN = [
    ("settings", "document.querySelector('#setRail .set-tab[data-set-tab=\"general\"]').click()", "settings_general.png"),
    ("settings", "document.querySelector('#setRail .set-tab[data-set-tab=\"about\"]').click()", "settings_about.png"),
    ("home", "", "home.png"),
    ("translate", "", "translate.png"),
    ("image", "", "image.png"),
    ("todo", "", "todo.png"),
    ("time", "", "time.png"),
]


def titles():
    out = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def cb(hwnd, _):
        if ctypes.windll.user32.IsWindowVisible(hwnd):
            n = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            if n:
                buf = ctypes.create_unicode_buffer(n + 1)
                ctypes.windll.user32.GetWindowTextW(hwnd, buf, n + 1)
                out.append(buf.value)
        return True

    ctypes.windll.user32.EnumWindows(cb, 0)
    return out


def main():
    SHOTS.mkdir(parents=True, exist_ok=True)
    win = appmod.build_window()[0]

    def js(code, default=None):
        try:
            return win.evaluate_js(code)
        except Exception:
            return default

    def on_start():
        end = time.time() + 40
        while time.time() < end:
            if js("document.readyState") == "complete":
                break
            time.sleep(0.4)
        time.sleep(2.5)
        js("location.hash = '#/settings'")
        time.sleep(0.6)
        js("document.querySelector('#langSeg button[data-lang=\"en\"]').click()")
        time.sleep(2.6)  # 等 prefs 回写、窗口标题更新

        print("窗口标题:", [t for t in titles() if "工具" in t or "Toolkit" in t])
        print("侧栏分组:", js("Array.from(document.querySelectorAll('.nav-label')).map(n=>n.textContent)"))
        print("品牌副标题:", js("document.querySelector('.brand-text span').textContent"))

        hwnd = find("Utility Toolkit") or find("实用工具")
        for page, extra, name in SHOT_PLAN:
            js(f"location.hash = '#/{page}'")
            time.sleep(0.7)
            if extra:
                js(extra)
                time.sleep(0.5)
            shot(hwnd, SHOTS / name)
            print("shot", name)
        win.destroy()

    webview.start(func=on_start, gui="edgechromium")
    return 0


if __name__ == "__main__":
    sys.exit(main())
