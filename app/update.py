"""检查更新与静默安装。

更新源是可配置的 JSON，两种格式都认：
  1) 自定义清单  {"version": "1.1.0", "notes": "...", "url": "...", "sha256": "..."}
  2) GitHub Releases API 的 /releases/latest ── 直接读 tag_name / body / assets

没有配置更新源、或者网络不通时，check() 会给出明确原因，
界面据此退化成「打开发布页」，不会卡在无响应状态。
"""

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

USER_AGENT = "PracticalTools-Updater/1.0"
MAX_BYTES = 300 * 1024 * 1024


class UpdateError(Exception):
    """检查/下载过程中的可预期错误，消息直接展示给用户。"""


def parse_version(text):
    """"v1.2.3" / "1.2" / "1.2.3.4" 都拆成可比较的元组。"""
    cleaned = str(text or "").strip().lstrip("vV")
    parts = []
    for chunk in cleaned.replace("-", ".").replace("_", ".").split("."):
        digits = ""
        for ch in chunk:
            if ch.isdigit():
                digits += ch
            else:
                break
        parts.append(int(digits) if digits else 0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:4])


def is_newer(latest, current):
    return parse_version(latest) > parse_version(current)


def ascii_url(url):
    """把地址里的中文等非 ASCII 字符转义 —— urllib 只接受 ASCII。"""
    parts = urllib.parse.urlsplit(str(url).strip())
    path = urllib.parse.quote(parts.path, safe="/%:@!$&'()*+,;=~-._")
    query = urllib.parse.quote(parts.query, safe="=&%+")
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, path, query, parts.fragment))


def _fetch_json(url, timeout=8):
    request = urllib.request.Request(ascii_url(url), headers={
        "User-Agent": USER_AGENT,
        "Accept": "application/vnd.github+json, application/json",
    })
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read(2 * 1024 * 1024)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise UpdateError("更新源不存在（404），检查地址是否写错") from exc
        if exc.code in (401, 403):
            raise UpdateError(f"更新源拒绝访问（{exc.code}）") from exc
        raise UpdateError(f"更新源返回 {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise UpdateError(f"连不上更新源：{exc.reason}") from exc
    except TimeoutError as exc:
        raise UpdateError("连接更新源超时") from exc
    try:
        return json.loads(raw.decode("utf-8-sig"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise UpdateError("更新源返回的不是合法 JSON") from exc


def normalize(data):
    """把两种格式统一成 {version, notes, url, page, sha256}。"""
    if not isinstance(data, dict):
        raise UpdateError("更新源格式无法识别")

    if data.get("version"):
        assets = []
        return {
            "version": str(data.get("version")).strip(),
            "notes": str(data.get("notes") or data.get("changelog") or "").strip(),
            "url": str(data.get("url") or data.get("download") or "").strip(),
            "page": str(data.get("page") or data.get("homepage") or "").strip(),
            "sha256": str(data.get("sha256") or "").strip().lower(),
            "assets": assets,
        }

    if data.get("tag_name"):
        # GitHub 的 assets 是倒序返回的（最后上传的排前面），不能直接取第一个：
        # release 里通常同时躺着安装包和免安装版，取错就会「下载了但没装上」。
        # 判定顺序：名字能认出安装包就用它；认不出（比如上传时文件名被吃掉，
        # 变成 "--.exe"）就挑体积最大的，安装包必然大于免安装版；只剩免安装
        # 时才退而求其次。
        url = ""
        sha = ""
        candidates = []
        last = ""
        last_sha = ""
        for asset in data.get("assets") or []:
            name = str(asset.get("name") or "").lower()
            if not name.endswith((".exe", ".msi")):
                continue
            link = str(asset.get("browser_download_url") or "").strip()
            if not link:
                continue
            digest = str(asset.get("digest") or "").strip().lower()
            digest = digest[len("sha256:"):] if digest.startswith("sha256:") else ""
            if "portable" in name or "免安装" in name:
                if not last:
                    last, last_sha = link, digest
                continue
            if "setup" in name or "install" in name or "安装" in name:
                url, sha = link, digest
                break
            candidates.append((int(asset.get("size") or 0), link, digest))
        if not url and candidates:
            candidates.sort(key=lambda item: -item[0])
            url, sha = candidates[0][1], candidates[0][2]
        if not url:
            url, sha = last, last_sha
        return {
            "version": str(data.get("tag_name")).strip(),
            "notes": str(data.get("body") or "").strip(),
            "url": url,
            "page": str(data.get("html_url") or "").strip(),
            "sha256": sha,
        }

    raise UpdateError("更新源里没有版本信息")


def check(current, feed_url, timeout=8):
    """查一次更新。任何异常都转成 ok=False + error，不抛给界面。"""
    feed = str(feed_url or "").strip()
    if not feed:
        return {
            "ok": False,
            "error": "还没有配置更新源",
            "code": "no_feed",
            "current": current,
        }
    try:
        info = normalize(_fetch_json(feed, timeout=timeout))
    except UpdateError as exc:
        return {"ok": False, "error": str(exc), "code": "network", "current": current}

    latest = info["version"]
    return {
        "ok": True,
        "current": current,
        "latest": latest,
        "has_update": is_newer(latest, current),
        "notes": info.get("notes", ""),
        "url": info.get("url", ""),
        "page": info.get("page", ""),
        "sha256": info.get("sha256", ""),
        "feed": feed,
    }


def _sha256_of(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 256), b""):
            digest.update(block)
    return digest.hexdigest()


def download(url, folder=None, sha256="", timeout=30):
    """把安装包下到临时目录，返回本地路径。"""
    if not str(url or "").strip():
        raise UpdateError("更新源没有给出下载地址")

    target_dir = Path(folder or Path(tempfile.gettempdir()) / "practical-tools-update")
    target_dir.mkdir(parents=True, exist_ok=True)
    decoded = urllib.parse.unquote(str(url).split("?")[0].rstrip("/").split("/")[-1]) or "setup.exe"
    name = decoded
    if not name.lower().endswith((".exe", ".msi")):
        name += ".exe"
    target = target_dir / name

    request = urllib.request.Request(ascii_url(url), headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            total = int(response.headers.get("Content-Length") or 0)
            if total > MAX_BYTES:
                raise UpdateError(f"安装包过大（{total / 1048576:.1f} MB）")
            written = 0
            with open(target, "wb") as out:
                while True:
                    block = response.read(1024 * 128)
                    if not block:
                        break
                    written += len(block)
                    if written > MAX_BYTES:
                        raise UpdateError("安装包超出预期大小，已中止")
                    out.write(block)
    except UpdateError:
        raise
    except urllib.error.HTTPError as exc:
        raise UpdateError(f"下载失败（{exc.code}）") from exc
    except urllib.error.URLError as exc:
        raise UpdateError(f"连不上下载地址：{exc.reason}") from exc
    except (TimeoutError, OSError) as exc:
        raise UpdateError(f"下载中断：{exc}") from exc

    if written < 1024:
        raise UpdateError("下载到的文件不完整")

    if sha256:
        actual = _sha256_of(target)
        if actual != sha256.lower():
            try:
                target.unlink()
            except OSError:
                pass
            raise UpdateError("安装包校验失败，可能下载被截断或被替换")

    return {"ok": True, "path": str(target), "size": written, "sha256": _sha256_of(target)}


def launch(path):
    """启动安装包。安装程序自己会接管后续，本进程随后退出。"""
    if not os.path.isfile(path):
        raise UpdateError("安装包不存在，可能已被清理")
    # /SILENT                     显示进度窗口但跳过向导，不打断用户
    # /SUPPRESSMSGBOXES           万一会弹提示框也自动答，否则无人值守时卡死
    # /CLOSEAPPLICATIONS          文件被占用时先尝试正常关闭
    # /FORCECLOSEAPPLICATIONS     关不掉就强制关；安静模式没有对话框可点，只能这样兜底
    # /NORESTART                  不重启系统
    # /LOG                        在临时目录留一份安装日志，出问题能查
    # /DIR="..."                  原地覆盖。静默安装不走向导，不指定就会装到默认目录，
    #                             结果是新旧两个版本并存，用户点的还是旧图标
    args = [
        str(path),
        "/SILENT",
        "/SUPPRESSMSGBOXES",
        "/CLOSEAPPLICATIONS",
        "/FORCECLOSEAPPLICATIONS",
        "/NORESTART",
        "/LOG",
    ]
    if getattr(sys, "frozen", False):
        here = os.path.dirname(os.path.abspath(sys.executable))
        if here:
            # 不能写成 /DIR="路径"：subprocess 会把内层引号转义成 \"，安装程序
            # 反而把引号当成路径的一部分。整只参数交给 subprocess 去加引号。
            args.append(f"/DIR={here}")
    creation = 0
    if sys.platform.startswith("win"):
        creation = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(args, close_fds=True, creationflags=creation)
    return True
