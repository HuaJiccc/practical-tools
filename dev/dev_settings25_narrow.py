"""窄窗口（1000px）下检查设置页：分类导航应变成横向页签，内容不溢出。"""
import json
import os
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "_data_setnarrow"
shutil.rmtree(DATA, ignore_errors=True)
DATA.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT.parent / "app"))
os.environ["PERSONALTOOLS_DATA"] = str(DATA)

import webview  # noqa: E402
import app as appmod  # noqa: E402
from dev_image_stress import capture, find_hwnd  # noqa: E402

SHOTS = ROOT / "_shots" / "v25"
SHOTS.mkdir(parents=True, exist_ok=True)
report = {}


def main():
    win, _ = appmod.build_window()
    pid = os.getpid()

    def work():
        try:
            time.sleep(3.0)
            hwnd = find_hwnd(pid)
            js = win.evaluate_js
            js("localStorage.setItem('personal-tools.prefs', JSON.stringify({theme:'light', accent:'blue', density:'normal', motion:'on'}))")
            win.resize(1000, 700)
            time.sleep(1.2)
            js("location.hash='#/settings'")
            time.sleep(1.2)
            js("document.querySelector('#toasts').innerHTML=''")
            report["rail_dir"] = js("getComputedStyle(document.querySelector('#setRail')).flexDirection")
            report["rail_h"] = js("Math.round(document.querySelector('#setRail').getBoundingClientRect().height)")
            report["card_w"] = js("Math.round(document.querySelector('.set-pane.active .card').getBoundingClientRect().width)")
            report["overflow"] = js("document.documentElement.scrollWidth > document.documentElement.clientWidth")
            capture(hwnd, str(SHOTS / "set_narrow.png"))
            js("document.querySelector('#setRail [data-set-tab=\"trans\"]').click()")
            time.sleep(0.6)
            js("document.querySelector('#toasts').innerHTML=''")
            capture(hwnd, str(SHOTS / "set_narrow_trans.png"))
            report["errors"] = js("JSON.stringify(window.__errs||[])")
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
    webview.start(debug=False)
    print(json.dumps(report, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
