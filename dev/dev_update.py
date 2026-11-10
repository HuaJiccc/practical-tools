"""更新模块自测：版本比较、两种清单格式、下载与校验、错误路径。

全部本地起一个 HTTP 服务，不依赖外网。
"""

import hashlib
import http.server
import json
import sys
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

import update as upd  # noqa: E402

checks = []


def check(name, ok, detail=""):
    checks.append((name, bool(ok), detail))
    print(("PASS  " if ok else "FAIL  ") + name + (f"  ({detail})" if detail else ""))


class Handler(http.server.BaseHTTPRequestHandler):
    routes = {}

    def log_message(self, *args):
        pass

    def do_GET(self):
        path = self.path.split("?")[0]
        if path not in self.routes:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"not found")
            return
        item = self.routes[path]
        if isinstance(item, tuple) and item[0] == "file":
            body = Path(item[1]).read_bytes()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        body = json.dumps(item).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def serve():
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}"


def main():
    tmp = Path(tempfile.mkdtemp(prefix="pt-upd-"))
    payload = tmp / "setup-test.exe"
    payload.write_bytes(b"MZ" + b"\x00" * 4000 + b"fake installer body")
    digest = hashlib.sha256(payload.read_bytes()).hexdigest()

    server, base = serve()
    try:
        Handler.routes = {
            "/plain.json": {
                "version": "1.2.0",
                "notes": "修了三个问题\n加了两个功能",
                "url": f"{base}/setup-test.exe",
                "page": "https://example.invalid/releases",
                "sha256": digest,
            },
            "/same.json": {"version": "1.0.0", "url": f"{base}/setup-test.exe"},
            "/old.json": {"version": "0.9.5", "url": f"{base}/setup-test.exe"},
            "/github.json": {
                "tag_name": "v1.3.0",
                "body": "GitHub 格式的更新说明",
                "html_url": "https://example.invalid/tag",
                "assets": [
                    {"name": "notes.txt", "browser_download_url": f"{base}/bad.txt"},
                    {"name": "实用工具-1.3.0-安装程序.exe", "browser_download_url": f"{base}/setup-test.exe"},
                ],
            },
            "/setup-test.exe": ("file", str(payload)),
            "/bad.json": {"no_version": True},
        }

        # ---- 版本比较 ----
        check("1.1.0 > 1.0.0", upd.is_newer("1.1.0", "1.0.0"))
        check("v1.0.10 > v1.0.9", upd.is_newer("v1.0.10", "v1.0.9"))
        check("1.0.0 不比 1.0.0 新", not upd.is_newer("1.0.0", "1.0.0"))
        check("0.9 < 1.0", not upd.is_newer("0.9", "1.0.0"))
        check("怪异字符串不炸", upd.is_newer("1.0.0-beta", "0.9.9"))

        # ---- 清单解析 ----
        r = upd.check("1.0.0", f"{base}/plain.json")
        check("自定义清单 ok", r.get("ok") and r.get("has_update"), json.dumps(r, ensure_ascii=False)[:90])
        check("读到说明", "修了三个问题" in (r.get("notes") or ""))
        check("读到 sha256", r.get("sha256") == digest)

        r2 = upd.check("1.0.0", f"{base}/same.json")
        check("同版本不算更新", r2.get("ok") and not r2.get("has_update"))

        r3 = upd.check("1.0.0", f"{base}/old.json")
        check("旧版本不算更新", r3.get("ok") and not r3.get("has_update"))

        r4 = upd.check("1.0.0", f"{base}/github.json")
        check("GitHub 格式 ok", r4.get("ok") and r4.get("latest") == "v1.3.0", str(r4.get("latest")))
        check("GitHub 挑出 exe", (r4.get("url") or "").endswith("setup-test.exe"),
              str(r4.get("url")))

        # ---- 错误路径 ----
        r5 = upd.check("1.0.0", "")
        check("没有更新源", r5.get("code") == "no_feed", str(r5.get("error")))

        r6 = upd.check("1.0.0", f"{base}/missing.json")
        check("404 有友好提示", not r6.get("ok") and "404" in (r6.get("error") or ""),
              str(r6.get("error")))

        r7 = upd.check("1.0.0", f"{base}/bad.json")
        check("格式不对有提示", not r7.get("ok") and "版本" in (r7.get("error") or ""),
              str(r7.get("error")))

        r8 = upd.check("1.0.0", "http://127.0.0.1:1/none.json", timeout=2)
        check("连不上有提示", not r8.get("ok"), str(r8.get("error"))[:60])

        # ---- 下载 ----
        got = upd.download(f"{base}/setup-test.exe", folder=str(tmp / "dl"), sha256=digest)
        check("下载成功", got.get("ok") and Path(got["path"]).is_file(), str(got.get("path")))
        check("大小一致", got.get("size") == len(payload.read_bytes()), str(got.get("size")))

        try:
            upd.download(f"{base}/setup-test.exe", folder=str(tmp / "dl2"), sha256="0" * 64)
            check("sha256 不符要拒绝", False, "没有抛错")
        except upd.UpdateError as exc:
            check("sha256 不符要拒绝", "校验" in str(exc), str(exc))

        try:
            upd.download(f"{base}/nothing.exe", folder=str(tmp / "dl3"))
            check("下载 404 要报错", False, "没有抛错")
        except upd.UpdateError as exc:
            check("下载 404 要报错", "404" in str(exc) or "下载" in str(exc), str(exc))

        try:
            upd.launch(str(tmp / "nope.exe"))
            check("安装包不存在要报错", False, "没有抛错")
        except upd.UpdateError as exc:
            check("安装包不存在要报错", "不存在" in str(exc), str(exc))

        # ---- App 层：源码模式只下载不安装 ----
        import app as appmod

        built = appmod.build_window()
        ui = None
        for obj in (built,):
            win = obj[0]
        # UiApi 实例挂在 window 上不方便取，直接构造一个最小的
        class FakeApi:
            settings = type("S", (), {"all": staticmethod(lambda: {})})()

        uiapi = appmod.UiApi(FakeApi())
        res = uiapi.update_install(f"{base}/setup-test.exe", digest)
        check("源码模式下载后不安装", res.get("ok") and res.get("installed") is False,
              json.dumps(res, ensure_ascii=False)[:100])
        about = uiapi.app_about()
        check("关于页版本是 1.0.0", about.get("version") == "1.0.0", str(about.get("version")))
        check("关于页有更新说明", len(about.get("notes") or "") > 20)
        try:
            win.destroy()
        except Exception:
            pass
    finally:
        server.shutdown()

    failed = [c for c in checks if not c[1]]
    print(f"\n{len(checks) - len(failed)}/{len(checks)} 通过")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
