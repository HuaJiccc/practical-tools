"""关闭窗口的二选一：首次弹框、选完记住、之后不再问、设置里能改。

真正去点窗口的 × 太依赖坐标，这里直接往窗口句柄发 WM_CLOSE ——
和点 × 走的是同一条 closing 事件，断言的是行为不是像素。
"""

import ctypes
import ctypes.wintypes as wt
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))
sys.path.insert(0, str(ROOT / "dev"))

WM_CLOSE = 0x0010
checks = []


def check(name, ok, detail=""):
    checks.append((name, bool(ok), detail))
    print(("PASS  " if ok else "FAIL  ") + name + (f"  ({detail})" if detail else ""))


def main():
    import webview
    import app as appmod
    from shot_util import find, shot

    pref_file = appmod.data_dir() / "ui_prefs.json"
    try:
        saved = json.loads(pref_file.read_text(encoding="utf-8")) if pref_file.exists() else {}
    except Exception:
        saved = {}
    # 关键前置：当作从没选过（并且没有旧的 close_to_tray 残留）
    saved.pop("close_action", None)
    saved.pop("close_to_tray", None)
    saved["language"] = "zh"
    saved["theme"] = "light"
    pref_file.write_text(json.dumps(saved, ensure_ascii=False), encoding="utf-8")

    win = appmod.build_window()[0]
    host = appmod.attach_tray(win)
    shots = ROOT / "dev" / "_shots" / "close"
    shots.mkdir(parents=True, exist_ok=True)
    user32 = ctypes.windll.user32
    user32.PostMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]

    def js(code, default=None):
        try:
            return win.evaluate_js(code)
        except Exception:
            return default

    def prefs_on_disk():
        try:
            return json.loads(pref_file.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def wait_for(pred, timeout=12, step=0.3):
        end = time.time() + timeout
        while time.time() < end:
            value = pred()
            if value:
                return value
            time.sleep(step)
        return None

    def close_window(hwnd):
        user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)

    def on_start():
        end = time.time() + 40
        while time.time() < end:
            if js("document.readyState") == "complete":
                break
            time.sleep(0.4)
        time.sleep(2.2)

        hwnd = find("实用工具")
        check("窗口已就绪", bool(hwnd), f"hwnd={hwnd}")
        check("托盘可用", bool(host and host.available))

        # --- 第一次关闭：应该弹框，且不关窗口 ---
        close_window(hwnd)
        opened = wait_for(lambda: js("document.querySelector('#modalRoot').classList.contains('open')") is True, 8)
        check("首次关闭弹出选择框", bool(opened))
        options = js("document.querySelectorAll('#modalRoot .close-option').length")
        check("两个选项都在", options == 2, f"{options} 个")
        check("窗口没有被关掉", bool(user32.IsWindowVisible(hwnd)))
        shot(find("实用工具"), shots / "ask.png")

        # --- 选「收进托盘」---
        js("document.querySelector('#modalRoot [data-pick=\"tray\"]').click()")
        hidden = wait_for(lambda: not user32.IsWindowVisible(hwnd), 8)
        check("选收进托盘后窗口隐藏", bool(hidden))
        check("选择已写入偏好", prefs_on_disk().get("close_action") == "tray",
              str(prefs_on_disk().get("close_action")))

        # --- 恢复后再关：不该再问 ---
        host.show_window()
        shown = wait_for(lambda: user32.IsWindowVisible(hwnd), 10)
        check("从托盘恢复成功", bool(shown))
        time.sleep(1.2)
        close_window(find("实用工具") or hwnd)
        time.sleep(1.6)
        check("第二次关闭不再询问",
              js("document.querySelector('#modalRoot').classList.contains('open')") is not True)
        check("第二次仍然收进托盘", not user32.IsWindowVisible(find("实用工具") or hwnd))

        # --- 设置里改成「直接退出」---
        host.show_window()
        wait_for(lambda: user32.IsWindowVisible(hwnd), 10)
        time.sleep(1.2)
        # 先离开设置页再回来：hash 没变的话不会触发 route，读到的还是旧状态
        js("location.hash = '#/home'")
        time.sleep(0.7)
        js("location.hash = '#/settings'")
        time.sleep(0.9)
        check("设置里是「收进托盘」选中",
              js("document.querySelector('#closeSeg button.active')?.dataset.act") == "tray",
              str(js("document.querySelector('#closeSeg button.active')?.dataset.act")))
        js("document.querySelector('#closeSeg button[data-act=\"quit\"]').click()")
        time.sleep(0.8)
        check("改为直接退出后偏好已更新", prefs_on_disk().get("close_action") == "quit",
              str(prefs_on_disk().get("close_action")))
        shot(find("实用工具"), shots / "settings.png")

        # --- 再关就应该真退出 ---
        close_window(find("实用工具") or hwnd)
        gone = wait_for(lambda: js("1") is None, 10)
        check("选择直接退出后进程真的结束", bool(gone))

    webview.start(func=on_start, gui="edgechromium")

    failed = [c for c in checks if not c[1]]
    print(f"\n{len(checks) - len(failed)}/{len(checks)} 通过")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
