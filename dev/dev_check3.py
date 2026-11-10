"""v2.1 新功能自测：每日规划 / 待办时间 / 轮盘 / 笔记分类。"""
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("PERSONALTOOLS_DATA", str(Path(__file__).resolve().parent / "_data"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

import webview  # noqa: E402
import app as appmod  # noqa: E402

OUT = Path(__file__).resolve().parent / "_shots"
OUT.mkdir(parents=True, exist_ok=True)
report = {}


def run_js(win, code, wait=0.45):
    result = win.evaluate_js(code)
    time.sleep(wait)
    return result


def work():
    time.sleep(3.2)
    win = webview.windows[0]
    win.evaluate_js("window.__errs = window.__errs || []")

    def shot(name):
        win.evaluate_js("1")
        from PIL import ImageGrab  # noqa: F401  (仅占位，实际用 PrintWindow)
        capture(win, OUT / f"{name}.png")

    # ---------- 记事本分类 ----------
    run_js(win, "location.hash='#/notes'", 1.2)
    run_js(win, "document.querySelector('#noteNew').click()", 1.0)
    run_js(win, "document.querySelector('#noteBody').value='周会记录\\n下周三讨论新版本排期';"
                "document.querySelector('#noteBody').dispatchEvent(new Event('input'))", 1.4)
    run_js(win, "document.querySelector('[data-note=\"category\"]').click()", 0.7)
    run_js(win, "document.querySelector('#noteCatPick [data-cat=\"work\"]').click()", 1.0)
    report["noteCatLabel"] = run_js(win, "document.querySelector('#noteCatLabel').textContent")
    report["noteCatBadge"] = run_js(win, "document.querySelector('#noteList .note-cat').textContent.trim()")
    run_js(win, "document.querySelectorAll('#noteCats [data-note-cat]')[1].click()", 0.7)  # 工作
    report["noteFilterWork"] = run_js(win, "document.querySelectorAll('#noteList [data-note-id]').length")
    run_js(win, "document.querySelectorAll('#noteCats [data-note-cat]')[4].click()", 0.7)  # 灵感
    report["noteFilterIdea"] = run_js(win, "document.querySelectorAll('#noteList [data-note-id]').length")
    report["noteIdeaEmpty"] = run_js(win, "document.querySelector('#noteList .empty p').textContent")
    run_js(win, "document.querySelectorAll('#noteCats [data-note-cat]')[0].click()", 0.7)

    # ---------- 待办：手动选时间 ----------
    run_js(win, "location.hash='#/todo'", 1.2)
    run_js(win, "document.querySelector('#todoWhen').click()", 0.8)
    run_js(win, "document.querySelectorAll('#dtDates [data-date]')[1].click()", 0.3)
    run_js(win, "document.querySelector('#dtTimes [data-time=\"14:00\"]').click()", 0.3)
    report["dtActive"] = run_js(win, "document.querySelector('#dtTimes .dt-chip.active').textContent")
    run_js(win, "document.querySelector('#modalRoot [data-ok]').click()", 0.8)
    report["whenLabel"] = run_js(win, "document.querySelector('#todoWhenLabel').textContent")

    run_js(win, "document.querySelector('#todoInput').value='手动时间测试任务';"
                "document.querySelector('#todoAdd').click()", 2.0)
    run_js(win, "document.querySelector('#todoTabs [data-view=\"all\"]').click()", 1.2)
    report["todoGroups"] = run_js(win, "Array.from(document.querySelectorAll('.todo-section-label')).map(e=>e.textContent)")
    report["todoDue"] = run_js(win, "document.querySelector('#todoList .todo-meta').textContent.trim()")

    # 编辑弹层
    run_js(win, "document.querySelector('#todoList [data-todo-act=\"edit\"]').click()", 0.9)
    report["editorFields"] = run_js(win, "Array.from(document.querySelectorAll('#edDate,#edTime,#edRemind')).map(e=>e.value)")
    run_js(win, "document.querySelectorAll('#edDate ~ .dt-chips [data-off]')[2].click()", 0.4)  # 后天
    run_js(win, "var s=document.querySelector('#edRemind'); s.value='15'; s.dispatchEvent(new Event('change'))", 0.3)
    run_js(win, "document.querySelector('.modal [data-ok]').click()", 1.6)
    report["todoAfterEdit"] = run_js(win, "document.querySelector('#todoList .todo-meta').textContent.trim()")

    # ---------- 每日规划 ----------
    run_js(win, "location.hash='#/plan'", 1.4)
    run_js(win, "document.querySelector('#planAdd').click()", 0.8)
    run_js(win, "document.querySelector('#plTitle').value='写周报';"
                "document.querySelector('#plStart').value='09:00';"
                "document.querySelector('#plEnd').value='10:30';"
                "document.querySelector('#plCats [data-cat=\"work\"]').click()", 0.5)
    run_js(win, "document.querySelector('.modal [data-ok]').click()", 1.4)

    run_js(win, "document.querySelector('#planAdd').click()", 0.8)
    run_js(win, "document.querySelector('#plTitle').value='和设计对齐';"
                "document.querySelector('#plStart').value='09:30';"
                "document.querySelector('#plEnd').value='10:00';"
                "document.querySelector('#plCats [data-cat=\"life\"]').click()", 0.5)
    run_js(win, "document.querySelector('.modal [data-ok]').click()", 1.4)

    report["planBlocks"] = run_js(win, "document.querySelectorAll('#planBody .plan-block').length")
    report["planCols"] = run_js(win, "Array.from(document.querySelectorAll('#planBody .plan-block')).map(e=>e.style.width)")
    report["planStat"] = run_js(win, "document.querySelector('#planStat').textContent")
    report["planLegend"] = run_js(win, "document.querySelectorAll('#planCats li').length")
    shot("plan_filled")

    # 勾完成
    run_js(win, "document.querySelector('#planList [data-plan-toggle]').click()", 1.4)
    report["planStatAfterDone"] = run_js(win, "document.querySelector('#planStat').textContent")
    report["planDoneBlocks"] = run_js(win, "document.querySelectorAll('#planBody .plan-block.done').length")

    # 前一天 / 回到今天
    run_js(win, "document.querySelector('#planPrev').click()", 1.2)
    report["planPrevSub"] = run_js(win, "document.querySelector('#planDateSub').textContent")
    report["planPrevBlocks"] = run_js(win, "document.querySelectorAll('#planBody .plan-block').length")
    run_js(win, "document.querySelector('#planTodayBtn').click()", 1.2)
    report["planBackBlocks"] = run_js(win, "document.querySelectorAll('#planBody .plan-block').length")

    # 导入待办（今天没有带时间的待办，应给出提示）
    run_js(win, "document.querySelector('#planFromTodo').click()", 1.6)
    report["planToast"] = run_js(win, "document.querySelector('.toast span') ? document.querySelector('.toast span').textContent : ''")

    # ---------- 轮盘 ----------
    run_js(win, "location.hash='#/picker'", 1.2)
    for name in ("面馆", "火锅", "寿司", "快餐"):
        run_js(win, f"document.querySelector('#pickInput').value='{name}';"
                    "document.querySelector('#pickAdd').click()", 0.7)
    report["wheelSlices"] = run_js(win, "document.querySelectorAll('#pickWheel path').length")
    report["wheelLabels"] = run_js(win, "document.querySelectorAll('#pickWheel text').length")
    shot("wheel")

    run_js(win, "document.querySelector('#pickSpin').click()", 0.3)
    report["spinState"] = run_js(win, "document.querySelector('#pickResult').textContent")
    time.sleep(4.6)
    report["spinResult"] = run_js(win, "document.querySelector('#pickResult').textContent")
    report["spinHistory"] = run_js(win, "document.querySelectorAll('#pickHistory li').length")
    report["wheelTransform"] = run_js(win, "document.querySelector('#pickWheel').style.transform")
    shot("wheel_result")

    # 列表模式
    run_js(win, "document.querySelector('#pickMode [data-mode=\"list\"]').click()", 0.6)
    report["listMode"] = run_js(win, "getComputedStyle(document.querySelector('#wheelWrap')).display")
    run_js(win, "document.querySelector('#pickMode [data-mode=\"wheel\"]').click()", 0.5)

    # ---------- 截图其余页面 ----------
    run_js(win, "location.hash='#/notes'", 1.2)
    shot("notes_cat")
    run_js(win, "location.hash='#/todo'", 1.2)
    shot("todo_time")

    report["errors"] = win.evaluate_js("window.__errs || []")
    win.destroy()


def capture(win, path):
    import ctypes
    import ctypes.wintypes as wt
    from PIL import Image

    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    hwnd = None
    pid = os.getpid()

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def cb(h, _):
        p = wt.DWORD()
        user32.GetWindowThreadProcessId(h, ctypes.byref(p))
        if p.value == pid and user32.IsWindowVisible(h):
            n = user32.GetWindowTextLengthW(h)
            if n:
                buf = ctypes.create_unicode_buffer(n + 1)
                user32.GetWindowTextW(h, buf, n + 1)
                if "个人工具" in buf.value:
                    found.append(h)
        return True

    found = []
    user32.EnumWindows(cb, 0)
    if not found:
        return
    hwnd = found[0]
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
    buf = ctypes.create_string_buffer(w * h * 4)
    gdi32.GetDIBits(mdc, bmp, 0, h, buf, ctypes.byref(bi), 0)
    Image.frombuffer("RGBA", (w, h), buf, "raw", "BGRA", 0, 1).convert("RGB").save(path)
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(mdc)
    user32.ReleaseDC(hwnd, hdc)


window, settings = appmod.build_window()
webview.start(gui="edgechromium", debug=False, private_mode=False,
              storage_path=str(Path(os.environ["PERSONALTOOLS_DATA"]) / "webview"), func=work)
print(json.dumps(report, ensure_ascii=False, indent=1))
