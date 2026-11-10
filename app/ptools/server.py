"""本地 HTTP 服务：把网页和 Python 接口焊在一起。

界面是 WebView 里的一个页面，它用 ``POST /api/<方法名>`` 调 Python。
因为只监听 127.0.0.1，端口又是随机的，所以额外发一个一次性令牌：
启动时塞进首页的 ``window.__TOKEN__``，之后每个请求都得带 ``X-Token``。
这样本机上别的程序就算猜到端口，也调不动接口。
"""

import json
import mimetypes
import secrets
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

MAX_BODY = 4 * 1024 * 1024      # 单次请求体上限，防止内存被撑爆
API_PREFIX = "/api/"
COVER_PREFIX = "/covers/"
SNIPPET = '<script>window.__TOKEN__="{token}";</script>'


class ApiServer:
    """起一个只给本机用的 HTTP 服务。``start()`` 返回自己，方便链式调用。"""

    def __init__(self, api, web_root, host="127.0.0.1", cover_root=None):
        self.api = api
        self.web_root = Path(web_root)
        self.cover_root = Path(cover_root) if cover_root else None
        self.host = host
        self.port = 0
        self.token = secrets.token_urlsafe(24)
        self._httpd = None
        self._thread = None

    @property
    def url(self):
        return f"http://{self.host}:{self.port}/"

    def start(self):
        handler = self._make_handler()
        self._httpd = ThreadingHTTPServer((self.host, 0), handler)
        self._httpd.daemon_threads = True
        self.port = self._httpd.server_address[1]
        self._thread = threading.Thread(target=self._httpd.serve_forever,
                                        name="pt-api-server", daemon=True)
        self._thread.start()
        return self

    def stop(self):
        if self._httpd:
            try:
                self._httpd.shutdown()
                self._httpd.server_close()
            except Exception:
                pass
            self._httpd = None
        self._thread = None

    # ---------------- 内部 ----------------

    def _resolve(self, root, relative):
        """把 URL 路径落到磁盘上，顺手挡住 ../ 这类越狱写法。"""
        if not root:
            return None
        clean = urllib.parse.unquote(str(relative or "")).lstrip("/\\")
        if not clean or clean.startswith(".."):
            return None
        target = (root / clean).resolve()
        try:
            target.relative_to(root.resolve())
        except ValueError:
            return None
        return target if target.is_file() else None

    def _make_handler(self):
        server = self

        class Handler(BaseHTTPRequestHandler):
            server_version = "PersonalToolkit"
            protocol_version = "HTTP/1.1"

            def log_message(self, fmt, *args):   # 别往控制台刷日志
                pass

            # ---------- 输出 ----------

            def _send(self, status, body, content_type="application/json; charset=utf-8",
                      extra=None):
                if isinstance(body, str):
                    body = body.encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                for key, value in (extra or {}).items():
                    self.send_header(key, value)
                self.end_headers()
                try:
                    self.wfile.write(body)
                except (BrokenPipeError, ConnectionResetError):
                    pass

            def _json(self, status, payload):
                self._send(status, json.dumps(payload, ensure_ascii=False))

            def _fail(self, status, message):
                self._json(status, {"ok": False, "error": message})

            # ---------- 路由 ----------

            def do_GET(self):
                path = urllib.parse.urlparse(self.path).path
                if path.startswith(API_PREFIX):
                    self._send(404, "not found", "text/plain; charset=utf-8")
                    return
                if path.startswith(COVER_PREFIX):
                    target = server._resolve(server.cover_root, path[len(COVER_PREFIX):])
                    if not target:
                        self._send(404, "not found", "text/plain; charset=utf-8")
                        return
                    self._file(target)
                    return
                if path in ("/", "/index.html"):
                    self._index()
                    return
                target = server._resolve(server.web_root, path)
                if not target:
                    self._send(404, "not found", "text/plain; charset=utf-8")
                    return
                self._file(target)

            def do_POST(self):
                path = urllib.parse.urlparse(self.path).path
                if not path.startswith(API_PREFIX):
                    self._fail(404, "unknown endpoint")
                    return
                if not secrets.compare_digest(str(self.headers.get("X-Token") or ""),
                                              server.token):
                    self._fail(403, "bad token")
                    return
                try:
                    length = int(self.headers.get("Content-Length") or 0)
                except (TypeError, ValueError):
                    length = 0
                if length > MAX_BODY:
                    self._fail(413, "body too large")
                    return
                raw = self.rfile.read(length) if length > 0 else b""
                if not raw:
                    self._fail(400, "invalid body")
                    return
                try:
                    payload = json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, ValueError):
                    self._fail(400, "invalid json")
                    return
                if not isinstance(payload, dict):
                    payload = {}
                self._call(path[len(API_PREFIX):].strip("/"), payload.get("args") or [])

            # ---------- 具体动作 ----------

            def _index(self):
                target = server._resolve(server.web_root, "index.html")
                if not target:
                    self._send(404, "not found", "text/plain; charset=utf-8")
                    return
                try:
                    html = target.read_text(encoding="utf-8")
                except OSError:
                    self._send(500, "index unreadable", "text/plain; charset=utf-8")
                    return
                # 令牌塞到 <head> 后面，越靠前越好，脚本加载时就能读到
                marker = SNIPPET.format(token=server.token)
                lowered = html.lower()
                at = lowered.find("<head>")
                if at >= 0:
                    html = html[:at + 6] + "\n" + marker + html[at + 6:]
                else:
                    html = marker + html
                self._send(200, html, "text/html; charset=utf-8")

            def _file(self, target):
                try:
                    body = target.read_bytes()
                except OSError:
                    self._send(404, "not found", "text/plain; charset=utf-8")
                    return
                kind = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
                if kind.startswith("text/") or kind in ("application/javascript",
                                                        "application/json"):
                    kind += "; charset=utf-8"
                self._send(200, body, kind)

            def _call(self, name, args):
                handler = getattr(server.api, name, None)
                if not name or name.startswith("_") or not callable(handler):
                    self._fail(404, f"unknown method: {name}")
                    return
                if not isinstance(args, (list, tuple)):
                    args = [args]
                try:
                    result = handler(*args)
                except Exception as exc:
                    self._fail(200, f"{type(exc).__name__}: {exc}")
                    return
                if isinstance(result, dict):
                    self._json(200, result)
                else:
                    self._json(200, {"ok": True, "value": result})

        return Handler
