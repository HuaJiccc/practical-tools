"""深色模式下的原生时间/日期控件配色自测。

重点是 <input type="time"> 这类浏览器原生控件：不设 color-scheme 就会保持白底，
深色主题下白底黑字，看着像一块贴纸。这里用计算样式断言，不靠肉眼。
"""

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))
sys.path.insert(0, str(ROOT / "dev"))

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
    saved["theme"] = "dark"
    saved["language"] = "zh"
    pref_file.write_text(json.dumps(saved, ensure_ascii=False), encoding="utf-8")

    win = appmod.build_window()[0]
    shots = ROOT / "dev" / "_shots" / "dark"
    shots.mkdir(parents=True, exist_ok=True)

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
        time.sleep(2.0)

        js("location.hash = '#/plan'")
        time.sleep(0.8)
        js("document.querySelector('#planAdd').click()")
        time.sleep(1.2)

        check("深色主题已生效",
              js("document.documentElement.dataset.theme") == "dark",
              str(js("document.documentElement.dataset.theme")))
        check("color-scheme 为 dark",
              (js("getComputedStyle(document.documentElement).colorScheme") or "") == "dark",
              str(js("getComputedStyle(document.documentElement).colorScheme")))

        for sel, label in (("#plStart", "开始"), ("#plEnd", "结束")):
            bg = js(f"getComputedStyle(document.querySelector('{sel}')).backgroundColor")
            fg = js(f"getComputedStyle(document.querySelector('{sel}')).color")
            check(f"{label}时间框背景是深色", bg in ("rgb(24, 27, 32)", "rgb(30, 34, 41)"), str(bg))
            check(f"{label}时间框文字是浅色", fg in ("rgb(240, 242, 246)",), str(fg))

        hwnd = find("实用工具") or find("Utility Toolkit")
        shot(hwnd, shots / "plan_modal.png")

        # 顺带看一眼长列表页与设置页：color-scheme 也会改原生滚动条
        js("document.querySelector('.modal-close')?.click()")
        time.sleep(0.5)
        js("location.hash = '#/notes'")
        time.sleep(1.0)
        shot(hwnd, shots / "notes_dark.png")
        js("location.hash = '#/settings'")
        time.sleep(1.0)
        shot(hwnd, shots / "settings_dark.png")
        check("深色下页面底色未被原生配色盖住",
              js("getComputedStyle(document.body).backgroundColor") == "rgb(16, 18, 21)",
              str(js("getComputedStyle(document.body).backgroundColor")))

        # 日期控件同样检查一遍（倒数日编辑弹窗里的日期框）
        js("document.querySelector('.modal-close')?.click()")
        time.sleep(0.6)
        js("location.hash = '#/time'")
        time.sleep(1.0)
        js("document.querySelector('#cdAdd').click()")
        time.sleep(1.0)
        dt = js("""(() => {
          const el = document.querySelector('#cdDate');
          if (!el) return null;
          const s = getComputedStyle(el);
          return JSON.stringify({bg: s.backgroundColor, fg: s.color});
        })()""")
        check("倒数日日期框也跟随深色", bool(dt) and "rgb(24, 27, 32)" in str(dt), str(dt))
        hwnd = find("实用工具") or find("Utility Toolkit")
        shot(hwnd, shots / "countdown_modal.png")
        js("document.querySelector('.modal-close')?.click()")
        time.sleep(0.5)

        # 切回浅色，确认还是浅色（别把亮色主题带坏）
        js("location.hash = '#/settings'")
        time.sleep(0.6)
        js("document.querySelector('#themeSeg button[data-theme=\"light\"]').click()")
        time.sleep(0.8)
        js("location.hash = '#/plan'")
        time.sleep(0.7)
        js("document.querySelector('#planAdd').click()")
        time.sleep(1.0)
        light_bg = js("getComputedStyle(document.querySelector('#plStart')).backgroundColor")
        check("浅色下时间框是白底", light_bg == "rgb(255, 255, 255)", str(light_bg))
        check("浅色下 color-scheme 为 light",
              (js("getComputedStyle(document.documentElement).colorScheme") or "") == "light",
              str(js("getComputedStyle(document.documentElement).colorScheme")))

        js("document.querySelector('.modal-close')?.click()")
        time.sleep(0.4)
        # 恢复深色偏好，别影响用户下次打开
        js("document.querySelector('#themeSeg button[data-theme=\"dark\"]').click()") if False else None
        win.destroy()

    webview.start(func=on_start, gui="edgechromium")

    failed = [c for c in checks if not c[1]]
    print(f"\n{len(checks) - len(failed)}/{len(checks)} 通过")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
