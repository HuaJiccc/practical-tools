"""关于页版本号自测：确认界面显示的是真实版本，而不是 index.html 里的占位符。

场景：用户改过数据目录、重启后停在「设置 → 数据目录」，再看「关于」，
版本号不该退回 1.0.0。
"""
import json
import os
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "_data_ver"
shutil.rmtree(DATA, ignore_errors=True)
DATA.mkdir(parents=True, exist_ok=True)
(DATA / "ui_prefs.json").write_text(json.dumps({
    "settingsTab": "data",
    "startPage": "last",
    "theme": "dark",
    "lastPage": "settings",
    "language": "zh",
}), encoding="utf-8")
os.environ["PERSONALTOOLS_DATA"] = str(DATA)
sys.path.insert(0, str(ROOT.parent / "app"))

from dev_image_stress import capture, find_hwnd  # noqa: E402

os.environ["PERSONALTOOLS_DATA"] = str(DATA)

import app as appmod  # noqa: E402

SHOT = ROOT / "_shots" / "version_ui.png"
SHOT.parent.mkdir(parents=True, exist_ok=True)


def main():
    win, _ = appmod.build_window()
    pid = os.getpid()
    out = {}

    def work():
        time.sleep(3.2)
        js = win.evaluate_js
        js("window.__errs=[];window.addEventListener('error',e=>window.__errs.push(String(e.message)))")
        # 启动后直接读（对应 syncSettingsUi 走过的那次）
        out["boot_version"] = js("(document.querySelector('#appVersion')||{}).textContent")
        js("location.hash='#/settings'")
        time.sleep(1.2)
        js("document.querySelector('#setRail [data-set-tab=\"data\"]').click()")
        time.sleep(1.0)
        out["data_tab_version"] = js("(document.querySelector('#appVersion')||{}).textContent")
        js("document.querySelector('#setRail [data-set-tab=\"about\"]').click()")
        time.sleep(1.4)
        out["about_version"] = js("(document.querySelector('#appVersion')||{}).textContent")
        out["badge"] = js("(document.querySelector('#aboutVersionBadge')||{}).textContent")
        out["errs"] = js("JSON.stringify(window.__errs||[])")
        hwnd = find_hwnd(pid)
        if hwnd:
            capture(hwnd, str(SHOT))
        print(json.dumps(out, ensure_ascii=False, indent=2), flush=True)
        win.destroy()

    import threading

    threading.Thread(target=work, daemon=True).start()
    import webview

    webview.start(debug=False)


if __name__ == "__main__":
    main()
