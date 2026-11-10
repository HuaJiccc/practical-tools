"""关于页与检查更新的界面自测（本地 mock 更新源，不走外网）。"""

import hashlib
import http.server
import json
import os
import sys
import tempfile
import threading
import urllib.parse
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))
sys.path.insert(0, str(ROOT / "dev"))

checks = []


def check(name, ok, detail=""):
    checks.append((name, bool(ok), detail))
    print(("PASS  " if ok else "FAIL  ") + name + (f"  ({detail})" if detail else ""))


class Handler(http.server.BaseHTTPRequestHandler):
    routes = {}

    def log_message(self, *args):
        pass

    def do_GET(self):
        path = urllib.parse.unquote(self.path.split("?")[0])
        if path not in self.routes:
            self.send_response(404)
            self.end_headers()
            return
        item = self.routes[path]
        if isinstance(item, tuple) and item[0] == "file":
            body = Path(item[1]).read_bytes()
        else:
            body = json.dumps(item, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    tmp = Path(tempfile.mkdtemp(prefix="pt-uid-"))
    pkg = tmp / "实用工具-1.1.0-安装程序.exe"
    pkg.write_bytes(b"MZ" + os.urandom(300000))
    digest = hashlib.sha256(pkg.read_bytes()).hexdigest()

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    Handler.routes = {
        "/feed.json": {
            "version": "1.1.0",
            "notes": "1.1 测试更新\n· 第一条说明\n· 第二条说明\n· 第三条说明",
            "url": f"{base}/实用工具-1.1.0-安装程序.exe",
            "page": "https://example.invalid/releases",
            "sha256": digest,
        },
        "/实用工具-1.1.0-安装程序.exe": ("file", str(pkg)),
    }

    os.environ["PT_UPDATE_FEED"] = f"{base}/feed.json"

    import webview
    import app as appmod
    from shot_util import find, shot

    # 固定用中文跑一遍，断言才稳定；语言相关的结果单独测
    pref_file = appmod.data_dir() / "ui_prefs.json"
    try:
        saved = json.loads(pref_file.read_text(encoding="utf-8")) if pref_file.exists() else {}
    except Exception:
        saved = {}
    saved["language"] = "zh"
    pref_file.write_text(json.dumps(saved, ensure_ascii=False), encoding="utf-8")

    win = appmod.build_window()[0]
    shots = ROOT / "dev" / "_shots" / "v10"

    def js(code, default=None):
        try:
            return win.evaluate_js(code)
        except Exception:
            return default

    def on_start():
        end = time.time() + 40
        while time.time() < end:
            if js("document.readyState") == "complete":
                break
            time.sleep(0.4)
        time.sleep(2.5)

        js("location.hash = '#/settings'")
        time.sleep(0.6)
        js("document.querySelector('#setRail .set-tab[data-set-tab=\"about\"]').click()")
        time.sleep(1.2)

        check("关于页版本号", js("document.querySelector('#appVersion').textContent") == "1.0.0",
              str(js("document.querySelector('#appVersion').textContent")))
        notes = js("document.querySelector('#releaseNotes').textContent") or ""
        check("更新说明已渲染", "中英文切换" in notes, notes[:40].replace("\n", " "))

        js("document.querySelector('#checkUpdate').click()")
        time.sleep(2.5)
        status = js("document.querySelector('#updateStatus').textContent") or ""
        check("检出新版", "发现新版本" in status and "1.1.0" in status, status[:60].replace("\n", " "))
        check("状态条可见", js("!document.querySelector('#updateStatus').hidden"))
        has_btn = js("!!document.querySelector('#updateStatus [data-upd=\"install\"]')")
        check("有立即更新按钮", has_btn)

        shots.mkdir(parents=True, exist_ok=True)
        hwnd = find("实用工具") or find("Utility Toolkit")
        shot(hwnd, shots / "about_update.png")

        if has_btn:
            js("document.querySelector('#updateStatus [data-upd=\"install\"]').click()")
            time.sleep(4.5)
            after = js("document.querySelector('#updateStatus').textContent") or ""
            check("下载完成提示", "已下载" in after, after[:70].replace("\n", " "))
            shot(hwnd, shots / "about_downloaded.png")

        # 英文下：状态条也要跟着变
        js("document.querySelector('#langSeg button[data-lang=\"en\"]').click()")
        time.sleep(1.0)
        js("document.querySelector('#setRail .set-tab[data-set-tab=\"about\"]').click()")
        time.sleep(0.8)
        js("document.querySelector('#checkUpdate').click()")
        time.sleep(2.2)
        en_status = js("document.querySelector('#updateStatus').textContent") or ""
        check("英文下状态条是英文", "Version" in en_status and "发现新版本" not in en_status,
              en_status[:60].replace("\n", " "))
        en_notes = js("document.querySelector('#releaseNotes').textContent") or ""
        check("英文下更新说明是英文", "first stable release" in en_notes, en_notes[:40])

        # 更新源还是占位符时，要给一句能看懂的话，而不是 404
        js("document.querySelector('#langSeg button[data-lang=\"zh\"]').click()")
        time.sleep(0.8)
        os.environ.pop("PT_UPDATE_FEED", None)
        js("document.querySelector('#setRail .set-tab[data-set-tab=\"about\"]').click()")
        time.sleep(0.6)
        js("document.querySelector('#checkUpdate').click()")
        time.sleep(1.6)
        ph = js("document.querySelector('#updateStatus').textContent") or ""
        check("占位更新源给明确提示", "还没有配置更新源" in ph and "404" not in ph,
              ph[:50].replace("\n", " "))
        check("占位时保留打开发布页出口",
              js("!!document.querySelector('#updateStatus [data-upd=\"page\"]')"))

        js("document.querySelector('#langSeg button[data-lang=\"en\"]').click()")
        time.sleep(0.8)
        js("document.querySelector('#setRail .set-tab[data-set-tab=\"about\"]').click()")
        time.sleep(0.6)
        js("document.querySelector('#checkUpdate').click()")
        time.sleep(1.6)
        ph_en = js("document.querySelector('#updateStatus').textContent") or ""
        check("占位提示英文也翻译", "No update source" in ph_en, ph_en[:50].replace("\n", " "))

        js("document.querySelector('#langSeg button[data-lang=\"zh\"]').click()")
        time.sleep(0.8)
        win.destroy()

    webview.start(func=on_start, gui="edgechromium")
    server.shutdown()

    failed = [c for c in checks if not c[1]]
    print(f"\n{len(checks) - len(failed)}/{len(checks)} 通过")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
