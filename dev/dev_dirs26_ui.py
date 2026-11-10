"""v2.6 存储位置界面自测：两个目录的路径、徽章、按钮渲染是否正常。

不点「更改」——那会弹系统目录框，自动化会卡在那里。切换逻辑由 dev_dirs26.py 覆盖。
"""
import json
import os
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "_data_dirsui"
shutil.rmtree(DATA, ignore_errors=True)
DATA.mkdir(parents=True, exist_ok=True)
os.environ["PERSONALTOOLS_DATA"] = str(DATA)
sys.path.insert(0, str(ROOT.parent / "app"))

from dev_image_stress import capture, find_hwnd  # noqa: E402  （这个模块会改数据目录）

os.environ["PERSONALTOOLS_DATA"] = str(DATA)

import app as appmod  # noqa: E402

SHOTS = ROOT / "_shots" / "v26"
SHOTS.mkdir(parents=True, exist_ok=True)

fails = []


def check(name, cond, detail=""):
    print(("PASS  " if cond else "FAIL  ") + name + (f"   {detail}" if detail else ""), flush=True)
    if not cond:
        fails.append(name)


def main():
    (DATA / "notes.json").write_text(json.dumps([{"id": "n1", "text": "x" * 400}]), "utf-8")
    exp = DATA / "exports"
    exp.mkdir(parents=True, exist_ok=True)
    (exp / "demo.png").write_bytes(b"\x89PNG" + b"0" * 2000)

    win, _ = appmod.build_window()
    pid = os.getpid()

    def work():
        try:
            time.sleep(3.0)
            hwnd = find_hwnd(pid)
            js = win.evaluate_js

            js("location.hash='#/settings'")
            time.sleep(1.4)
            js("document.querySelector('#setRail [data-set-tab=\"data\"]').click()")
            time.sleep(1.2)
            js("document.querySelector('#toasts').innerHTML=''")

            data_path = js("(document.querySelector('#dataPath')||{}).textContent || ''").strip()
            export_path = js("(document.querySelector('#exportPath')||{}).textContent || ''").strip()
            check("数据目录显示真实路径", bool(data_path) and data_path != "—", data_path)
            check("图片目录显示真实路径", bool(export_path) and export_path != "—", export_path)
            check("数据路径是绝对路径", bool(data_path) and len(data_path) > 3 and data_path[1] == ":", data_path)
            check("图片路径在数据目录下", export_path.lower().startswith(data_path.lower()), export_path)

            check("两个徽章都显示默认",
                  js("(document.querySelector('#dataBadge')||{}).textContent || ''").strip() == "默认"
                  and js("(document.querySelector('#exportBadge')||{}).textContent || ''").strip() == "默认")
            check("说明文字在", "都存在这里" in js("(document.querySelector('#dataHint')||{}).textContent || ''"))
            check("恢复默认按钮默认隐藏",
                  js("document.querySelector('#resetData').hidden === true && document.querySelector('#resetExport').hidden === true") is True)

            check("更改按钮齐全",
                  js("!!document.querySelector('#moveData') && !!document.querySelector('#moveExport')") is True)
            check("打开按钮齐全",
                  js("!!document.querySelector('#openData') && !!document.querySelector('#openExports')") is True)
            check("按钮确实绑了事件",
                  js("document.querySelector('#moveData').onclick !== null && document.querySelector('#moveExport').onclick !== null") is True)

            # 路径用省略号截断，不能把行撑破
            check("数据路径不横向溢出",
                  js("(()=>{const e=document.querySelector('#dataPath');return e.scrollWidth<=e.clientWidth+1})()") is True)
            check("设置行没超出卡片",
                  js("(()=>{const card=document.querySelector('.set-pane[data-set-pane=\"data\"] .panel');"
                     "const row=card.querySelectorAll('.setting-row')[0];"
                     "return row.getBoundingClientRect().right <= card.getBoundingClientRect().right+1})()") is True)

            capture(hwnd, str(SHOTS / "dirs_wide.png"))

            # 窄窗口：按钮不能把文字挤断
            win.resize(1000, 720)
            time.sleep(1.2)
            check("窄窗口下路径仍不溢出",
                  js("(()=>{const e=document.querySelector('#exportPath');return e.scrollWidth<=e.clientWidth+1})()") is True)
            check("窄窗口下按钮仍可见",
                  js("(()=>{const b=document.querySelector('#moveExport');const r=b.getBoundingClientRect();return r.width>20&&r.height>10})()") is True)
            capture(hwnd, str(SHOTS / "dirs_narrow.png"))

            errs = js("JSON.stringify(window.__errs||[])")
            check("无 JS 报错", errs in ("[]", ""), errs)
        except Exception:
            import traceback

            print(traceback.format_exc(), flush=True)
            fails.append("exception")
        finally:
            try:
                win.destroy()
            except Exception:
                pass

    import threading

    threading.Thread(target=work, daemon=True).start()
    import webview

    webview.start(debug=False)
    print()
    print(f"失败 {len(fails)} 项：{fails}" if fails else "全部通过")


if __name__ == "__main__":
    main()
