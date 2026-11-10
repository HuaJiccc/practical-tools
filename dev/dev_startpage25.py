"""验证「启动页面」跨启动生效（顺带验证界面偏好确实写进了 data/ui_prefs.json）。

用法：
    python dev/dev_startpage25.py set last      # 设为「上次停留」并跳到记事
    python dev/dev_startpage25.py check notes   # 期望这次打开直接停在记事
    python dev/dev_startpage25.py set chart     # 设为固定页
    python dev/dev_startpage25.py check chart
"""
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "_data_sp"
DATA.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT.parent / "app"))
os.environ["PERSONALTOOLS_DATA"] = str(DATA)

import webview  # noqa: E402
import app as appmod  # noqa: E402

mode = sys.argv[1] if len(sys.argv) > 1 else "check"
arg = sys.argv[2] if len(sys.argv) > 2 else ""
report = {}


def main():
    win, _ = appmod.build_window()

    def work():
        try:
            time.sleep(3.2)
            js = win.evaluate_js
            if mode == "set":
                js("location.hash = '#/settings'")
                time.sleep(1.2)
                js("document.querySelector('#setRail [data-set-tab=\"general\"]').click()")
                time.sleep(0.5)
                js(
                    f"(()=>{{const s=document.querySelector('#startPage'); s.value='{arg}';"
                    f"s.dispatchEvent(new Event('change'));}})()"
                )
                time.sleep(1.2)
                report["select"] = js("document.querySelector('#startPage').value")
                if arg == "last":
                    js("location.hash = '#/notes'")
                    time.sleep(2.0)
                report["page_before_close"] = js("document.querySelector('.page.active').dataset.page")
                time.sleep(3.0)  # 等 pushPrefs 的 350ms 防抖 + 落盘
            else:
                report["hash"] = js("location.hash")
                report["page"] = js("document.querySelector('.page.active').dataset.page")
                report["title"] = js("document.getElementById('pageTitle').textContent")
                report["local_prefs"] = js("localStorage.getItem('personal-tools.prefs')")
        except Exception:
            import traceback
            report["exception"] = traceback.format_exc()
        finally:
            try:
                win.destroy()
            except Exception:
                pass

    import threading
    threading.Thread(target=work, daemon=True).start()
    # 和 app.main() 一样用持久化 profile
    webview.start(debug=False, private_mode=False, storage_path=str(DATA / "webview"))
    print(json.dumps(report, ensure_ascii=False))
    if mode == "check":
        ok = report.get("page") == arg
        print(("PASS" if ok else "FAIL") + f"  启动后停在 {report.get('page')}（期望 {arg}）")
        prefs_file = DATA / "ui_prefs.json"
        if prefs_file.exists():
            print("ui_prefs.json:", prefs_file.read_text("utf-8").replace("\n", " "))
        sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
