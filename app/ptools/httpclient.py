"""只用标准库的 HTTP 小工具。

只用 urllib：不引 requests，安装包就不用带一个第三方依赖。
自动处理 gzip/deflate，失败统一抛 HttpError（带 HTTP 状态码）。
"""

import gzip
import json
import urllib.error
import urllib.parse
import urllib.request
import zlib

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


class HttpError(Exception):
    """请求失败。``status`` 是 HTTP 状态码，网络层失败时为 None。"""

    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


def _decode(raw, headers):
    encoding = (headers.get("Content-Encoding") or "").lower()
    if "gzip" in encoding:
        try:
            return gzip.decompress(raw)
        except OSError:
            return raw
    if "deflate" in encoding:
        try:
            return zlib.decompress(raw)
        except zlib.error:
            try:
                return zlib.decompress(raw, -zlib.MAX_WBITS)
            except zlib.error:
                return raw
    return raw


def request(url, data=None, headers=None, timeout=15, method=None):
    """发一个请求，返回解码后的字符串。"""
    head = {"User-Agent": USER_AGENT, "Accept-Encoding": "gzip, deflate"}
    if headers:
        head.update({str(k): str(v) for k, v in headers.items()})

    body = data
    if isinstance(body, str):
        body = body.encode("utf-8")

    req = urllib.request.Request(
        url, data=body, headers=head, method=method or ("POST" if body else "GET")
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            return _decode(raw, resp.headers).decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", "replace")[:200]
        except Exception:  # noqa: BLE001
            pass
        raise HttpError(f"HTTP {exc.code}{('：' + detail) if detail else ''}", exc.code) from exc
    except urllib.error.URLError as exc:
        raise HttpError(f"连不上服务器：{exc.reason}") from exc
    except TimeoutError as exc:
        raise HttpError("请求超时") from exc
    except OSError as exc:
        raise HttpError(f"网络错误：{exc}") from exc


def get(url, headers=None, timeout=15):
    return request(url, headers=headers, timeout=timeout, method="GET")


def post(url, data, headers=None, timeout=15):
    return request(url, data=data, headers=headers, timeout=timeout, method="POST")


def get_bytes(url, headers=None, timeout=15):
    """拿原始字节（图片、音频这类）。"""
    head = {"User-Agent": USER_AGENT, "Accept-Encoding": "identity"}
    if headers:
        head.update({str(k): str(v) for k, v in headers.items()})
    req = urllib.request.Request(url, headers=head)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return _decode(resp.read(), resp.headers)
    except urllib.error.HTTPError as exc:
        raise HttpError(f"HTTP {exc.code}", exc.code) from exc
    except urllib.error.URLError as exc:
        raise HttpError(f"连不上服务器：{exc.reason}") from exc
    except TimeoutError as exc:
        raise HttpError("请求超时") from exc
    except OSError as exc:
        raise HttpError(f"网络错误：{exc}") from exc


def get_json(url, headers=None, timeout=15):
    text = get(url, headers=headers, timeout=timeout)
    try:
        return json.loads(text)
    except ValueError as exc:
        raise HttpError("返回的不是合法 JSON") from exc


def quote(text):
    return urllib.parse.quote(str(text), safe="")
