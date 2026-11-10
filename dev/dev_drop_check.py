"""开发用：数据成图「拖入 Excel」端到端验证（真实 drop 事件 + 真实 xlsx 字节）。"""
import base64
import ctypes
import ctypes.wintypes as wt
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ["PERSONALTOOLS_DATA"] = str(ROOT / "_data_drop")
sys.path.insert(0, str(ROOT.parent / "app"))

import webview  # noqa: E402
import app as appmod  # noqa: E402
from PIL import Image  # noqa: E402

SHOTS = ROOT / "_shots" / "v22"
SHOTS.mkdir(parents=True, exist_ok=True)
XLSX = ROOT / "_data" / "销售报表.xlsx"
CSV = ROOT / "_data" / "区域.csv"
CSV.write_text('区域,金额,备注\n华北,320,"北京, 天津"\n华东,410,"上海、杭州"\n华南,280,"广州"\n', encoding="utf-8")
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
    if not result:
        return None

    def area(hwnd):
        r = wt.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(r))
        return (r.right - r.left) * (r.bottom - r.top)

    return max(result, key=area)


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


DRAG_JS = """
(function(b64, name, mime){
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i += 1) bytes[i] = bin.charCodeAt(i);
  const file = new File([bytes], name, { type: mime });
  const dt = new DataTransfer();
  dt.items.add(file);
  const page = document.querySelector('[data-page="chart"]');
  ['dragenter', 'dragover'].forEach((type) => {
    const ev = new Event(type, { bubbles: true, cancelable: true });
    Object.defineProperty(ev, 'dataTransfer', { value: dt });
    page.dispatchEvent(ev);
  });
  window.__dt = dt;
  return 'dragged';
})(%s, %s, %s)
"""

DROP_JS = """
(function(){
  const page = document.querySelector('[data-page="chart"]');
  const dropped = new Event('drop', { bubbles: true, cancelable: true });
  Object.defineProperty(dropped, 'dataTransfer', { value: window.__dt });
  page.dispatchEvent(dropped);
  return 'dispatched';
})()
"""


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

        js("location.hash='#/chart'")
        time.sleep(1.5)
        report["mask_hidden"] = js("!document.getElementById('chartDrop').classList.contains('over')")

        # 模拟拖入 xlsx：先看悬停提示，再松手
        b64 = base64.b64encode(XLSX.read_bytes()).decode()
        js(DRAG_JS % (json.dumps(b64), json.dumps("销售报表.xlsx"),
                      json.dumps("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")))
        time.sleep(0.3)
        report["mask_after_dragenter"] = js("document.getElementById('chartDrop').classList.contains('over')")
        capture(hwnd, str(SHOTS / "chart_drop_mask.png"))
        js(DROP_JS)
        time.sleep(1.6)
        report["parse"] = js("document.getElementById('chartParse').textContent")
        report["filebar_shown"] = js("!document.getElementById('chartFilebar').hidden")
        report["filename"] = js("document.getElementById('chartFileName').textContent")
        report["fileinfo"] = js("document.getElementById('chartFileInfo').textContent")
        report["sheets"] = js("JSON.stringify([...document.querySelectorAll('#chartSheets button')].map(b=>b.textContent))")
        report["ta_lines"] = js("document.getElementById('chartInput').value.split('\\n').length")
        report["ta_first3"] = js("JSON.stringify(document.getElementById('chartInput').value.split('\\n').slice(0,3))")
        report["meta"] = js("document.getElementById('chartMeta').textContent")
        report["rects"] = js("document.querySelectorAll('#chartCanvas rect').length")
        capture(hwnd, str(SHOTS / "chart_drop_xlsx.png"))

        # 切到第二个工作表
        js("document.querySelectorAll('#chartSheets button')[1].click()")
        time.sleep(1.2)
        report["sheet2_parse"] = js("document.getElementById('chartParse').textContent")
        report["sheet2_meta"] = js("document.getElementById('chartMeta').textContent")
        report["sheet2_first"] = js("JSON.stringify(document.getElementById('chartInput').value.split('\\n')[0])")
        capture(hwnd, str(SHOTS / "chart_drop_sheet2.png"))

        # 拖入 CSV（带引号里含逗号）
        js("location.hash='#/home'")
        time.sleep(0.4)
        js("location.hash='#/chart'")
        time.sleep(1.0)
        b64 = base64.b64encode(CSV.read_bytes()).decode()
        js(DRAG_JS % (json.dumps(b64), json.dumps("区域.csv"), json.dumps("text/csv")))
        time.sleep(0.2)
        js(DROP_JS)
        time.sleep(1.4)
        report["csv_parse"] = js("document.getElementById('chartParse').textContent")
        report["csv_first2"] = js("JSON.stringify(document.getElementById('chartInput').value.split('\\n').slice(0,3))")
        report["csv_meta"] = js("document.getElementById('chartMeta').textContent")

        # 200 行的大表：应截到 61 行（表头 + 60）并正常渲染
        js("location.hash='#/home'")
        time.sleep(0.4)
        js("location.hash='#/chart'")
        time.sleep(1.0)
        big = ROOT / "_data" / "大表.xlsx"
        b64 = base64.b64encode(big.read_bytes()).decode()
        js(DRAG_JS % (json.dumps(b64), json.dumps("大表.xlsx"),
                      json.dumps("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")))
        time.sleep(0.2)
        js(DROP_JS)
        time.sleep(1.8)
        report["big_lines"] = js("document.getElementById('chartInput').value.split('\\n').length")
        report["big_info"] = js("document.getElementById('chartFileInfo').textContent")
        report["big_parse"] = js("document.getElementById('chartParse').textContent")
        report["big_rects"] = js("document.querySelectorAll('#chartCanvas rect').length")
        capture(hwnd, str(SHOTS / "chart_drop_big.png"))

        # 清空
        js("document.getElementById('chartClear').click()")
        time.sleep(0.6)
        report["after_clear_bar"] = js("document.getElementById('chartFilebar').hidden")
        report["after_clear_parse"] = js("document.getElementById('chartParse').textContent")

        # 深色主题下再看一眼文件栏
        js("location.hash='#/settings'")
        time.sleep(1.0)
        js("document.querySelector('#themeSeg button[data-theme=\"dark\"]').click()")
        time.sleep(0.8)
        js("location.hash='#/chart'")
        time.sleep(1.0)
        b64 = base64.b64encode(XLSX.read_bytes()).decode()
        js(DRAG_JS % (json.dumps(b64), json.dumps("销售报表.xlsx"),
                      json.dumps("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")))
        time.sleep(0.2)
        js(DROP_JS)
        time.sleep(1.5)
        capture(hwnd, str(SHOTS / "chart_drop_dark.png"))
        js("location.hash='#/settings'")
        time.sleep(0.8)
        js("document.querySelector('#themeSeg button[data-theme=\"light\"]').click()")
        time.sleep(0.6)

        report["errors"] = js("JSON.stringify(window.__errs || [])")

        (SHOTS / "report_drop.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
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
