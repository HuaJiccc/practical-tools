"""运行路径与用户设置的持久化。

数据目录的优先级：环境变量 ``PERSONALTOOLS_DATA`` → exe 旁的 ``data-dir.txt``
（安装程序写的）→ 程序旁边的 ``data`` → 最后才退回 ``%APPDATA%``。
前两个是"用户明确指定过"，后两个是兜底，选中的那个必须真的能写。
"""

import json
import os
import shutil
import sys
import threading
from pathlib import Path

APP_ID = "PersonalTools"

# 只认这些键：别的键写进来会被丢掉，免得设置文件被历史版本的键堆满。
DEFAULT_SETTINGS = {
    "provider": "auto",
    "source_lang": "auto",
    "target_lang": "zh-Hans",
    "auto_translate": False,
    "auto_translate_delay": 900,
    "history_limit": 300,
    "theme": "aurora",
    "glass_blur": 22,
    "glass_opacity": 100,
    "ai_base_url": "",
    "ai_api_key": "",
    "ai_model": "gpt-4o-mini",
    "reminders_enabled": True,
    "use_wmdb": True,
    "tmdb_api_key": "",
    "tmdb_base_url": "https://api.themoviedb.org/3",
    "omdb_api_key": "",
    "use_tvmaze": True,
    "auto_fetch_metadata": True,
    "count_rewatch": True,
    "always_on_top": False,
    "window_width": 1180,
    "window_height": 780,
}


def resource_dir():
    """打包后的资源目录（PyInstaller 解压到 _MEIPASS）或源码根目录。"""
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)
    return Path(__file__).resolve().parent.parent


def web_dir():
    return resource_dir() / "web"


def app_dir():
    """程序自己所在的目录：打包后是 exe 旁边，源码模式是项目根。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def legacy_data_dir():
    """老版本把数据放在这里（roaming AppData），只用于迁移。"""
    base = os.environ.get("APPDATA") or str(Path.home())
    return Path(base) / APP_ID


def _writable(path):
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write-probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


def _override_dir():
    """用户明确指定的数据目录，返回 (路径, 来源说明)，没指定则 (None, '')。"""
    env = (os.environ.get("PERSONALTOOLS_DATA") or "").strip()
    if env:
        return Path(env), "环境变量 PERSONALTOOLS_DATA"

    config = app_dir() / "data-dir.txt"
    try:
        if config.is_file():
            text = config.read_text(encoding="utf-8-sig").strip()
            if text:
                # 只取第一行有效路径：整个文件可能被别的程序写了注释
                first = text.splitlines()[0].strip().strip('"')
                if first:
                    return Path(first), "data-dir.txt"
    except OSError:
        pass
    return None, ""


def data_dir():
    """最终使用的数据目录（缓存一次，运行期不再变）。"""
    override, _source = _override_dir()
    if override is not None:
        try:
            override.mkdir(parents=True, exist_ok=True)
            return override
        except OSError:
            pass

    beside = app_dir() / "data"
    if _writable(beside):
        return beside

    # 程序目录不可写（装在 Program Files 之类）：退回 AppData
    fallback = legacy_data_dir() / "data"
    try:
        fallback.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return fallback


def migrate_legacy_data():
    """把老位置残留的数据搬到当前目录，搬完把老目录删掉。绝不抛异常。"""
    source = legacy_data_dir()
    target = data_dir()
    report = {"moved": [], "removed": False, "from": str(source), "to": str(target)}
    try:
        if not source.is_dir() or source.resolve() == target.resolve():
            return report
        # 老目录下面还有一层 data/ 时以它为准
        root = source / "data" if (source / "data").is_dir() else source
        for item in sorted(root.iterdir()):
            if item.is_dir():
                continue
            dest = target / item.name
            if dest.exists():
                continue
            shutil.copy2(item, dest)
            report["moved"].append(item.name)
        if report["moved"]:
            shutil.rmtree(source, ignore_errors=True)
            report["removed"] = not source.exists()
    except Exception as exc:  # noqa: BLE001 - 迁移失败不该拦住启动
        report["error"] = f"{type(exc).__name__}: {exc}"
    return report


def write_text(path, text):
    """写文件：先写临时文件再改名，改名失败就直接覆盖写。

    AppData 被重定向到另一个卷时，``rename`` 会抛 WinError 17，
    那样会让每一次保存都静默失败，所以改名只当优化。
    """
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(text, encoding="utf-8")
        try:
            os.replace(tmp, path)
        except OSError:
            path.write_text(text, encoding="utf-8")
            try:
                tmp.unlink()
            except OSError:
                pass
        return True
    except OSError:
        try:
            path.write_text(text, encoding="utf-8")
            return True
        except OSError:
            return False


class Settings:
    """线程安全的 JSON 设置存储，只认 DEFAULT_SETTINGS 里的键。"""

    def __init__(self, path):
        self._path = Path(path)
        self._lock = threading.RLock()
        self._data = dict(DEFAULT_SETTINGS)
        self.load()

    def load(self):
        with self._lock:
            try:
                raw = json.loads(self._path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                raw = {}
            if isinstance(raw, dict):
                for key, value in raw.items():
                    if key in DEFAULT_SETTINGS and isinstance(
                        value, type(DEFAULT_SETTINGS[key])
                    ):
                        self._data[key] = value
                    elif key in DEFAULT_SETTINGS and DEFAULT_SETTINGS[key] is None:
                        self._data[key] = value
            return dict(self._data)

    def save(self):
        with self._lock:
            ok = write_text(
                self._path, json.dumps(self._data, ensure_ascii=False, indent=2)
            )
            return ok

    def all(self):
        with self._lock:
            return dict(self._data)

    def get(self, key, default=None):
        with self._lock:
            return self._data.get(key, default)

    def update(self, patch):
        if not isinstance(patch, dict):
            return self.all()
        with self._lock:
            changed = False
            for key, value in patch.items():
                if key not in DEFAULT_SETTINGS:
                    continue  # 白名单之外的键直接丢掉
                if self._data.get(key) != value:
                    self._data[key] = value
                    changed = True
            if changed:
                self.save()
            return dict(self._data)

    def reset(self):
        with self._lock:
            self._data = dict(DEFAULT_SETTINGS)
            self.save()
            return dict(self._data)
