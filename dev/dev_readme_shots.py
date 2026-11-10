"""重新生成 README 用的界面截图（docs/screenshots）。

README 里的图还停在改名前（「个人工具」），所以统一按当前版本重拍一遍。
固定浅色主题 + 中文，四张：概览 / 翻译 / 图片工具 / 设置。
拍完顺手校验文件名与尺寸，避免把半张图或者空白图塞进文档。
"""

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))
sys.path.insert(0, str(ROOT / "dev"))

OUT = ROOT / "docs" / "screenshots"
PAGES = [
    ("home", "#/"),
    ("translate", "#/translate"),
    ("image", "#/image"),
    ("settings", "#/settings"),
]

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
    saved["theme"] = "light"
    saved["language"] = "zh"
    saved["density"] = "standard"
    pref_file.write_text(json.dumps(saved, ensure_ascii=False), encoding="utf-8")

    OUT.mkdir(parents=True, exist_ok=True)
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
        time.sleep(2.0)
        hwnd = find("实用工具")
        check("窗口已就绪", bool(hwnd), f"hwnd={hwnd}")

        for name, route in PAGES:
            js(f"location.hash = '{route}'")
            time.sleep(1.4)
            path = OUT / f"{name}.png"
            shot(hwnd, path)
            size = path.stat().st_size if path.exists() else 0
            check(f"{name}.png 已生成", size > 20000, f"{size // 1024} KB")

        # README 里那两张并排图只用到这四张，多拍一张关于页留给后面的文档
        js("document.querySelector('#setRail .set-tab[data-set-tab=\"about\"]').click()")
        time.sleep(1.0)
        shot(hwnd, OUT / "about.png")
        check("about.png 已生成", (OUT / "about.png").stat().st_size > 20000,
              f"{(OUT / 'about.png').stat().st_size // 1024} KB")

        win.destroy()

    webview.start(func=on_start, gui="edgechromium")

    failed = [c for c in checks if not c[1]]
    print(f"\n{len(checks) - len(failed)}/{len(checks)} 通过")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
