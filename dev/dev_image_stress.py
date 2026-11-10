"""图片工具压力测试：证件照 / 视频转 GIF / 压缩图片，各跑 12 次并逐次校验产物。

每次都是真实链路：合成文件 -> drop 事件 -> 点 UI 上的按钮 -> 后端落盘 -> PIL 解码校验。
输出每一轮的通过/失败原因，最后给出总数统计。
"""
import base64
import ctypes
import ctypes.wintypes as wt
import json
import os
import re
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "_data_stress"
os.environ["PERSONALTOOLS_DATA"] = str(DATA)
DATA.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT.parent / "app"))

import webview  # noqa: E402
import app as appmod  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

SHOTS = ROOT / "_shots" / "v23"
SHOTS.mkdir(parents=True, exist_ok=True)

SIZE_MAP = {
    "one": (295, 413),
    "small": (260, 378),
    "two": (413, 579),
    "big": (390, 567),
    "visa": (413, 531),
    "us": (600, 600),
}
BACK_MAP = {
    "none": None,
    "white": (255, 255, 255),
    "blue": (67, 142, 219),
    "red": (217, 58, 73),
    "gray": (237, 237, 237),
}


def make_portrait(path, w, h, bg, shirt=(66, 88, 128)):
    im = Image.new("RGB", (w, h), bg)
    d = ImageDraw.Draw(im)
    d.ellipse([w * 0.08, h * 0.60, w * 0.92, h * 1.45], fill=shirt)
    d.rectangle([w * 0.42, h * 0.48, w * 0.58, h * 0.74], fill=(232, 196, 168))
    d.ellipse([w * 0.30, h * 0.14, w * 0.70, h * 0.60], fill=(238, 205, 180))
    d.ellipse([w * 0.29, h * 0.11, w * 0.71, h * 0.39], fill=(42, 34, 30))
    d.ellipse([w * 0.38, h * 0.30, w * 0.44, h * 0.34], fill=(40, 40, 40))
    d.ellipse([w * 0.56, h * 0.30, w * 0.62, h * 0.34], fill=(40, 40, 40))
    im.save(path, quality=94)
    return path


def make_photo(path, w, h):
    im = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(im)
    for y in range(h):
        d.line([(0, y), (w, y)], fill=(24 + y * 130 // h, 80 + y * 40 // h, 210 - y * 110 // h))
    for x in range(0, w, 41):
        d.line([(x, 0), (x + 260, h)], fill=(210, 130, 70), width=4)
    im.save(path, quality=97)
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
  const seconds = 2.4;
  window.__job = { done: false, data: null, error: null };
  try {
    const W = 320, H = 240;
    const cv = document.createElement('canvas');
    cv.width = W; cv.height = H;
    const ctx = cv.getContext('2d');
    const stream = cv.captureStream(30);
    const mime = MediaRecorder.isTypeSupported('video/webm;codecs=vp8')
      ? 'video/webm;codecs=vp8' : 'video/webm';
    const rec = new MediaRecorder(stream, { mimeType: mime, videoBitsPerSecond: 1200000 });
    const chunks = [];
    rec.ondataavailable = (e) => { if (e.data.size) chunks.push(e.data); };
    const stopped = new Promise((r) => { rec.onstop = r; });
    rec.start(200);
    await new Promise((resolve) => {
      const t0 = performance.now();
      const draw = () => {
        const t = (performance.now() - t0) / 1000;
        ctx.fillStyle = 'hsl(' + Math.round(t * 150) % 360 + ' 62% 52%)';
        ctx.fillRect(0, 0, W, H);
        ctx.fillStyle = '#ffffff';
        ctx.fillRect(20 + ((t * 260) % (W - 90)), 56, 56, 56);
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
    const bytes = new Uint8Array(await blob.arrayBuffer());
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


def wait_for(js, expr, limit=25.0, step=0.15):
    end = time.time() + limit
    while time.time() < end:
        try:
            if js(expr):
                return True
        except Exception:  # noqa: BLE001
            pass
        time.sleep(step)
    return False


def near(a, b, tol=4):
    return all(abs(int(x) - int(y)) <= tol for x, y in zip(a, b))


class Runner:
    def __init__(self, js, hwnd, video_b64):
        self.js = js
        self.hwnd = hwnd
        self.video_b64 = video_b64
        self.results = {"id": [], "gif": [], "cmp": []}

    # ---------- 证件照 ----------
    def run_id(self, case):
        js = self.js
        sel = case["source"]
        b64 = base64.b64encode(sel.read_bytes()).decode()
        js(DROP_JS % (json.dumps(b64), json.dumps(sel.name), json.dumps("image/jpeg"),
                      json.dumps("#idStage")))
        if not wait_for(js, "!document.getElementById('idFrame').hidden", 8):
            return self.fail("id", case, "照片没有加载出来")
        js(f"document.querySelector('#idSizes [data-size=\"{case['size']}\"]').click()")
        js(f"document.querySelector('#idBgs [data-back=\"{case['back']}\"]').click()")
        js("(() => { const el = document.getElementById('idTol');"
           f" el.value = {case['tol']}; el.dispatchEvent(new Event('input', {{bubbles:true}})); }})()")
        time.sleep(0.35)
        js("document.getElementById('idSaveHint').removeAttribute('title')")
        js("document.getElementById('idSave').click()")
        if not wait_for(js, "!!document.getElementById('idSaveHint').title", 10):
            hint = js("document.getElementById('idSaveHint').textContent")
            return self.fail("id", case, f"保存失败：{hint}")
        path = Path(js("document.getElementById('idSaveHint').title"))
        want_w, want_h = SIZE_MAP[case["size"]]
        try:
            im = Image.open(path)
            im.load()
            rgb = im.convert("RGB")
            problems = []
            if im.size != (want_w, want_h):
                problems.append(f"尺寸 {im.size} 应为 {(want_w, want_h)}")
            if im.format != "PNG":
                problems.append(f"格式 {im.format}")
            back = BACK_MAP[case["back"]]
            if back:
                corners = ((3, 3), (want_w - 4, 3), (3, want_h - 4), (want_w - 4, want_h - 4))
                hits = sum(1 for pt in corners if near(rgb.getpixel(pt), back, case["tolerance"]))
                # 横图裁成竖版时下半部分会被肩膀占满，只要上两个角是底色即算通过
                if hits < 2:
                    problems.append(f"四个角只有 {hits} 个换了底色：{[rgb.getpixel(pt) for pt in corners]}")
            center = rgb.getpixel((want_w // 2, want_h // 2))
            if back and near(center, back, 6):
                problems.append("中心被底色盖住了，人像没保留")
            if problems:
                return self.fail("id", case, "；".join(problems))
            return self.ok("id", case, f"{im.size[0]}×{im.size[1]} {path.stat().st_size // 1024}KB")
        except Exception as exc:  # noqa: BLE001
            return self.fail("id", case, f"产物打不开：{exc}")

    # ---------- GIF ----------
    def run_gif(self, case):
        js = self.js
        js("document.querySelector('#imgTabs [data-tool=\"gif\"]').click()")
        time.sleep(0.25)
        js(DROP_JS % (json.dumps(self.video_b64), json.dumps("clip.webm"),
                      json.dumps("video/webm"), json.dumps("#gifStage")))
        if not wait_for(js, "!document.getElementById('gifMake').disabled", 10):
            return self.fail("gif", case, "视频没有加载出来")
        meta = js("document.getElementById('gifMeta').textContent")
        m = re.search(r"([\d.]+)s", meta)
        duration = float(m.group(1)) if m else 0.0
        js(f"document.querySelector('#gifFps [data-fps=\"{case['fps']}\"]').click()")
        js(f"document.querySelector('#gifWidth [data-w=\"{case['w']}\"]').click()")
        js("(() => { const el = document.getElementById('gifDur');"
           f" el.value = {case['len']}; el.dispatchEvent(new Event('input', {{bubbles:true}})); }})()")
        js("(() => { const el = document.getElementById('gifStart');"
           f" el.value = {case['start']}; el.dispatchEvent(new Event('input', {{bubbles:true}})); }})()")
        time.sleep(0.25)
        js("document.getElementById('gifSave').disabled = true")
        js("document.getElementById('gifSaveHint').removeAttribute('title')")
        js("document.getElementById('gifMake').click()")
        if not wait_for(js, "!document.getElementById('gifSave').disabled", 60):
            info = js("document.getElementById('gifProgressText').textContent")
            return self.fail("gif", case, f"生成失败：{info}")
        js("document.getElementById('gifSave').click()")
        if not wait_for(js, "!!document.getElementById('gifSaveHint').title", 10):
            return self.fail("gif", case, "保存失败")
        path = Path(js("document.getElementById('gifSaveHint').title"))
        try:
            im = Image.open(path)
            frames = getattr(im, "n_frames", 1)
            src_w = 320
            want_w = min(case["w"], src_w)
            want_w -= want_w % 2
            want_h = round(want_w * 240 / src_w)
            want_h -= want_h % 2
            effective = min(case["len"], duration)
            want_frames = max(1, round(effective * case["fps"]))
            problems = []
            if im.size != (want_w, want_h):
                problems.append(f"尺寸 {im.size} 应为 {(want_w, want_h)}")
            if im.format != "GIF":
                problems.append(f"格式 {im.format}")
            if abs(frames - want_frames) > 1:
                problems.append(f"帧数 {frames} 应为 {want_frames}")
            points = [(8, 8), (want_w // 2, want_h // 2), (want_w - 9, 8),
                      (want_w // 2, want_h - 9), (want_w // 4, want_h // 3),
                      (want_w * 3 // 4, want_h // 2), (20, want_h // 2),
                      (want_w // 2, 40), (want_w - 20, want_h - 20)]
            sigs = []
            for i in range(frames):
                im.seek(i)
                frame = im.convert("RGB")
                frame.load()
                sigs.append(tuple(frame.getpixel(pt) for pt in points))
            if len(set(sigs)) < 2:
                problems.append("各帧一模一样，没抓到画面变化")
            if path.stat().st_size < 800:
                problems.append(f"文件只有 {path.stat().st_size}B，太小")
            if problems:
                return self.fail("gif", case, "；".join(problems))
            return self.ok("gif", case, f"{im.size[0]}×{im.size[1]} {frames}帧 {path.stat().st_size // 1024}KB")
        except Exception as exc:  # noqa: BLE001
            return self.fail("gif", case, f"产物解不开：{exc}")

    # ---------- 压缩 ----------
    def run_cmp(self, case):
        js = self.js
        js("document.querySelector('#imgTabs [data-tool=\"compress\"]').click()")
        time.sleep(0.25)
        src = case["source"]
        b64 = base64.b64encode(src.read_bytes()).decode()
        js(DROP_JS % (json.dumps(b64), json.dumps(src.name), json.dumps("image/jpeg"),
                      json.dumps("#cmpStage")))
        if not wait_for(js, "!document.getElementById('cmpRun').disabled", 8):
            return self.fail("cmp", case, "图片没有加载出来")
        js(f"document.querySelector('#cmpFmt [data-fmt=\"{case['fmt']}\"]').click()")
        js(f"document.querySelector('#cmpMax [data-max=\"{case['max']}\"]').click()")
        js(f"document.getElementById('cmpKb').value = {case['kb']}")
        js("document.getElementById('cmpSave').disabled = true")
        js("document.getElementById('cmpSaveHint').removeAttribute('title')")
        js("document.getElementById('cmpRun').click()")
        if not wait_for(js, "!document.getElementById('cmpSave').disabled", 90):
            return self.fail("cmp", case, "压缩没有完成")
        js("document.getElementById('cmpSave').click()")
        if not wait_for(js, "!!document.getElementById('cmpSaveHint').title", 10):
            return self.fail("cmp", case, "保存失败")
        path = Path(js("document.getElementById('cmpSaveHint').title"))
        inst = path.stat().st_size
        target = case["kb"] * 1024
        try:
            im = Image.open(path)
            im.load()
            w, h = im.size
            problems = []
            if inst > target:
                problems.append(f"{inst}B 超过目标 {target}B")
            if inst < target * 0.05:
                problems.append(f"只有 {inst}B，压过头了")
            if case["max"]:
                if max(w, h) > case["max"] + 1:
                    problems.append(f"最长边 {max(w, h)} 超过 {case['max']}")
            want_ext = "WEBP" if case["fmt"] == "image/webp" else "JPEG"
            if im.format != want_ext:
                problems.append(f"格式 {im.format} 应为 {want_ext}")
            if problems:
                return self.fail("cmp", case, "；".join(problems))
            return self.ok("cmp", case, f"{inst // 1024}KB≤{case['kb']}KB {w}×{h}")
        except Exception as exc:  # noqa: BLE001
            return self.fail("cmp", case, f"产物打不开：{exc}")

    # ---------- 记录 ----------
    def ok(self, kind, case, detail):
        self.results[kind].append({"case": case["name"], "ok": True, "detail": detail})
        print(f"  ✓ {case['name']}: {detail}", flush=True)
        return True

    def fail(self, kind, case, why):
        self.results[kind].append({"case": case["name"], "ok": False, "detail": why})
        print(f"  ✗ {case['name']}: {why}", flush=True)
        return False


def main():
    # 素材
    p1 = make_portrait(DATA / "p_white.jpg", 900, 1200, (243, 243, 243))
    p2 = make_portrait(DATA / "p_blue.jpg", 1200, 1600, (206, 226, 242))
    p3 = make_portrait(DATA / "p_wide.jpg", 800, 600, (240, 240, 240))
    p4 = make_portrait(DATA / "p_gray.jpg", 640, 480, (228, 228, 228), shirt=(120, 60, 60))
    big = make_photo(DATA / "big.jpg", 3000, 2000)
    mid = make_photo(DATA / "mid.jpg", 1200, 800)

    id_cases = [
        {"name": "白底一寸", "source": p1, "size": "one", "back": "white", "tol": 34, "tolerance": 4},
        {"name": "白底二寸蓝底", "source": p1, "size": "two", "back": "blue", "tol": 34, "tolerance": 5},
        {"name": "小一寸红底", "source": p1, "size": "small", "back": "red", "tol": 34, "tolerance": 5},
        {"name": "大一寸灰底", "source": p1, "size": "big", "back": "gray", "tol": 34, "tolerance": 5},
        {"name": "签证白底", "source": p1, "size": "visa", "back": "white", "tol": 40, "tolerance": 4},
        {"name": "美签蓝底", "source": p1, "size": "us", "back": "blue", "tol": 30, "tolerance": 5},
        {"name": "浅蓝底图换蓝", "source": p2, "size": "one", "back": "blue", "tol": 45, "tolerance": 6},
        {"name": "浅蓝底图换红", "source": p2, "size": "two", "back": "red", "tol": 45, "tolerance": 6},
        {"name": "横图一寸白", "source": p3, "size": "one", "back": "white", "tol": 34, "tolerance": 4},
        {"name": "横图二寸蓝", "source": p3, "size": "two", "back": "blue", "tol": 50, "tolerance": 6},
        {"name": "灰底保留原图", "source": p4, "size": "small", "back": "none", "tol": 34, "tolerance": 4},
        {"name": "低容差大一寸", "source": p2, "size": "big", "back": "gray", "tol": 18, "tolerance": 6},
    ]

    gif_cases = [
        {"name": "320宽 1.0s 10fps", "w": 320, "len": 1.0, "fps": 10, "start": 0},
        {"name": "240宽 1.0s 10fps", "w": 240, "len": 1.0, "fps": 10, "start": 0.4},
        {"name": "240宽 1.5s 8fps", "w": 240, "len": 1.5, "fps": 8, "start": 0},
        {"name": "320宽 1.0s 15fps", "w": 320, "len": 1.0, "fps": 15, "start": 0.2},
        {"name": "480宽 0.5s 10fps", "w": 480, "len": 0.5, "fps": 10, "start": 0},
        {"name": "320宽 0.5s 10fps 起点0.8", "w": 320, "len": 0.5, "fps": 10, "start": 0.8},
        {"name": "240宽 2.0s 10fps", "w": 240, "len": 2.0, "fps": 10, "start": 0},
        {"name": "320宽 1.0s 8fps", "w": 320, "len": 1.0, "fps": 8, "start": 0},
        {"name": "240宽 1.0s 15fps", "w": 240, "len": 1.0, "fps": 15, "start": 0.5},
        {"name": "320宽 1.5s 10fps", "w": 320, "len": 1.5, "fps": 10, "start": 0.3},
        {"name": "240宽 1.0s 10fps 起点1.0", "w": 240, "len": 1.0, "fps": 10, "start": 1.0},
        {"name": "320宽 0.5s 15fps", "w": 320, "len": 0.5, "fps": 15, "start": 0.6},
    ]

    cmp_cases = [
        {"name": "大图 200KB JPEG", "source": big, "kb": 200, "fmt": "image/jpeg", "max": 0},
        {"name": "大图 500KB JPEG", "source": big, "kb": 500, "fmt": "image/jpeg", "max": 0},
        {"name": "大图 100KB JPEG", "source": big, "kb": 100, "fmt": "image/jpeg", "max": 0},
        {"name": "大图 1MB JPEG", "source": big, "kb": 1024, "fmt": "image/jpeg", "max": 0},
        {"name": "大图 200KB WebP", "source": big, "kb": 200, "fmt": "image/webp", "max": 0},
        {"name": "大图 200KB 限1920", "source": big, "kb": 200, "fmt": "image/jpeg", "max": 1920},
        {"name": "大图 200KB 限1280", "source": big, "kb": 200, "fmt": "image/jpeg", "max": 1280},
        {"name": "大图 50KB JPEG", "source": big, "kb": 50, "fmt": "image/jpeg", "max": 0},
        {"name": "中图 80KB JPEG", "source": mid, "kb": 80, "fmt": "image/jpeg", "max": 0},
        {"name": "中图 300KB WebP", "source": mid, "kb": 300, "fmt": "image/webp", "max": 0},
        {"name": "大图 800KB WebP 限1920", "source": big, "kb": 800, "fmt": "image/webp", "max": 1920},
        {"name": "大图 150KB WebP 限800", "source": big, "kb": 150, "fmt": "image/webp", "max": 800},
    ]

    win, _ = appmod.build_window()
    pid = os.getpid()

    def work():
        runner = None
        try:
            time.sleep(3.0)
            hwnd = find_hwnd(pid)
            if not hwnd:
                print("FATAL: 找不到窗口")
                return
            js = win.evaluate_js
            js("location.hash='#/image'")
            time.sleep(1.2)

            # 先录一段视频当素材
            js(REC_JS)
            if not wait_for(js, "window.__job && window.__job.done", 30):
                print("FATAL: 视频录制超时")
                return
            err = js("window.__job.error")
            video_b64 = js("(window.__job && window.__job.data) || ''")
            if err or not video_b64:
                print(f"FATAL: 录制失败 {err}")
                return
            (DATA / "clip.webm").write_bytes(base64.b64decode(video_b64))
            print(f"素材视频 {len(base64.b64decode(video_b64)) // 1024} KB", flush=True)

            runner = Runner(js, hwnd, video_b64)

            print("\n[1/3] 证件照 ×12", flush=True)
            for case in id_cases:
                runner.run_id(case)
                time.sleep(0.15)
            capture(hwnd, str(SHOTS / "stress_id.png"))

            print("\n[2/3] 视频转 GIF ×12", flush=True)
            for case in gif_cases:
                runner.run_gif(case)
            capture(hwnd, str(SHOTS / "stress_gif.png"))

            print("\n[3/3] 压缩图片 ×12", flush=True)
            for case in cmp_cases:
                runner.run_cmp(case)
            capture(hwnd, str(SHOTS / "stress_cmp.png"))
        except Exception:  # noqa: BLE001
            print("FATAL\n" + traceback.format_exc(), flush=True)
        finally:
            if runner:
                print("\n================ 汇总 ================", flush=True)
                total = 0
                fails = 0
                for kind, label in (("id", "证件照"), ("gif", "视频转 GIF"), ("cmp", "压缩图片")):
                    rows = runner.results[kind]
                    bad = [r for r in rows if not r["ok"]]
                    total += len(rows)
                    fails += len(bad)
                    print(f"{label}: {len(rows) - len(bad)}/{len(rows)} 通过", flush=True)
                    for r in bad:
                        print(f"    失败 → {r['case']}: {r['detail']}", flush=True)
                print(f"合计 {total} 次，失败 {fails} 次", flush=True)
                (SHOTS / "stress_report.json").write_text(
                    json.dumps(runner.results, ensure_ascii=False, indent=2), encoding="utf-8")
            try:
                win.destroy()
            except Exception:
                pass

    webview.start(func=work, gui="edgechromium", private_mode=False,
                  storage_path=str(DATA / "webview"))


if __name__ == "__main__":
    main()
