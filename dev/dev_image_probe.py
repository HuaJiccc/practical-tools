"""开发用：图片工具（证件照 / 视频转 GIF / 压缩图片）冒烟测试。

跑一遍完整链路，输出关键断言，确认页面、拖放、编码、保存都能走通。
"""
import base64
import ctypes
import ctypes.wintypes as wt
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "_data_img"
os.environ["PERSONALTOOLS_DATA"] = str(DATA)
DATA.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT.parent / "app"))

import webview  # noqa: E402
import app as appmod  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

SHOTS = ROOT / "_shots" / "v23"
SHOTS.mkdir(parents=True, exist_ok=True)
report = {}


def make_portrait(path, w, h, bg, shirt=(66, 88, 128)):
    im = Image.new("RGB", (w, h), bg)
    d = ImageDraw.Draw(im)
    d.ellipse([w * 0.08, h * 0.60, w * 0.92, h * 1.45], fill=shirt)
    d.rectangle([w * 0.42, h * 0.48, w * 0.58, h * 0.74], fill=(232, 196, 168))
    d.ellipse([w * 0.30, h * 0.14, w * 0.70, h * 0.60], fill=(238, 205, 180))
    d.ellipse([w * 0.29, h * 0.11, w * 0.71, h * 0.39], fill=(42, 34, 30))
    d.ellipse([w * 0.38, h * 0.30, w * 0.44, h * 0.34], fill=(40, 40, 40))
    d.ellipse([w * 0.56, h * 0.30, w * 0.62, h * 0.34], fill=(40, 40, 40))
    im.save(path, quality=93)
    return path


def make_photo(path, w, h):
    im = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(im)
    for y in range(h):
        d.line([(0, y), (w, y)], fill=(30 + y * 120 // h, 90, 200 - y * 100 // h))
    for x in range(0, w, 37):
        d.line([(x, 0), (x + 200, h)], fill=(200, 120, 60), width=3)
    im.save(path, quality=96)
    return path


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


DROP_JS = """
(function(b64, name, mime, zone){
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i += 1) bytes[i] = bin.charCodeAt(i);
  const file = new File([bytes], name, { type: mime });
  const dt = new DataTransfer();
  dt.items.add(file);
  const target = document.querySelector(zone);
  const ev = new Event('drop', { bubbles: true, cancelable: true });
  Object.defineProperty(ev, 'dataTransfer', { value: dt });
  target.dispatchEvent(ev);
  return 'ok';
})(%s, %s, %s, %s)
"""

REC_JS = """
(async () => {
  const seconds = 1.6;
  window.__job = { done: false, data: null, error: null };
  try {
    const W = 320, H = 240;
    const cv = document.createElement('canvas');
    cv.width = W; cv.height = H;
    const ctx = cv.getContext('2d');
    const stream = cv.captureStream(30);
    const mime = MediaRecorder.isTypeSupported('video/webm;codecs=vp8')
      ? 'video/webm;codecs=vp8' : 'video/webm';
    const rec = new MediaRecorder(stream, { mimeType: mime, videoBitsPerSecond: 900000 });
    const chunks = [];
    rec.ondataavailable = (e) => { if (e.data.size) chunks.push(e.data); };
    const stopped = new Promise((r) => { rec.onstop = r; });
    rec.start(200);
    await new Promise((resolve) => {
      const t0 = performance.now();
      const draw = () => {
        const t = (performance.now() - t0) / 1000;
        ctx.fillStyle = 'hsl(' + Math.round(t * 70) % 360 + ' 62% 52%)';
        ctx.fillRect(0, 0, W, H);
        ctx.fillStyle = '#ffffff';
        ctx.fillRect(20 + ((t * 130) % (W - 90)), 56, 56, 56);
        ctx.fillStyle = '#101010';
        ctx.font = 'bold 44px sans-serif';
        ctx.fillText(String(Math.floor(t * 10)), 18, 214);
      };
      const timer = setInterval(() => {
        draw();
        if ((performance.now() - t0) / 1000 >= seconds) {
          clearInterval(timer);
          resolve();
        }
      }, 33);
      draw();
    });
    rec.stop();
    await stopped;
    const blob = new Blob(chunks, { type: 'video/webm' });
    const buf = await blob.arrayBuffer();
    const bytes = new Uint8Array(buf);
    let str = '';
    const CH = 0x8000;
    for (let i = 0; i < bytes.length; i += CH) {
      str += String.fromCharCode.apply(null, bytes.subarray(i, i + CH));
    }
    window.__job.data = btoa(str);
  } catch (err) {
    window.__job.error = String(err);
  } finally {
    window.__job.done = true;
  }
  return 'started';
})()
"""


def wait_for(js, expr, limit=20.0, step=0.2):
    end = time.time() + limit
    while time.time() < end:
        if js(expr):
            return True
        time.sleep(step)
    return False


def main():
    portrait = make_portrait(DATA / "portrait.jpg", 900, 1200, (243, 243, 243))
    photo = make_photo(DATA / "photo.jpg", 3000, 2000)
    win, _settings = appmod.build_window()
    pid = os.getpid()

    def work():
        try:
            run_steps()
        except Exception as exc:  # noqa: BLE001
            import traceback
            report["fatal"] = traceback.format_exc()
            print(json.dumps(report, ensure_ascii=False, indent=2))
            print("FATAL", exc, flush=True)
        finally:
            try:
                win.destroy()
            except Exception:
                pass

    def run_steps():
        time.sleep(3.0)
        hwnd = find_hwnd(pid)
        if not hwnd:
            report["fatal"] = "no hwnd"
            return
        js = win.evaluate_js

        js("location.hash='#/image'")
        time.sleep(1.2)
        report["nav"] = js("!!document.querySelector('[data-nav=\"image\"]')")
        report["tabs"] = js("document.querySelectorAll('#imgTabs .img-tab').length")
        capture(hwnd, str(SHOTS / "image_id_empty.png"))

        # ---- 证件照 ----
        b64 = base64.b64encode(portrait.read_bytes()).decode()
        js(DROP_JS % (json.dumps(b64), json.dumps("portrait.jpg"), json.dumps("image/jpeg"),
                      json.dumps("#idStage")))
        time.sleep(1.2)
        report["id_canvas"] = js("(() => { const c = document.getElementById('idCanvas'); return c.width + 'x' + c.height; })()")
        report["id_filebar"] = js("!document.getElementById('idFilebar').hidden")
        js("document.querySelector('#idSizes [data-size=\"two\"]').click()")
        js("document.querySelector('#idBgs [data-back=\"blue\"]').click()")
        time.sleep(0.8)
        report["id_px"] = js("document.getElementById('idPx').textContent")
        report["id_canvas2"] = js("(() => { const c = document.getElementById('idCanvas'); return c.width + 'x' + c.height; })()")
        report["id_corner"] = js("(() => { const c = document.getElementById('idCanvas'); const d = c.getContext('2d').getImageData(4, 4, 1, 1).data; return [d[0], d[1], d[2]].join(','); })()")
        js("document.getElementById('idSave').click()")
        time.sleep(1.5)
        report["id_hint"] = js("document.getElementById('idSaveHint').textContent")
        capture(hwnd, str(SHOTS / "image_id.png"))

        # ---- 视频转 GIF ----
        js("document.querySelector('#imgTabs [data-tool=\"gif\"]').click()")
        time.sleep(0.5)
        js(REC_JS)
        got = wait_for(js, "window.__job && window.__job.done", limit=30)
        report["rec_done"] = got
        report["rec_error"] = js("window.__job && window.__job.error")
        video_b64 = js("(window.__job && window.__job.data) || ''") if got else ""
        report["video_bytes"] = len(base64.b64decode(video_b64)) if video_b64 else 0
        if video_b64:
            (DATA / "clip.webm").write_bytes(base64.b64decode(video_b64))
        js(DROP_JS % (json.dumps(video_b64), json.dumps("clip.webm"), json.dumps("video/webm"),
                      json.dumps("#gifStage")))
        time.sleep(1.6)
        report["gif_meta"] = js("document.getElementById('gifMeta').textContent")
        report["gif_make_disabled"] = js("document.getElementById('gifMake').disabled")
        js("document.getElementById('gifMake').click()")
        ok = wait_for(js, "!document.getElementById('gifSave').disabled", limit=45)
        report["gif_done"] = ok
        report["gif_info"] = js("document.getElementById('gifInfo').textContent")
        report["gif_progress"] = js("document.getElementById('gifProgressText').textContent")
        js("document.getElementById('gifSave').click()")
        time.sleep(1.5)
        report["gif_hint"] = js("document.getElementById('gifSaveHint').textContent")
        capture(hwnd, str(SHOTS / "image_gif.png"))

        # ---- 压缩 ----
        js("document.querySelector('#imgTabs [data-tool=\"compress\"]').click()")
        time.sleep(0.5)
        b64p = base64.b64encode(photo.read_bytes()).decode()
        js(DROP_JS % (json.dumps(b64p), json.dumps("photo.jpg"), json.dumps("image/jpeg"),
                      json.dumps("#cmpStage")))
        time.sleep(1.2)
        report["cmp_info"] = js("document.getElementById('cmpFileInfo').textContent")
        js("document.getElementById('cmpKb').value = 180")
        js("document.getElementById('cmpRun').click()")
        ok2 = wait_for(js, "!document.getElementById('cmpSave').disabled", limit=60)
        report["cmp_done"] = ok2
        report["cmp_before"] = js("document.getElementById('cmpBefore').textContent")
        report["cmp_after"] = js("document.getElementById('cmpAfter').textContent")
        report["cmp_q"] = js("document.getElementById('cmpQuality').textContent")
        js("document.getElementById('cmpSave').click()")
        time.sleep(1.5)
        report["cmp_hint"] = js("document.getElementById('cmpSaveHint').textContent")
        capture(hwnd, str(SHOTS / "image_compress.png"))

        # ---- 保存产物校验 ----
        for key in ("id_hint", "gif_hint", "cmp_hint"):
            m = re.search(r"→ (.+)$", str(report.get(key) or ""))
            if not m:
                report[key + "_file"] = "no path"
                continue
            p = Path(m.group(1).strip())
            if not p.exists():
                report[key + "_file"] = "missing"
                continue
            info = {"size": p.stat().st_size}
            try:
                im = Image.open(p)
                info["format"] = im.format
                info["size_px"] = list(im.size)
                if im.format == "GIF":
                    info["frames"] = getattr(im, "n_frames", 1)
                else:
                    info["corner"] = list(im.convert("RGB").getpixel((4, 4)))
            except Exception as exc:  # noqa: BLE001
                info["open_error"] = str(exc)
            report[key + "_file"] = info

        report["errors"] = js("JSON.stringify(window.__errs || [])")
        print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)

    webview.start(func=work, gui="edgechromium", private_mode=False,
                  storage_path=str(DATA / "webview"))


if __name__ == "__main__":
    main()
