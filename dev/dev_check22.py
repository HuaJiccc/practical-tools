"""开发用：v2.2 新功能端到端自测（番茄钟 / 倒数日 / 世界时钟 / 心情 / 成图 / 全局搜索）。"""
from pathlib import Path as _P
_ROOT = _P(__file__).resolve().parent.parent

import ctypes
import ctypes.wintypes as wt
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("PERSONALTOOLS_DATA", str(_ROOT / "dev/_data"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

import webview  # noqa: E402
import app as appmod  # noqa: E402
from PIL import Image  # noqa: E402

SHOTS = (_ROOT / "dev/_shots/v22")
SHOTS.mkdir(parents=True, exist_ok=True)
report = {}


def find_hwnd(pid):
    user32 = ctypes.windll.user32
    result = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def cb(hwnd, lparam):
        p = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(p))
        if p.value == pid and user32.IsWindowVisible(hwnd):
            n = user32.GetWindowTextLengthW(hwnd)
            if n:
                buf = ctypes.create_unicode_buffer(n + 1)
                user32.GetWindowTextW(hwnd, buf, n + 1)
                if "个人工具" in buf.value:
                    result.append(hwnd)
        return True

    user32.EnumWindows(cb, 0)
    return result[0] if result else None


def capture(hwnd, path):
    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    rect = wt.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    w, h = rect.right - rect.left, rect.bottom - rect.top
    hdc = user32.GetWindowDC(hwnd)
    mdc = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    gdi32.SelectObject(mdc, bmp)
    user32.PrintWindow(hwnd, mdc, 2)

    class BMIH(ctypes.Structure):
        _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG),
                    ("biPlanes", wt.WORD), ("biBitCount", wt.WORD), ("biCompression", wt.DWORD),
                    ("biSizeImage", wt.DWORD), ("biXPelsPerMeter", wt.LONG),
                    ("biYPelsPerMeter", wt.LONG), ("biClrUsed", wt.DWORD), ("biClrImportant", wt.DWORD)]

    class BMI(ctypes.Structure):
        _fields_ = [("bmiHeader", BMIH), ("bmiColors", wt.DWORD * 3)]

    bi = BMI()
    bi.bmiHeader.biSize = ctypes.sizeof(BMIH)
    bi.bmiHeader.biWidth = w
    bi.bmiHeader.biHeight = -h
    bi.bmiHeader.biPlanes = 1
    bi.bmiHeader.biBitCount = 32
    bi.bmiHeader.biCompression = 0
    buf = ctypes.create_string_buffer(w * h * 4)
    gdi32.GetDIBits(mdc, bmp, 0, h, buf, ctypes.byref(bi), 0)
    Image.frombuffer("RGBA", (w, h), buf, "raw", "BGRA", 0, 1).convert("RGB").save(path)
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(mdc)
    user32.ReleaseDC(hwnd, hdc)


def run():
    win, settings = appmod.build_window()
    pid = os.getpid()

    def work():
        time.sleep(3.0)
        hwnd = find_hwnd(pid)
        if not hwnd:
            print("no hwnd")
            win.destroy()
            return
        js = win.evaluate_js
        errors = []

        # ---------- 番茄钟 ----------
        js("location.hash='#/time'")
        time.sleep(1.6)
        report["focus_initial"] = js("document.getElementById('focusTime').textContent")
        js("document.getElementById('focusStart').click()")
        time.sleep(2.4)
        report["focus_running"] = js("document.getElementById('focusTime').textContent")
        report["focus_btn"] = js("document.querySelector('#focusStart span').textContent")
        report["focus_ring"] = js("document.getElementById('focusRing').style.strokeDashoffset")
        js("document.getElementById('focusLabel').value='写周报'; document.getElementById('focusLabel').dispatchEvent(new Event('input'))")
        js("document.getElementById('focusStart').click()")
        time.sleep(0.6)
        report["focus_paused"] = js("document.getElementById('focusTime').textContent")
        report["focus_paused_btn"] = js("document.querySelector('#focusStart span').textContent")
        js("document.getElementById('focusReset').click()")
        time.sleep(0.4)
        report["focus_reset"] = js("document.getElementById('focusTime').textContent")
        report["focus_stats_text"] = js("document.getElementById('focusStats').innerText.replace(/\\n/g,' | ')")
        capture(hwnd, str(SHOTS / "time_focus.png"))

        # ---------- 倒数日 ----------
        js("document.querySelector('#timeTabs [data-tab=\"countdown\"]').click()")
        time.sleep(1.0)
        js("document.getElementById('cdAdd').click()")
        time.sleep(0.6)
        js("document.getElementById('cdTitle').value='项目上线'; document.getElementById('cdDate').value='2026-12-01'")
        js("document.querySelector('#modalRoot [data-ok]').click()")
        time.sleep(1.2)
        js("document.getElementById('cdAdd').click()")
        time.sleep(0.5)
        js("document.getElementById('cdTitle').value='妈妈生日'; document.getElementById('cdDate').value='2026-03-18'; document.getElementById('cdRepeat').value='year'")
        js("document.querySelector('#modalRoot [data-ok]').click()")
        time.sleep(1.2)
        report["cd_items"] = js("JSON.stringify([...document.querySelectorAll('.cd-item')].map(el=>el.innerText.replace(/\\n/g,' | ')))")
        capture(hwnd, str(SHOTS / "time_countdown.png"))

        # ---------- 世界时钟 ----------
        js("document.querySelector('#timeTabs [data-tab=\"world\"]').click()")
        time.sleep(1.4)
        report["world_cards"] = js("document.querySelectorAll('.world-city').length")
        report["world_first"] = js("document.querySelector('.world-city').innerText.replace(/\\n/g,' | ')")
        js("document.getElementById('worldInput').value='悉尼'; document.getElementById('worldAdd').click()")
        time.sleep(1.0)
        report["world_after_add"] = js("document.querySelectorAll('.world-city').length")
        report["world_all"] = js("JSON.stringify([...document.querySelectorAll('.world-city')].map(el=>el.dataset.tz))")
        capture(hwnd, str(SHOTS / "time_world.png"))

        # ---------- 心情日记 ----------
        js("location.hash='#/mood'")
        time.sleep(1.6)
        report["mood_title"] = js("document.getElementById('moodTitle').textContent")
        js("document.querySelectorAll('[data-mood-pick]')[3].click()")
        js("document.getElementById('moodText').value='今天把番茄钟调通了'; document.getElementById('moodText').dispatchEvent(new Event('input'))")
        js("document.getElementById('moodSave').click()")
        time.sleep(1.4)
        report["mood_emoji"] = js("document.querySelector('.mood-day.sel .m-emoji') ? document.querySelector('.mood-day.sel .m-emoji').textContent : null")
        report["mood_stats"] = js("document.getElementById('moodStats').innerText.replace(/\\n/g,' | ')")
        report["mood_recent"] = js("document.getElementById('moodRecent').innerText.replace(/\\n/g,' | ')")
        capture(hwnd, str(SHOTS / "mood.png"))

        # ---------- 数据成图 ----------
        js("location.hash='#/chart'")
        time.sleep(1.4)
        js("document.getElementById('chartSample').click()")
        time.sleep(0.8)
        report["chart_parse"] = js("document.getElementById('chartParse').textContent")
        report["chart_meta"] = js("document.getElementById('chartMeta').textContent")
        report["chart_rects"] = js("document.querySelectorAll('#chartCanvas rect').length")
        report["chart_title"] = js("document.getElementById('chartTitle').textContent")
        capture(hwnd, str(SHOTS / "chart_bar.png"))
        js("document.querySelector('#chartTypes [data-type=\"line\"]').click()")
        time.sleep(0.8)
        report["chart_lines"] = js("document.querySelectorAll('#chartCanvas polyline').length")
        capture(hwnd, str(SHOTS / "chart_line.png"))
        js("document.querySelector('#chartTypes [data-type=\"donut\"]').click()")
        time.sleep(0.8)
        report["chart_donut_paths"] = js("document.querySelectorAll('#chartCanvas path').length")

        # ---------- 全局搜索 ----------
        js("document.dispatchEvent(new KeyboardEvent('keydown', {key:'k', ctrlKey:true, bubbles:true}))")
        time.sleep(0.5)
        report["cmd_open"] = js("document.getElementById('cmdRoot').classList.contains('open')")
        js("const i=document.getElementById('cmdInput'); i.value='周'; i.dispatchEvent(new Event('input'))")
        time.sleep(1.2)
        report["cmd_rows"] = js("document.querySelectorAll('.cmd-row').length")
        report["cmd_groups"] = js("JSON.stringify([...document.querySelectorAll('.cmd-group')].map(e=>e.textContent))")
        report["cmd_first"] = js("document.querySelector('.cmd-row') ? document.querySelector('.cmd-row').innerText.replace(/\\n/g,' | ') : null")
        capture(hwnd, str(SHOTS / "search.png"))
        js("document.getElementById('cmdInput').dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowDown',bubbles:true}))")
        time.sleep(0.3)
        report["cmd_selected"] = js("document.querySelectorAll('.cmd-row.on').length")
        js("document.getElementById('cmdInput').dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true}))")
        time.sleep(1.2)
        report["cmd_closed"] = js("!document.getElementById('cmdRoot').classList.contains('open')")
        report["cmd_page"] = js("location.hash")

        report["js_errors"] = js("JSON.stringify(window.__errs || [])")
        (SHOTS / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        win.destroy()

    webview.start(
        gui="edgechromium",
        debug=False,
        private_mode=False,
        storage_path=str(Path(os.environ["PERSONALTOOLS_DATA"]) / "webview"),
        func=work,
    )


if __name__ == "__main__":
    run()
