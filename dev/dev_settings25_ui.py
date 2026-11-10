"""v2.5 设置页界面自测：六个分类逐个点开、截图，并验证新设置的联动效果。"""
import json
import os
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "_data_setui"
shutil.rmtree(DATA, ignore_errors=True)
DATA.mkdir(parents=True, exist_ok=True)
os.environ["PERSONALTOOLS_DATA"] = str(DATA)
sys.path.insert(0, str(ROOT.parent / "app"))

from dev_image_stress import capture, find_hwnd  # noqa: E402  （这个模块会改数据目录）

os.environ["PERSONALTOOLS_DATA"] = str(DATA)

import webview  # noqa: E402
import app as appmod  # noqa: E402

SHOTS = ROOT / "_shots" / "v25"
SHOTS.mkdir(parents=True, exist_ok=True)

TABS = ["look", "general", "trans", "ai", "data", "about"]
report = {}
fails = []


def check(name, cond, detail=""):
    report[name] = detail if detail else bool(cond)
    print(("PASS  " if cond else "FAIL  ") + name + (f"   {detail}" if detail else ""), flush=True)
    if not cond:
        fails.append(name)


def main():
    # 造点数据，占用统计才不空
    (DATA / "notes.json").write_text(json.dumps([{"id": "n1", "text": "x" * 900}]), "utf-8")
    exp = DATA / "exports"
    exp.mkdir(parents=True, exist_ok=True)
    (exp / "demo.png").write_bytes(b"\x89PNG" + b"0" * 3000)

    win, _ = appmod.build_window()
    pid = os.getpid()

    def work():
        try:
            time.sleep(3.0)
            hwnd = find_hwnd(pid)
            js = win.evaluate_js

            js("localStorage.setItem('personal-tools.prefs', JSON.stringify({theme:'light', accent:'blue', density:'normal', motion:'on'}))")
            js("location.reload()")
            time.sleep(3.0)
            js("localStorage.setItem('personal-tools.prefs', JSON.stringify({theme:'light', accent:'blue', density:'normal', motion:'on'}))")
            js("location.hash='#/settings'")
            time.sleep(1.4)
            js("document.querySelector('#toasts').innerHTML=''")

            check("侧栏 6 个分类", js("document.querySelectorAll('#setRail .set-tab').length") == 6,
                  str(js("document.querySelectorAll('#setRail .set-tab').length")))
            check("6 个面板", js("document.querySelectorAll('.set-pane').length") == 6,
                  str(js("document.querySelectorAll('.set-pane').length")))

            for i, tab in enumerate(TABS):
                js(f"document.querySelector('#setRail [data-set-tab=\"{tab}\"]').click()")
                time.sleep(0.7)
                visible = js(f"(document.querySelector('.set-pane[data-set-pane=\"{tab}\"]').offsetParent !== null)")
                check(f"分类 {tab} 可见", visible is True or visible is not False and visible,
                      f"offsetParent={visible}")
                js("document.querySelector('#toasts').innerHTML=''")
                if tab in ("look", "general", "ai", "data", "about"):
                    time.sleep(0.4)
                    capture(hwnd, str(SHOTS / f"set_{i}_{tab}.png"))

            # ---- 外观：密度 / 动效 ----
            js("document.querySelector('#setRail [data-set-tab=\"look\"]').click()")
            time.sleep(0.4)
            pad_before = js("getComputedStyle(document.querySelector('[data-set-pane=\"look\"] .setting-row')).paddingTop")
            js("document.querySelector('#densitySeg [data-density=\"compact\"]').click()")
            time.sleep(0.5)
            pad_after = js("getComputedStyle(document.querySelector('[data-set-pane=\"look\"] .setting-row')).paddingTop")
            check("紧凑模式变紧", pad_before != pad_after, f"{pad_before} -> {pad_after}")
            check("密度写进 html", js("document.documentElement.dataset.density") == "compact")
            check("密度已存盘", "compact" in js("localStorage.getItem('personal-tools.prefs')"))

            js("document.querySelector('#motionSwitch').click()")
            time.sleep(0.4)
            check("动效开关写进 html", js("document.documentElement.dataset.motion") == "off")
            js("document.querySelector('#motionSwitch').click()")
            time.sleep(0.3)
            check("动效可以开回来", js("document.documentElement.dataset.motion") == "on")
            js("document.querySelector('#densitySeg [data-density=\"normal\"]').click()")
            time.sleep(0.3)

            # ---- 通用：启动页 / 开机自启 ----
            js("document.querySelector('#setRail [data-set-tab=\"general\"]').click()")
            time.sleep(0.6)
            opts = js("Array.from(document.querySelectorAll('#startPage option')).map(o=>o.value).join(',')")
            check("启动页选项完整", opts.count(",") >= 8, opts)
            js("const s=document.querySelector('#startPage'); s.value='plan'; s.dispatchEvent(new Event('change'))")
            time.sleep(0.4)
            check("启动页存进 prefs", '"startPage":"plan"' in js("localStorage.getItem('personal-tools.prefs')"),
                  js("localStorage.getItem('personal-tools.prefs')"))
            auto = js("document.querySelector('#autoStartSwitch').classList.contains('on')")
            check("自启开关有状态", auto in (True, False), str(auto))
            js("document.querySelector('#maxSwitch').click()")
            time.sleep(0.6)
            check("最大化开关可切换", js("document.querySelector('#maxSwitch').classList.contains('on')") is True)
            js("document.querySelector('#maxSwitch').click()")
            time.sleep(0.5)

            # ---- 翻译：延迟档位 ----
            js("document.querySelector('#setRail [data-set-tab=\"trans\"]').click()")
            time.sleep(0.6)
            check("延迟有 4 档", js("document.querySelectorAll('#delaySeg button').length") == 4)
            check("默认选中 0.9s", js("document.querySelector('#delaySeg .active') && document.querySelector('#delaySeg .active').dataset.delay") == "900",
                  str(js("document.querySelector('#delaySeg .active') && document.querySelector('#delaySeg .active').dataset.delay")))
            js("document.querySelector('#delaySeg [data-delay=\"1500\"]').click()")
            time.sleep(0.8)
            check("延迟改成 1.5s", js("document.querySelector('#delaySeg .active').dataset.delay") == "1500",
                  str(js("document.querySelector('#delaySeg .active').dataset.delay")))
            js("document.querySelector('#toasts').innerHTML=''")
            capture(hwnd, str(SHOTS / "set_trans.png"))
            js("document.querySelector('#delaySeg [data-delay=\"900\"]').click()")
            time.sleep(0.6)

            # ---- 数据：占用统计 ----
            js("document.querySelector('#setRail [data-set-tab=\"data\"]').click()")
            time.sleep(1.6)
            usage = js("document.querySelector('#dataUsage').textContent")
            check("占用统计有结果", ("共" in usage) and ("统计失败" not in usage), usage)
            export_path = js("document.querySelector('#exportPath').textContent")
            check("导出目录已填", export_path not in ("—", ""), export_path)
            chips = js("document.querySelectorAll('#usageList .usage-chip').length")
            check("占用明细有条目", chips >= 1, f"{chips} 条")
            js("document.querySelector('#toasts').innerHTML=''")
            capture(hwnd, str(SHOTS / "set_data.png"))

            # ---- 关于：诊断信息 ----
            js("document.querySelector('#setRail [data-set-tab=\"about\"]').click()")
            time.sleep(1.4)
            diag = js("document.querySelector('#diagBox').textContent")
            check("诊断信息已填", "WebView2" in diag and "版本" in diag, diag.replace("\n", " | ")[:60])
            check("诊断可复制文本", js("document.querySelector('#diagBox').dataset.text").count("：") >= 6,
                  str(js("document.querySelector('#diagBox').dataset.text")[:40]))
            check("版本号已填", js("document.querySelector('#appVersion').textContent") not in ("", "2.0.0"),
                  js("document.querySelector('#appVersion').textContent"))

            # ---- 深色看一遍 ----
            js("document.documentElement.dataset.theme='dark'")
            js("document.querySelector('#setRail [data-set-tab=\"look\"]').click()")
            time.sleep(0.8)
            js("document.querySelector('#toasts').innerHTML=''")
            capture(hwnd, str(SHOTS / "set_look_dark.png"))
            js("document.querySelector('#setRail [data-set-tab=\"general\"]').click()")
            time.sleep(0.6)
            js("document.querySelector('#toasts').innerHTML=''")
            capture(hwnd, str(SHOTS / "set_general_dark.png"))

            errs = js("JSON.stringify(window.__errs||[])")
            check("无 JS 报错", errs in ("[]", ""), errs)

            # 还原偏好，避免污染源码运行环境
            js("localStorage.setItem('personal-tools.prefs', JSON.stringify({theme:'light', accent:'blue'}))")
        except Exception:
            import traceback
            report["exception"] = traceback.format_exc()
            print(traceback.format_exc(), flush=True)
        finally:
            try:
                win.destroy()
            except Exception:
                pass

    import threading
    threading.Thread(target=work, daemon=True).start()
    webview.start(debug=False)
    print()
    print(f"失败 {len(fails)} 项：{fails}" if fails else "全部通过")
    print(json.dumps({"fails": fails}, ensure_ascii=False))


if __name__ == "__main__":
    main()
