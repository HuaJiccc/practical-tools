"""1.0.3 自测：关于页版本号 + 反馈入口。

- 服务端返回的页面里，版本号已经是真值（不再有占位符）
- 界面显示 1.0.3
- 点「反馈问题」会打开带标题/正文的反馈地址，同时把正文写进剪贴板
"""
import json
import os
import re
import shutil
import sys
import threading
import time
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "_data_feedback"
shutil.rmtree(DATA, ignore_errors=True)
DATA.mkdir(parents=True, exist_ok=True)
os.environ["PERSONALTOOLS_DATA"] = str(DATA)
sys.path.insert(0, str(ROOT.parent / "app"))

from dev_image_stress import capture, find_hwnd  # noqa: E402

os.environ["PERSONALTOOLS_DATA"] = str(DATA)

import app as appmod  # noqa: E402

opened = []
webbrowser.open = lambda url, *a, **k: opened.append(url) or True

SHOT = ROOT / "_shots" / "feedback_ui.png"
SHOT.parent.mkdir(parents=True, exist_ok=True)
fails = []


def check(name, cond, detail=""):
    print(("PASS  " if cond else "FAIL  ") + name + (f"   {detail}" if detail else ""), flush=True)
    if not cond:
        fails.append(name)


def fetch_index(url):
    for key in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"):
        os.environ.pop(key, None)
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    return op.open(url, timeout=10).read().decode("utf-8")


def main():
    win, _ = appmod.build_window()
    pid = os.getpid()

    def work():
        try:
            time.sleep(3.2)
            js = win.evaluate_js

            check("服务端下发的页面里版本已是真值",
                  js("document.documentElement.innerHTML.includes('id=\"appVersion\">' + '" + appmod.VERSION + "')") is True,
                  appmod.VERSION)

            js("location.hash='#/settings'")
            time.sleep(1.2)
            js("document.querySelector('#setRail [data-set-tab=\"about\"]').click()")
            time.sleep(1.6)
            version = (js("(document.querySelector('#appVersion')||{}).textContent || ''") or "").strip()
            badge = (js("(document.querySelector('#aboutVersionBadge')||{}).textContent || ''") or "").strip()
            notes = (js("(document.querySelector('#releaseNotes')||{}).innerText || ''") or "").strip()
            check("关于页版本号是 1.0.3", version == "1.0.3", version)
            check("更新说明徽章是 v1.0.3", badge == "v1.0.3", badge)
            check("更新说明已刷新", "1.0.3" in notes, notes[:40])
            check("反馈按钮存在", js("!!document.querySelector('#feedbackBug')") is True)

            js("document.querySelector('#feedbackBug').click()")
            time.sleep(2.0)
            toast = (js("(document.querySelector('#toasts')||{}).innerText || ''") or "").strip()
            check("点了反馈有提示", "反馈页" in toast, toast)
            check("打开了反馈地址", bool(opened), str(opened[:1]))
            if opened:
                url = opened[0]
                check("地址是仓库的 issue 页", "github.com/HuaJiccc/practical-tools/issues/new" in url, url[:80])
                q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
                title = (q.get("title") or [""])[0]
                body = (q.get("body") or [""])[0]
                check("标题带版本号", "1.0.3" in title, title)
                check("正文带运行信息", "版本" in body and "数据目录" in body, body[:80].replace("\n", " | "))
                check("正文长度合理", 80 < len(body) <= 1600, str(len(body)))

            hwnd = find_hwnd(pid)
            if hwnd:
                capture(hwnd, str(SHOT))
        except Exception as exc:  # noqa: BLE001
            fails.append(f"异常：{type(exc).__name__}: {exc}")
            print("FAIL 异常:", exc, flush=True)
        finally:
            win.destroy()

    threading.Thread(target=work, daemon=True).start()
    import webview

    webview.start(debug=False)

    print("---")
    print("结果:", "全部通过" if not fails else f"{len(fails)} 项失败：{fails}", flush=True)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
