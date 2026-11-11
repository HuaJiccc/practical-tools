"""实用工具 —— 桌面外壳。

界面是纯本地 HTML/CSS/JS，通过本机回环 HTTP 服务和 Python 后端通信。
产品名在此统一定义：窗口标题、任务栏身份、开机自启项都读它。
"""

import base64
import ctypes
import json
import os
import re
import sys
import threading
import time
import traceback
from pathlib import Path

BASE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import webview  # noqa: E402

from ptools import notify  # noqa: E402
from ptools.api import Api  # noqa: E402
from ptools.config import (  # noqa: E402
    Settings,
    app_dir,
    data_dir,
    migrate_legacy_data,
    resource_dir,
    web_dir,
)
from ptools.currency import Currency  # noqa: E402
from ptools.notes import Notes  # noqa: E402
from ptools.picker import Picker  # noqa: E402
from ptools.server import ApiServer  # noqa: E402
from ptools.store import History, LastRecord  # noqa: E402
from ptools.todo import Todo  # noqa: E402

import aitranslate  # noqa: E402
import update as updater  # noqa: E402
from tray import Tray  # noqa: E402
from uistore import (  # noqa: E402
    ChartStore,
    CountdownStore,
    FocusStore,
    MoodStore,
    NoteMetaStore,
    PlanStore,
    PrefsStore,
    _snippet,
)

VERSION = "1.0.2"
APP_NAME = "实用工具"
APP_NAME_EN = "Utility Toolkit"
APP_ID = "PracticalTools.DesktopApp"
AUTHOR = "H.J."
LEGACY_APP_NAMES = ("个人工具",)

# 更新源仓库（形如 "octocat/my-tools"）。换仓库只改这一行。
# 也可以用 settings.json 里的 update_feed 覆盖，
# 或临时用环境变量 PT_UPDATE_FEED 指向本地清单调试。
UPDATE_REPO = "HuaJiccc/practical-tools"
UPDATE_FEED = f"https://api.github.com/repos/{UPDATE_REPO}/releases/latest"
UPDATE_PAGE = f"https://github.com/{UPDATE_REPO}/releases"
UPDATE_PLACEHOLDER = "your-name/practical-tools"

# 关于页展示的本版更新说明（跟 VERSION 一起改）
RELEASE_NOTES = """1.0.2 更新体验修复
· 修掉「下载完装不上」：以前安装过程完全静默，装完也不会重开程序，看着像失败了
· 现在静默安装完成后会自动重新打开程序，装好即可用
· 安装过程加了兜底：文件被占用时强制关闭旧进程，避免后台装到一半退出
· 安装日志留在系统临时目录，出问题可以查"""

RELEASE_NOTES_EN = """1.0.2 update-flow fix
- Fixed "downloads but seems not to install": the silent install never reopened the app
- The app now reopens automatically once a silent install finishes
- The installer force-closes a lingering old process so the files are never locked
- Install logs are kept in the temp folder for troubleshooting"""


def _rebrand_runtime():
    """把 `ptools` 里的产品名改成当前名字，进程内只改一次。

    影响两处：系统通知的发送者名（notify.DISPLAY_NAME）与任务栏标识。
    改名后不做这一步，通知弹出来仍写着旧名字。
    """
    import ptools
    from ptools import api as pt_api
    from ptools import notify as pt_notify

    for module in (ptools, pt_api, pt_notify):
        for attr, value in (
            ("APP_NAME", APP_NAME),
            ("DISPLAY_NAME", APP_NAME),
            ("APP_EN_NAME", APP_NAME_EN),
            ("APP_ID", APP_ID),
        ):
            if hasattr(module, attr):
                try:
                    setattr(module, attr, value)
                except Exception:  # noqa: BLE001
                    pass


_rebrand_runtime()

_LANG_NAMES = None


def _lang_name(code):
    """语言 id → 中文名。目录有 53 条，缓存一份别每次重建。"""
    global _LANG_NAMES
    if _LANG_NAMES is None:
        try:
            from ptools import languages

            _LANG_NAMES = {item["id"]: item["name"] for item in languages.catalogue()}
        except Exception:
            _LANG_NAMES = {}
    return _LANG_NAMES.get(code or "")


def extra_provider_label(provider):
    return {aitranslate.AI: "AI 接口", aitranslate.TRANSMART: "腾讯交互翻译"}.get(provider, provider or "")

# 旧版遗留在设置文件里的键（影视书籍接口、玻璃材质参数），保存时顺手清掉。
LEGACY_SETTING_KEYS = {
    "glass_blur",
    "glass_opacity",
    "use_wmdb",
    "tmdb_api_key",
    "tmdb_base_url",
    "omdb_api_key",
    "use_tvmaze",
    "auto_fetch_metadata",
    "count_rewatch",
}


def strip_legacy_settings():
    """把设置文件里与已移除功能相关的键删掉。"""
    path = data_dir() / "settings.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return
    cleaned = {key: value for key, value in raw.items() if key not in LEGACY_SETTING_KEYS}
    if cleaned == raw:
        return
    try:
        path.write_text(json.dumps(cleaned, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


# —— 存储位置（v2.6）：数据目录走 ptools 的 data-dir.txt，图片目录走界面偏好 ——

DATA_DIR_FILE = "data-dir.txt"
EXPORT_DIRNAME = "exports"


def data_dir_file() -> Path:
    """``data-dir.txt`` 的位置：打包版在 exe 旁边，源码模式在 app/ 下。"""
    return app_dir() / DATA_DIR_FILE


def read_data_override() -> str:
    """读出用户指定的数据目录；没指定或文件坏了都返回空串。"""
    try:
        for line in data_dir_file().read_text(encoding="utf-8-sig").splitlines():
            text = line.strip()
            if text and not text.startswith("#"):
                return text
    except OSError:
        pass
    return ""


def install_data_dir() -> "Path | None":
    """安装版的数据目录（%LOCALAPPDATA%\\实用工具\\data）；免安装版返回 None。

    判定依据是程序装在 %LOCALAPPDATA%\\Programs 下 —— 这是 Inno 按用户安装时的
    默认位置。这种装法下把数据放在用户目录比塞进安装目录更合适：卸载不会连带
    删除，也不需要管理员权限。

    安装包会写 data-dir.txt 指向这里，所以界面上要把它当作「默认」而不是
    「自定义」——用户并没有做过选择。
    """
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        return None
    try:
        app_dir().resolve().relative_to((Path(local) / "Programs").resolve())
    except (ValueError, OSError):
        return None
    return Path(local) / APP_NAME / "data"


def installer_data_dir():
    """安装程序约定的数据目录：%LOCALAPPDATA%\\<产品名>\\data。

    和 install_data_dir() 的区别：这里不看 exe 装在哪。用户把程序装到 D 盘时，
    安装包写下的仍然是这个路径，界面应当把它当「默认」而不是「自定义」。
    """
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        return None
    return Path(local) / APP_NAME / "data"


def dir_writable(path: Path) -> bool:
    """真写一个探针文件，比 os.access 可靠（Windows 上后者基本没用）。"""
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write-probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


def export_dir_of(prefs) -> Path:
    """图片保存目录：优先用户设置，目录不在了/不可写就回落到 data/exports。"""
    raw = ""
    if prefs is not None:
        raw = str(prefs.all().get("export_dir") or "").strip()
    if raw:
        try:
            target = Path(raw).expanduser()
            target.mkdir(parents=True, exist_ok=True)
            return target
        except OSError:
            pass
    fallback = data_dir() / EXPORT_DIRNAME
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def copy_user_data(src: Path, dst: Path) -> int:
    """把现有数据搬到新目录：只搬 json 记录和 exports / backup，同名不覆盖。

    webview 缓存（几百 MB 的 Chromium 数据）不搬，搬到新地方也会重建。
    """
    import shutil

    copied = 0
    dst.mkdir(parents=True, exist_ok=True)
    try:
        items = list(src.iterdir())
    except OSError:
        return 0
    for item in items:
        if item.name in ("webview", ".write-probe"):
            continue
        target = dst / item.name
        try:
            if item.is_file() and item.suffix.lower() == ".json":
                if not target.exists():
                    shutil.copy2(item, target)
                    copied += 1
            elif item.is_dir() and item.name in (EXPORT_DIRNAME, "backup"):
                for sub in item.rglob("*"):
                    if not sub.is_file():
                        continue
                    out = target / sub.relative_to(item)
                    if out.exists():
                        continue
                    out.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(sub, out)
                    copied += 1
        except OSError:
            continue
    return copied


def apply_dark_titlebar(dark):
    """让系统标题栏跟随深浅主题（Windows 10/11）。"""
    try:
        hwnd = ctypes.windll.user32.FindWindowW(None, APP_NAME)
        if not hwnd:
            return False
        value = ctypes.c_int(1 if dark else 0)
        for attribute in (20, 19):
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, attribute, ctypes.byref(value), ctypes.sizeof(value)
            ) == 0:
                return True
    except Exception:
        pass
    return False


class UiApi:
    """只暴露新界面需要的接口。

    所有 media_* 方法都会被拦掉；bootstrap 也由这里自己组装，
    不再依赖影视书籍的元数据。
    """

    def __init__(self, api, plan=None, note_meta=None, focus=None, countdown=None, mood=None, chart=None, exports=None, prefs=None, tray_host=None):
        object.__setattr__(self, "_api", api)
        object.__setattr__(self, "_plan", plan)
        object.__setattr__(self, "_note_meta", note_meta)
        object.__setattr__(self, "_focus", focus)
        object.__setattr__(self, "_countdown", countdown)
        object.__setattr__(self, "_mood", mood)
        object.__setattr__(self, "_chart", chart)
        object.__setattr__(self, "_exports", exports)
        object.__setattr__(self, "_prefs", prefs)
        object.__setattr__(self, "_tray_host", tray_host)
        object.__setattr__(self, "_window", None)

    def bind_window(self, window):
        """窗口建好之后回填一份，目录选择框要用它。"""
        object.__setattr__(self, "_window", window)

    def __getattr__(self, name):
        if name.startswith("media_"):
            raise AttributeError(name)
        return getattr(self._api, name)

    # —— 翻译：内置四渠道原样透传，扩展渠道（AI / 腾讯交互翻译）在这里接 ——

    def translate(self, text, source="auto", target="zh-Hans", provider=None, remember=True):
        key = (provider or "").strip().lower()
        if key in (aitranslate.AI, aitranslate.TRANSMART):
            return self._translate_extra(text, source, target, key, remember)

        out = self._api.translate(text, source, target, provider, remember)
        # 智能选择时内置四渠道全挂了（常见于外网被墙），再用腾讯交互翻译兜一次
        if key in ("", "auto") and isinstance(out, dict) and not out.get("ok"):
            fallback = self._translate_extra(text, source, target, aitranslate.TRANSMART, remember)
            if fallback.get("ok"):
                fallback["attempts"] = [{"provider": "auto", "error": out.get("error")}]
                return fallback
        return out

    def _translate_extra(self, text, source, target, provider, remember):
        started = time.time()
        settings = self._api.settings.all()

        def name(code, fallback=""):
            return _lang_name(code) or fallback or code or ""

        try:
            if provider == aitranslate.AI:
                result = aitranslate.translate_ai(text, source, target, settings, name)
                label = aitranslate.ai_label(settings)
            else:
                result = aitranslate.translate_transmart(text, source, target, name)
                label = "腾讯交互翻译"
        except aitranslate.ExtraError as exc:
            return {"ok": False, "error": str(exc), "provider": provider, "provider_label": extra_provider_label(provider), "attempts": []}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"翻译失败：{exc}", "provider": provider, "provider_label": extra_provider_label(provider), "attempts": []}

        elapsed = int((time.time() - started) * 1000)
        entry = None
        if remember:
            try:
                entry = self._api.history.add(text, result["text"], source, target, provider, label)
            except Exception:
                entry = None
        stats = None
        try:
            stats = self._api.history.stats()
        except Exception:
            pass
        return {
            "ok": True,
            "text": result["text"],
            "translit": "",
            "tts": "",
            "source": source,
            "target": target,
            "detected": result.get("detected") or "",
            "detected_name": result.get("detected_name") or "",
            "same_language": False,
            "provider": provider,
            "provider_label": label,
            "elapsed_ms": elapsed,
            "attempts": [],
            "entry": entry,
            "stats": stats,
        }

    def ai_test(self):
        """设置页的「测试连接」：用当前保存的配置真翻一句，把耗时和回显带回来。"""
        settings = self._api.settings.all()
        try:
            out = aitranslate.test_ai(settings, lambda code, fb="": _lang_name(code) or fb or code or "")
        except aitranslate.ExtraError as exc:
            return {"ok": False, "error": str(exc)}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"测试失败：{exc}"}
        return {"ok": True, **out}

    def probe(self):
        """内置四渠道沿用原实现，再把腾讯交互翻译和 AI 接口补进结果里。"""
        out = self._api.probe()
        results = list(out.get("results") or [])
        settings = self._api.settings.all()

        def name(code, fallback=""):
            return _lang_name(code) or fallback or code or ""

        started = time.time()
        try:
            got = aitranslate.translate_transmart("hello", "auto", "zh-Hans", name)
            results.append({
                "key": aitranslate.TRANSMART, "label": "腾讯交互翻译", "ok": True,
                "latency_ms": int((time.time() - started) * 1000), "sample": got["text"][:20],
            })
        except Exception as exc:  # noqa: BLE001
            results.append({
                "key": aitranslate.TRANSMART, "label": "腾讯交互翻译", "ok": False,
                "latency_ms": int((time.time() - started) * 1000), "error": str(exc),
            })

        started = time.time()
        if not aitranslate.ai_ready(settings):
            results.append({
                "key": aitranslate.AI, "label": "AI 接口", "ok": False,
                "latency_ms": 0, "error": "还没配置接口地址和 Key",
            })
        else:
            try:
                got = aitranslate.translate_ai("hello", "auto", "zh-Hans", settings, name)
                results.append({
                    "key": aitranslate.AI, "label": aitranslate.ai_label(settings), "ok": True,
                    "latency_ms": int((time.time() - started) * 1000), "sample": got["text"][:20],
                })
            except Exception as exc:  # noqa: BLE001
                results.append({
                    "key": aitranslate.AI, "label": aitranslate.ai_label(settings), "ok": False,
                    "latency_ms": int((time.time() - started) * 1000), "error": str(exc),
                })

        return {"ok": True, "results": results}

    def image_save(self, name, data_b64):
        """把前端生成的图片/GIF 落盘到「图片保存目录」，重名自动加序号。"""
        if not data_b64:
            return {"ok": False, "error": "没有可写入的内容"}
        try:
            raw = base64.b64decode(data_b64, validate=False)
        except Exception:
            return {"ok": False, "error": "数据损坏，无法解码"}
        if not raw:
            return {"ok": False, "error": "内容为空"}
        if len(raw) > 200 * 1024 * 1024:
            return {"ok": False, "error": "文件超过 200 MB"}

        clean = re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", str(name or "图片")).strip(" .") or "图片"
        if len(clean) > 90:
            stem, dot, ext = clean.rpartition(".")
            clean = (stem[: 90 - len(ext) - 1] + dot + ext) if dot else clean[:90]
        target_dir = export_dir_of(self._prefs)
        target_dir.mkdir(parents=True, exist_ok=True)

        path = target_dir / clean
        if path.exists():
            stem, dot, ext = clean.rpartition(".")
            if not dot:
                stem, ext = clean, ""
            for index in range(2, 500):
                candidate = target_dir / (f"{stem}-{index}.{ext}" if ext else f"{stem}-{index}")
                if not candidate.exists():
                    path = candidate
                    break
        try:
            path.write_bytes(raw)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"写入失败：{exc}"}
        return {"ok": True, "path": str(path), "name": path.name, "size": len(raw)}

    def image_open_dir(self):
        """打开图片保存目录（保存后想马上看看结果）。"""
        path = export_dir_of(self._prefs)
        try:
            os.startfile(str(path))
            return {"ok": True, "path": str(path)}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)}

    def ui_theme(self, theme="light"):
        return {"ok": apply_dark_titlebar(str(theme) == "dark")}

    def ui_prefs(self, patch=None):
        """界面偏好（主题色 / 密度 / 动效 / 启动页…）的读写。

        localStorage 按源隔离，本地服务端口每次都变，靠它记不住，
        所以真正的副本存在 data/ui_prefs.json。
        """
        if not self._prefs:
            return {"ok": False, "error": "偏好存储未初始化", "prefs": {}}
        if patch is None:
            return {"ok": True, "prefs": self._prefs.all()}
        merged = self._prefs.update(patch)
        if self._tray_host:
            try:
                self._tray_host.refresh_label()
            except Exception:
                pass
        # 窗口标题跟着界面语言走
        lang = str(merged.get("language") or "zh").lower()
        if self._window:
            try:
                self._window.set_title(APP_NAME_EN if lang.startswith("en") else APP_NAME)
            except Exception:
                pass
        return {"ok": True, "prefs": merged}

    def close_decision(self, action="", remember=True):
        """用户在「关闭窗口要怎样」里做的选择。

        第一次点 × 时前端弹框问一次，选完写进 ui_prefs.close_action，
        以后点 × 直接照做；设置里可以改回「先问我」。
        """
        act = str(action or "").strip().lower()
        if act not in ("tray", "quit"):
            return {"ok": False, "error": "无效的选择"}

        host = self._tray_host
        if self._prefs and remember:
            self._prefs.update({"close_action": act})

        if act == "quit":
            if host:
                host.quit()
            elif self._window:
                try:
                    self._window.destroy()
                except Exception:
                    os._exit(0)
            return {"ok": True, "action": "quit"}

        if host and host.available:
            host.hide_later(balloon=False)
            return {"ok": True, "action": "tray"}

        # 没托盘可收：留在窗口，别让程序凭空消失
        return {"ok": False, "error": "托盘图标不可用，程序仍在运行"}

    # ---- v2.5：通用 / 数据 / 关于 设置项 ----
    def sys_autostart(self, enabled=None):
        """读写开机自启（HKCU\\...\\Run，不需要管理员，不弹黑窗）。

        改名前留下的旧项会在读取时自动接到新名下，避免升级后自启悄悄失效。
        """
        name = APP_NAME
        run_key = r"Software\Microsoft\Windows\CurrentVersion\Run"
        if getattr(sys, "frozen", False):
            command = f'"{Path(sys.executable)}"'
        else:
            command = f'"{Path(sys.executable)}" "{Path(__file__).resolve().parent / "app.py"}"'
        try:
            import winreg

            if enabled is None:
                try:
                    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, run_key) as key:
                        value, _ = winreg.QueryValueEx(key, name)
                    return {"ok": True, "enabled": bool(str(value).strip()), "command": command}
                except FileNotFoundError:
                    pass
                migrated = self._adopt_legacy_autostart(run_key, name, command)
                return {"ok": True, "enabled": migrated, "command": command}
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, run_key, 0, winreg.KEY_SET_VALUE) as key:
                if enabled:
                    winreg.SetValueEx(key, name, 0, winreg.REG_SZ, command)
                else:
                    try:
                        winreg.DeleteValue(key, name)
                    except FileNotFoundError:
                        pass
            return {"ok": True, "enabled": bool(enabled), "command": command}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"写注册表失败：{exc}"}

    @staticmethod
    def _adopt_legacy_autostart(run_key, name, command):
        """把旧产品名下的自启项改写成当前名字，返回是否接管到了。"""
        try:
            import winreg
        except Exception:
            return False
        adopted = False
        for old in LEGACY_APP_NAMES:
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, run_key) as key:
                    old_value, _ = winreg.QueryValueEx(key, old)
            except FileNotFoundError:
                continue
            if not str(old_value).strip():
                continue
            try:
                with winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER, run_key, 0, winreg.KEY_SET_VALUE
                ) as key:
                    winreg.SetValueEx(key, name, 0, winreg.REG_SZ, command)
                    try:
                        winreg.DeleteValue(key, old)
                    except FileNotFoundError:
                        pass
                adopted = True
            except OSError:
                continue
        return adopted

    def data_stats(self):
        """统计数据目录占用（跳过 webview 缓存，那个不算用户数据）。"""
        root = data_dir()

        def measure(path):
            if path.is_file():
                try:
                    return path.stat().st_size, 1
                except OSError:
                    return 0, 0
            total = 0
            count = 0
            if not path.is_dir():
                return 0, 0
            for item in path.rglob("*"):
                if item.is_file():
                    try:
                        total += item.stat().st_size
                        count += 1
                    except OSError:
                        continue
            return total, count

        rows = []
        total = 0
        total_files = 0
        try:
            for item in root.iterdir():
                if not item.is_file() or item.suffix.lower() != ".json":
                    continue
                size, count = measure(item)
                rows.append({"name": item.stem, "size": size, "count": count})
                total += size
                total_files += count
        except OSError:
            pass
        exports = export_dir_of(self._prefs)
        exp_size, exp_count = measure(exports)
        rows.sort(key=lambda row: -row["size"])
        return {
            "ok": True,
            "dir": str(root),
            "exports_dir": str(exports),
            "total": total + exp_size,
            "files": total_files + exp_count,
            "rows": rows[:8],
            "exports": {"size": exp_size, "count": exp_count},
        }

    # ---- v2.6：存储位置可自定义 ----

    def dirs_info(self):
        """当前两个目录在哪、是不是用户改过、能不能改。"""
        override = read_data_override()
        prefs = self._prefs.all() if self._prefs else {}
        custom_export = str(prefs.get("export_dir") or "").strip()
        default_dir = install_data_dir() or (app_dir() / "data")
        # 安装包写的默认值也算默认：用户没选过，界面不该显示「自定义」
        at_default = False
        if override:
            try:
                current = Path(override).resolve()
                at_default = current == Path(default_dir).resolve()
                inst = installer_data_dir()
                if not at_default and inst is not None and current == inst.resolve():
                    at_default = True
                    default_dir = inst
            except OSError:
                at_default = False
        return {
            "ok": True,
            "data_dir": str(data_dir()),
            "data_default": str(default_dir),
            "data_override": override,
            "data_custom": bool(override) and not at_default,
            # 程序目录本身不可写时，没法记住选择（data-dir.txt 没地方放）
            "can_move_data": dir_writable(app_dir()),
            "export_dir": str(export_dir_of(self._prefs)),
            "export_default": str(data_dir() / EXPORT_DIRNAME),
            "export_custom": bool(custom_export),
        }

    def pick_folder(self, current=""):
        """弹系统目录选择框，返回用户选的路径；取消时 cancelled 为真。"""
        window = getattr(self, "_window", None)
        if window is None:
            return {"ok": False, "error": "窗口还没准备好，稍后再试"}
        try:
            import webview as _webview

            folder = getattr(getattr(_webview, "FileDialog", None), "FOLDER", None)
            if folder is None:  # 老版本 pywebview
                folder = _webview.FOLDER_DIALOG
            start = current if current and Path(current).is_dir() else str(Path.home())
            picked = window.create_file_dialog(folder, directory=start)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"打开选择框失败：{exc}"}
        if not picked:
            return {"ok": False, "cancelled": True}
        return {"ok": True, "path": str(picked[0])}

    def data_set_dir(self, path):
        """切换数据目录：校验可写 → 搬一份现有数据 → 写 data-dir.txt，重启生效。"""
        text = str(path or "").strip()
        if not text:
            return {"ok": False, "error": "路径为空"}
        target = Path(text).expanduser()
        current = data_dir().resolve()
        try:
            resolved = target.resolve()
        except OSError:
            resolved = target
        if resolved == current:
            return {"ok": True, "restart": False, "copied": 0, "path": str(current)}
        if not dir_writable(target):
            return {"ok": False, "error": "这个目录没有写入权限，换一个试试"}
        if not dir_writable(app_dir()):
            return {
                "ok": False,
                "error": "程序所在目录不可写，没法记住你的选择。把程序放到「文档」这类可写位置后再试",
            }
        copied = 0
        # 新目录建在当前数据目录里面时不搬，免得套娃
        if current not in resolved.parents:
            copied = copy_user_data(current, target)
        try:
            # ptools 只读第一行有效路径，写注释会让它整段失效，这里只写路径
            data_dir_file().write_text(f"{target}\n", encoding="utf-8")
        except OSError as exc:
            return {"ok": False, "error": f"写入配置失败：{exc}"}
        return {"ok": True, "restart": True, "copied": copied, "path": str(target)}

    def data_reset_dir(self):
        """恢复默认数据目录，重启生效。

        安装版把配置写回用户目录，而不是删文件 —— 删掉的话重启后会落到安装
        目录里的 data，卸载时会被一并清理，等于把数据放到了会消失的地方。
        """
        default_dir = install_data_dir() or (app_dir() / "data")
        path = data_dir_file()
        if install_data_dir() is not None:
            try:
                path.write_text(str(default_dir), encoding="utf-8")
            except OSError as exc:
                return {"ok": False, "error": f"写入配置失败：{exc}"}
            restart = Path(str(default_dir)).resolve() != Path(data_dir()).resolve()
            return {"ok": True, "restart": restart, "path": str(default_dir)}
        if not path.exists():
            return {"ok": True, "restart": False, "path": str(data_dir())}
        try:
            path.unlink()
        except OSError as exc:
            return {"ok": False, "error": f"删除配置失败：{exc}"}
        return {"ok": True, "restart": True, "path": str(default_dir)}

    def export_set_dir(self, path):
        """设置图片保存目录，立即生效（下一次保存就写到这里）。"""
        text = str(path or "").strip()
        if not text:
            return {"ok": False, "error": "路径为空"}
        target = Path(text).expanduser()
        if not dir_writable(target):
            return {"ok": False, "error": "这个目录没有写入权限，换一个试试"}
        if self._prefs:
            self._prefs.update({"export_dir": str(target)})
        return {"ok": True, "path": str(target)}

    def export_reset_dir(self):
        """图片保存目录改回默认（数据目录下的 exports）。"""
        if self._prefs:
            self._prefs.update({"export_dir": ""})
        target = data_dir() / EXPORT_DIRNAME
        target.mkdir(parents=True, exist_ok=True)
        return {"ok": True, "path": str(target)}

    def app_restart(self):
        """重启自己。改了数据目录必须重启，否则新位置不会生效。"""
        import subprocess
        import threading

        if getattr(sys, "frozen", False):
            args = [sys.executable]
        else:
            args = [sys.executable, str(BASE_DIR / "app.py")]
        try:
            subprocess.Popen(
                args,
                cwd=str(app_dir()),
                creationflags=0x00000008,  # DETACHED_PROCESS，新进程不跟着一起死
                close_fds=True,
            )
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"重启失败：{exc}"}
        threading.Timer(0.6, lambda: os._exit(0)).start()
        return {"ok": True}

    def data_backup(self):
        """把 data 下的 json 记录复制到 data/backup/时间戳 里。"""
        import shutil

        root = data_dir()
        target = root / "backup" / time.strftime("%Y%m%d-%H%M%S")
        copied = 0
        try:
            target.mkdir(parents=True, exist_ok=True)
            for item in root.iterdir():
                if item.is_file() and item.suffix.lower() == ".json":
                    shutil.copy2(item, target / item.name)
                    copied += 1
            if not copied:
                return {"ok": False, "error": "还没有可备份的数据"}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"备份失败：{exc}"}
        return {"ok": True, "path": str(target), "count": copied}

    def open_exports(self):
        return self.image_open_dir()

    def open_guide(self):
        """打开安装目录里的使用说明。"""
        exe_dir = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent
        for name in ("使用说明.txt", "使用说明.md", "README.md"):
            path = exe_dir / name
            if path.exists():
                try:
                    os.startfile(str(path))
                    return {"ok": True, "path": str(path)}
                except Exception as exc:  # noqa: BLE001
                    return {"ok": False, "error": str(exc)}
        return {"ok": False, "error": "没找到「使用说明.txt」"}

    def diag_info(self):
        """拼一段运行信息，方便反馈问题时贴出来（不含任何密钥）。"""
        import platform

        settings = self._api.settings.all()
        root = data_dir()
        total = 0
        try:
            for item in root.rglob("*"):
                if item.is_file() and "webview" not in item.parts:
                    total += item.stat().st_size
        except OSError:
            pass
        edge = ""
        try:
            import winreg

            key = r"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key) as handle:
                edge, _ = winreg.QueryValueEx(handle, "pv")
        except Exception:  # noqa: BLE001
            edge = ""
        lang = str((self._prefs.all() if self._prefs else {}).get("language") or "zh").lower()
        en = lang.startswith("en")
        ai_model = (settings.get("ai_model") or "").strip()
        ai = (
            (f"configured {ai_model}".strip() if en else f"已配置 {ai_model}".strip())
            if (settings.get("ai_api_key") or "").strip()
            else ("not configured" if en else "未配置")
        )
        items = [
            ["Version" if en else "版本", VERSION],
            ["Author" if en else "作者", AUTHOR],
            ["System" if en else "系统", f"{platform.system()} {platform.release()} ({platform.version()})"],
            ["Python", f"{platform.python_version()} {platform.machine()}"],
            ["WebView2", edge or ("not detected" if en else "未读取到")],
            ["Build" if en else "运行方式",
             ("packaged" if en else "打包版") if getattr(sys, "frozen", False) else ("source" if en else "源码")],
            ["Data folder" if en else "数据目录", str(root)],
            ["Data size" if en else "数据占用", f"{total / 1048576:.2f} MB"],
            ["Channel" if en else "翻译通道", settings.get("provider") or "auto"],
            ["AI API" if en else "AI 接口", ai],
            ["Reminders" if en else "待办提醒",
             ("on" if en else "开") if settings.get("reminders_enabled", True) else ("off" if en else "关")],
        ]
        sep = ": " if en else "："
        text = "\n".join(f"{name}{sep}{value}" for name, value in items)
        return {"ok": True, "items": items, "text": text}

    # ---- v1.0：关于页、检查更新、原地安装 ----

    def app_about(self):
        """关于页要的东西：版本、本版说明、发布页地址。"""
        settings = self._api.settings.all()
        prefs = self._prefs.all() if self._prefs else {}
        lang = str(prefs.get("language") or "zh").lower()
        return {
            "ok": True,
            "version": VERSION,
            "name": APP_NAME,
            "name_en": APP_NAME_EN,
            "author": AUTHOR,
            "repo": "" if UPDATE_PLACEHOLDER in UPDATE_REPO else UPDATE_REPO,
            "notes": RELEASE_NOTES_EN if lang.startswith("en") else RELEASE_NOTES,
            "page": settings.get("update_page") or UPDATE_PAGE,
            "feed": settings.get("update_feed") or UPDATE_FEED,
            "frozen": bool(getattr(sys, "frozen", False)),
        }

    def update_check(self):
        """查一次更新。配置错了、断网了都返回 ok=False 和一句能看懂的原因。"""
        settings = self._api.settings.all()
        feed = os.environ.get("PT_UPDATE_FEED") or settings.get("update_feed") or UPDATE_FEED
        page = settings.get("update_page") or UPDATE_PAGE
        # 仓库地址还是占位符时直接说明，别让人看到「404 更新源不存在」以为是坏了
        if UPDATE_PLACEHOLDER in feed and not os.environ.get("PT_UPDATE_FEED"):
            return {
                "ok": False,
                "code": "no_feed",
                "current": VERSION,
                "page": page,
                "error": "还没有配置更新源：作者尚未填写发布仓库地址",
            }
        result = updater.check(VERSION, feed)
        result.setdefault("page", page)
        return result

    def update_install(self, url="", sha256="", dry=None):
        """下载并启动安装包。源码模式下只下载不安装，方便调试。"""
        if not str(url or "").strip():
            return {"ok": False, "error": "没有可下载的地址"}
        try:
            got = updater.download(url, sha256=sha256 or "")
        except updater.UpdateError as exc:
            return {"ok": False, "error": str(exc)}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"下载失败：{exc}"}

        frozen = bool(getattr(sys, "frozen", False))
        if dry is None:
            dry = os.environ.get("PT_UPDATE_DRY") == "1"
        if not frozen or dry:
            return {
                "ok": True,
                "downloaded": True,
                "installed": False,
                "path": got["path"],
                "size": got["size"],
                "note": "源码/调试模式：已下载，未执行安装",
            }

        try:
            updater.launch(got["path"])
        except updater.UpdateError as exc:
            return {"ok": False, "error": str(exc)}
        self._schedule_exit()
        return {"ok": True, "downloaded": True, "installed": True, "path": got["path"], "size": got["size"]}

    def update_open_page(self, url=""):
        """打开发布页 —— 没配置更新源时的兜底路径。"""
        settings = self._api.settings.all()
        target = str(url or settings.get("update_page") or UPDATE_PAGE).strip()
        if not target.startswith(("http://", "https://")):
            return {"ok": False, "error": "发布页地址无效"}
        if UPDATE_PLACEHOLDER in target:
            return {"ok": False, "error": "发布页还没建好：作者尚未填写仓库地址"}
        try:
            import webbrowser

            webbrowser.open(target)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"打开浏览器失败：{exc}"}
        return {"ok": True, "url": target}

    def _schedule_exit(self):
        """安装程序启动后本进程要让位，否则文件被占用装不上去。

        留 2.5 秒是给界面把「即将关闭并安装」那句话显示完 —— 退出太快
        用户只看到窗口消失，会以为程序崩了。
        """

        def bye():
            host = self._tray_host
            if host:
                try:
                    host.stop()
                except Exception:
                    pass
            os._exit(0)

        threading.Timer(2.5, bye).start()


    def save_settings(self, patch):
        result = self._api.save_settings(patch)
        strip_legacy_settings()
        return result

    # ---- 每日规划（v2.1 新增，独立 JSON 存储）----
    def plan_get(self, date):
        if not self._plan:
            return {"ok": False, "error": "规划存储未初始化"}
        return {"ok": True, "date": str(date), "items": self._plan.get(date), "stats": self._plan.stats(date)}

    def plan_save(self, date, items):
        if not self._plan:
            return {"ok": False, "error": "规划存储未初始化"}
        saved = self._plan.save(date, items)
        return {"ok": True, "date": str(date), "items": saved, "stats": self._plan.stats(date)}

    def plan_clear(self, date):
        if not self._plan:
            return {"ok": False, "error": "规划存储未初始化"}
        self._plan.save(date, [])
        return {"ok": True, "date": str(date), "items": [], "stats": self._plan.stats(date)}

    # ---- 笔记分类（同样独立存储）----
    def note_meta_all(self):
        return {"ok": True, "map": self._note_meta.all() if self._note_meta else {}}

    def note_meta_set(self, note_id, category):
        if not self._note_meta:
            return {"ok": False, "error": "分类存储未初始化"}
        self._note_meta.set(note_id, category)
        return {"ok": True, "map": self._note_meta.all()}

    def note_meta_prune(self, note_ids):
        if not self._note_meta:
            return {"ok": True, "removed": 0}
        removed = self._note_meta.prune(note_ids or [])
        return {"ok": True, "removed": removed, "map": self._note_meta.all()}

    def notes_delete(self, note_id):
        result = self._api.notes_delete(note_id)
        if isinstance(result, dict) and result.get("ok") and self._note_meta:
            self._note_meta.remove(note_id)
        return result

    # ---- 番茄钟（v2.2）----
    def focus_log(self, entry):
        if not self._focus:
            return {"ok": False, "error": "记录存储未初始化"}
        item = self._focus.add(entry)
        return {"ok": True, "item": item, "stats": self._focus.stats()}

    def focus_state(self, limit=12):
        if not self._focus:
            return {"ok": False, "error": "记录存储未初始化"}
        return {"ok": True, "sessions": self._focus.recent(limit), "stats": self._focus.stats()}

    def ui_notify(self, title, body=""):
        """番茄钟结束之类的轻提示，走系统通知。"""
        try:
            from ptools import notify as _notify

            ok = _notify.toast(str(title), str(body), icon_path())
            return {"ok": bool(ok)}
        except Exception as exc:  # 通知失败不该影响计时
            return {"ok": False, "error": str(exc)}

    # ---- 倒数日 ----
    def countdown_all(self):
        if not self._countdown:
            return {"ok": False, "error": "存储未初始化"}
        return {"ok": True, "items": self._countdown.all()}

    def countdown_save(self, item):
        if not self._countdown:
            return {"ok": False, "error": "存储未初始化"}
        saved = self._countdown.upsert(item)
        if not saved:
            return {"ok": False, "error": "标题不能为空"}
        return {"ok": True, "item": saved, "items": self._countdown.all()}

    def countdown_delete(self, item_id):
        if not self._countdown:
            return {"ok": False, "error": "存储未初始化"}
        removed = self._countdown.remove(item_id)
        return {"ok": True, "removed": removed, "items": self._countdown.all()}

    # ---- 心情日记 ----
    def mood_month(self, ym):
        if not self._mood:
            return {"ok": False, "error": "存储未初始化"}
        return {"ok": True, "month": str(ym), "days": self._mood.month(ym), "stats": self._mood.stats(ym)}

    def mood_set(self, day, mood, text=""):
        if not self._mood:
            return {"ok": False, "error": "存储未初始化"}
        entry = self._mood.set(day, mood, text)
        month = str(day)[:7]
        return {"ok": True, "entry": entry, "days": self._mood.month(month), "stats": self._mood.stats(month)}

    def mood_delete(self, day):
        if not self._mood:
            return {"ok": False, "error": "存储未初始化"}
        self._mood.remove(day)
        month = str(day)[:7]
        return {"ok": True, "days": self._mood.month(month), "stats": self._mood.stats(month)}

    def mood_recent(self, limit=8):
        if not self._mood:
            return {"ok": False, "error": "存储未初始化"}
        return {"ok": True, "items": self._mood.recent(limit)}

    # ---- 数据成图 ----
    def chart_last(self):
        if not self._chart:
            return {"ok": True, "last": None}
        return {"ok": True, "last": self._chart.get()}

    def chart_save(self, payload):
        if not self._chart:
            return {"ok": False, "error": "存储未初始化"}
        return {"ok": True, "last": self._chart.save(payload)}

    # ---- 全局搜索 ----
    def search_all(self, query, limit=40):
        q = str(query or "").strip()
        if not q:
            return {"ok": True, "query": "", "items": []}
        low = q.lower()
        per_type = max(4, int(limit) // 4)
        groups = []
        api = self._api

        def collect(kind, rows):
            found = []
            for row in rows:
                if len(found) >= per_type:
                    break
                found.append(row)
            if found:
                groups.append((kind, found))

        # 笔记：标题和正文都搜
        try:
            rows = []
            for note in (api.notes.list() if api.notes else []):
                title = note.get("title") or "无标题"
                content = note.get("content") or ""
                if low in title.lower() or low in content.lower():
                    rows.append({
                        "type": "note",
                        "id": note.get("id"),
                        "title": title,
                        "sub": _snippet(content, q),
                        "ts": note.get("updated") or note.get("ts") or 0,
                    })
            rows.sort(key=lambda r: r["ts"] or 0, reverse=True)
            collect("note", rows)
        except Exception:
            pass

        # 待办：标题和备注
        try:
            rows = []
            for item in (api.todo.list("all") if api.todo else []):
                if low in (item.get("title") or "").lower() or low in (item.get("notes") or "").lower():
                    due = (item.get("due_at") or "").replace("T", " ")
                    sub = "已完成" if item.get("status") == "done" else (due or "没定时间")
                    rows.append({
                        "type": "todo",
                        "id": item.get("id"),
                        "title": item.get("title") or "",
                        "sub": sub,
                        "ts": item.get("created_at") or 0,
                        "done": item.get("status") == "done",
                    })
            rows.sort(key=lambda r: r["ts"] or 0, reverse=True)
            collect("todo", rows)
        except Exception:
            pass

        # 每日规划：最近半年的标题和备注
        try:
            rows = []
            for item in (self._plan.search(q, limit=per_type * 2) if self._plan else []):
                rows.append({
                    "type": "plan",
                    "id": item.get("id"),
                    "title": item.get("title") or "",
                    "sub": f"{item.get('date')} {item.get('start')}–{item.get('end')}",
                    "ts": 0,
                    "date": item.get("date"),
                })
            collect("plan", rows)
        except Exception:
            pass

        # 倒数日
        try:
            rows = []
            for item in (self._countdown.search(q, limit=per_type) if self._countdown else []):
                rows.append({
                    "type": "countdown",
                    "id": item.get("id"),
                    "title": item.get("title") or "",
                    "sub": f"{item.get('date')}{'· 每年' if item.get('repeat') == 'year' else ''}",
                    "ts": item.get("created") or 0,
                })
            collect("countdown", rows)
        except Exception:
            pass

        # 翻译历史与收藏
        try:
            rows = []
            for rec in (api.history.list(limit=400) if api.history else []):
                text = rec.get("text") or ""
                result = rec.get("result") or ""
                if low in text.lower() or low in result.lower():
                    rows.append({
                        "type": "history",
                        "id": rec.get("id"),
                        "title": text.strip()[:70] or result.strip()[:70],
                        "sub": _snippet(result or text, q),
                        "ts": rec.get("ts") or 0,
                        "favorite": bool(rec.get("favorite")),
                    })
            rows.sort(key=lambda r: r["ts"] or 0, reverse=True)
            collect("history", rows)
        except Exception:
            pass

        # 心情日记
        try:
            rows = []
            for item in (self._mood.search(q, limit=per_type) if self._mood else []):
                rows.append({
                    "type": "mood",
                    "id": item.get("date"),
                    "title": item.get("text") or "",
                    "sub": item.get("date") or "",
                    "ts": item.get("at") or 0,
                    "date": item.get("date"),
                })
            collect("mood", rows)
        except Exception:
            pass

        items = [row for _, rows in groups for row in rows]
        return {
            "ok": True,
            "query": q,
            "items": items[: int(limit)],
            "groups": {kind: len(rows) for kind, rows in groups},
        }

    def bootstrap(self):
        api = self._api
        from ptools import aihint, languages, network, notify, translate, units
        from ptools.todo import PRIORITIES, REPEATS, STATUSES

        settings = api.settings.all()
        return {
            "ok": True,
            "app_name": APP_NAME,
            "version": VERSION,
            "settings": settings,
            "languages": languages.catalogue(),
            "providers": [
                {"key": key, "label": translate.PROVIDER_LABELS[key]}
                for key in translate.PROVIDER_ORDER
            ]
            + [
                {"key": aitranslate.TRANSMART, "label": "腾讯交互翻译", "free": True},
                {"key": aitranslate.AI, "label": "AI 接口", "needs_key": True},
            ]
            + [{"key": "auto", "label": "智能选择"}],
            "ai": {
                "ready": aitranslate.ai_ready(settings),
                "base_url": settings.get("ai_base_url") or "",
                "model": settings.get("ai_model") or "",
                "endpoint": aitranslate.normalize_endpoint(settings.get("ai_base_url") or ""),
                "has_key": bool((settings.get("ai_api_key") or "").strip()),
                "presets": aitranslate.PRESETS,
            },
            "history": api.history.list(limit=120),
            "stats": api.history.stats(),
            "notes": api.notes.list() if api.notes else [],
            "note_stats": api.notes.stats() if api.notes else {"total": 0, "pinned": 0, "chars": 0},
            "picker": api.picker.get() if api.picker else {"options": [], "lastResult": "", "history": []},
            "unit_categories": units.catalogue(),
            "currency": api.currency.state() if api.currency else None,
            "last_conversion": api.convert_store.get() if api.convert_store else None,
            "todo_items": api.todo.list("today") if api.todo else [],
            "todo_stats": api.todo.stats() if api.todo else {},
            "todo_meta": {
                "priorities": [{"id": k, "name": n} for k, n in PRIORITIES],
                "repeats": [{"id": k, "name": n} for k, n in REPEATS],
                "statuses": [{"id": k, "name": n} for k, n in STATUSES],
                "ai_ready": aihint.configured(settings),
                "notifications": notify.available(),
            },
            "note_categories": self._note_meta.all() if self._note_meta else {},
            "plan_today": self._plan.get(time.strftime("%Y-%m-%d")) if self._plan else [],
            "focus": self._focus.stats() if self._focus else {},
            "countdowns": self._countdown.all() if self._countdown else [],
            "mood_month": self._mood.month(time.strftime("%Y-%m")) if self._mood else {},
            "mood_stats": self._mood.stats(time.strftime("%Y-%m")) if self._mood else {},
            "chart_last": self._chart.get() if self._chart else None,
            "data_dir": str(data_dir()),
            "exports_dir": str(export_dir_of(self._prefs)),
            "ui_prefs": self._prefs.all() if self._prefs else {},
            "migration": api.startup or {},
            "online": network.online(),
        }


def icon_path():
    roots = [resource_dir() / "assets", Path(__file__).resolve().parent.parent / "assets"]
    for root in roots:
        for name in ("icon.ico", "icon.png"):
            candidate = root / name
            if candidate.exists():
                return str(candidate)
    return None


def claim_taskbar_identity():
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    except Exception:
        pass
    try:
        notify.register_app_id(icon_path())
    except Exception:
        pass


def build_window():
    migration = migrate_legacy_data()
    root = data_dir()

    settings = Settings(root / "settings.json")
    history = History(root / "history.json", settings.get("history_limit", 300))
    notes = Notes(root / "notes.json")
    picker = Picker(root / "random_picker_data.json")
    currency = Currency(root / "currency_rates.json")
    last_conversion = LastRecord(root / "last_conversion.json")
    icon = icon_path()
    todo = Todo(root / "todo_data.json", notifier=notify.toast, icon_path=icon)
    plan = PlanStore(root / "plan_data.json")
    note_meta = NoteMetaStore(root / "note_meta.json")
    focus = FocusStore(root / "focus_log.json")
    countdown = CountdownStore(root / "countdown_data.json")
    mood = MoodStore(root / "mood_diary.json")
    chart = ChartStore(root / "chart_data.json")
    prefs = PrefsStore(root / "ui_prefs.json")

    api = Api(
        settings,
        history,
        notes=notes,
        picker=picker,
        currency=currency,
        convert_store=last_conversion,
        media=None,
        todo=todo,
        startup=migration,
    )
    api.icon = icon
    api.version = VERSION

    if settings.get("reminders_enabled", True):
        todo.start_scheduler()

    index = web_dir() / "index.html"
    if not index.exists():
        raise SystemExit(f"缺少界面文件：{index}")

    exports = root / "exports"
    tray_host = TrayHost(None, prefs)
    ui = UiApi(api, plan, note_meta, focus, countdown, mood, chart, exports, prefs, tray_host=tray_host)
    server = ApiServer(ui, web_dir()).start()

    width = int(settings.get("window_width") or 1240)
    height = int(settings.get("window_height") or 820)
    width = max(width, 1000)
    height = max(height, 660)

    window = webview.create_window(
        APP_NAME,
        server.url,
        width=width,
        height=height,
        min_size=(1000, 660),
        frameless=False,
        easy_drag=False,
        shadow=True,
        on_top=bool(settings.get("always_on_top")),
        background_color="#F3F4F6",
        text_select=True,
    )
    api.window = window
    ui.bind_window(window)
    tray_host.window = window
    window.tray_host = tray_host  # 测试脚本按二元组解包，这里挂到窗口上
    return window, settings


class TrayHost:
    """托盘宿主。

    窗口是最小化还是收进托盘、点关闭是退出还是留下，全部读 prefs，
    前端改完设置立刻生效，不需要重启。
    """

    LABELS = {
        "zh": {
            "show": "打开主窗口",
            "settings": "设置",
            "data": "数据目录",
            "quit": "退出",
            "tip": "{} · 正在后台运行",
            "balloon_title": "{}",
            "balloon_text": "已缩到托盘，双击图标重新打开",
        },
        "en": {
            "show": "Open main window",
            "settings": "Settings",
            "data": "Open data folder",
            "quit": "Quit",
            "tip": "{} · running in background",
            "balloon_title": "{}",
            "balloon_text": "Minimized to tray. Double-click the icon to reopen.",
        },
    }

    def __init__(self, window, prefs):
        self.window = window
        self.prefs = prefs
        self.tray = None
        self.quitting = False
        self.available = False
        self.error = ""
        self._ballooned = False
        self._asked_at = 0.0

    # ------- 偏好 -------

    def pref(self, key, default=False):
        try:
            value = self.prefs.all().get(key) if self.prefs else None
        except Exception:
            value = None
        return default if value is None else bool(value)

    def pref_str(self, key, default=""):
        try:
            value = (self.prefs.all() if self.prefs else {}).get(key)
        except Exception:
            value = None
        if value is None or value == "":
            return default
        return str(value)

    def close_action(self):
        """点 × 该干什么：'tray' / 'quit' / ''（还没选过，需要问一次）。"""
        action = self.pref_str("close_action", "")
        if action in ("tray", "quit"):
            return action
        # 旧版只有 close_to_tray 开关，读过来当成已经选过，免得升级后又问一遍
        if self.pref("close_to_tray", False):
            return "tray"
        return ""

    def lang(self):
        try:
            value = str((self.prefs.all() if self.prefs else {}).get("language") or "zh").lower()
        except Exception:
            value = "zh"
        return "en" if value.startswith("en") else "zh"

    # ------- 窗口动作（可能被托盘线程调用） -------

    def show_window(self):
        def _act():
            try:
                state = getattr(self.window.state, "name", "") or str(self.window.state)
                if "MINIMIZED" in state.upper():
                    self.window.restore()
            except Exception:
                pass
            try:
                self.window.show()
            except Exception:
                pass
            self._ballooned = False

        threading.Thread(target=_act, name="pt-tray-show", daemon=True).start()

    def hide_to_tray(self, balloon=False):
        try:
            self.window.hide()
        except Exception:
            return False
        if balloon and self.tray and not self._ballooned:
            self._ballooned = True
            labels = self.LABELS[self.lang()]
            self.tray.balloon(
                labels["balloon_title"].format(APP_NAME), labels["balloon_text"]
            )
        return True

    def quit(self):
        self.quitting = True
        self.stop()

        def _act():
            try:
                self.window.destroy()
            except Exception:
                os._exit(0)

        threading.Thread(target=_act, name="pt-tray-quit", daemon=True).start()

    # ------- 托盘 -------

    def _menu(self):
        labels = self.LABELS[self.lang()]
        return [
            ("show", labels["show"]),
            ("settings", labels["settings"]),
            ("data", labels["data"]),
            (None, ""),
            ("quit", labels["quit"]),
        ]

    def start(self):
        if not sys.platform.startswith("win"):
            return False
        if not self.pref("tray_enabled", True):
            return False
        try:
            self.tray = Tray(APP_NAME, icon_path() or "", self._menu(), self.on_command, self.show_window)
            self.available = bool(self.tray.start())
            if self.available:
                self.refresh_label()
            else:
                self.error = "托盘图标注册失败"
            return self.available
        except Exception as exc:  # noqa: BLE001
            self.available = False
            self.error = f"{type(exc).__name__}: {exc}"
            return False

    def stop(self):
        if self.tray:
            try:
                self.tray.stop()
            except Exception:
                pass
            self.tray = None
        self.available = False

    def refresh_label(self):
        """语言变了就换菜单文案与提示。菜单是每次右键临时建的，改列表即可。"""
        if not self.tray:
            return
        self.tray.menu = self._menu()
        self.tray.title = self.LABELS[self.lang()]["tip"].format(APP_NAME)

    def on_command(self, cmd):
        if cmd == "show":
            self.show_window()
        elif cmd == "settings":
            self.show_window()
            try:
                self.window.evaluate_js("location.hash = '#/settings'")
            except Exception:
                pass
        elif cmd == "data":
            try:
                os.startfile(str(data_dir()))
            except Exception:
                pass
        elif cmd == "quit":
            self.quit()

    # ------- 窗口事件 -------

    def on_minimized(self):
        if self.pref("minimize_to_tray", True) and self.available:
            self.hide_to_tray(balloon=True)

    def on_closing(self):
        if self.quitting:
            return True
        if not self.available:
            return True

        action = self.close_action()
        if action == "quit":
            return True
        if action == "tray":
            self.hide_later(balloon=True)
            return False  # 取消关闭

        # 还没选过：取消关闭，弹一次二选一。选完写进 prefs，以后不再问。
        threading.Thread(target=self.ask_close_action, name="pt-tray-ask", daemon=True).start()
        return False

    def hide_later(self, balloon=True):
        """closing 是阻塞事件、回调跑在 WinForms 的 UI 线程上。

        在回调里直接 hide() 会去 Invoke 同一个线程，把消息泵卡住
        （窗口藏了但界面不再响应）。所以返回后另起线程收窗口。
        """

        def later():
            time.sleep(0.05)
            self.hide_to_tray(balloon=balloon)

        threading.Thread(target=later, name="pt-tray-hide", daemon=True).start()

    def ask_close_action(self):
        """让前端弹「收进托盘 / 直接退出」的框。

        不设常驻标志位：用户按 Esc 取消后还得能再问，
        所以只按时间挡住 1.2 秒内的重复触发（狂点 × 不会叠出多个弹窗）。
        """
        now = time.time()
        if now - self._asked_at < 1.2:
            return
        self._asked_at = now
        try:
            time.sleep(0.06)
            self.window.evaluate_js("window.PTAskClose && window.PTAskClose()")
        except Exception:
            # 前端没接住（界面已经挂了），按最保守的方式留在托盘
            self.hide_later(balloon=True)


def attach_tray(window):
    """启动托盘并把窗口事件挂上。main() 与自测脚本共用这一段。"""
    host = getattr(window, "tray_host", None)
    if not host:
        return None
    try:
        host.start()
    except Exception as exc:  # noqa: BLE001
        host.error = f"start: {type(exc).__name__}: {exc}"
    try:
        window.events.minimized += host.on_minimized
        window.events.closing += host.on_closing
    except Exception as exc:  # noqa: BLE001
        host.error += f" | events: {type(exc).__name__}: {exc}"
    return host


def main():
    claim_taskbar_identity()
    try:
        window, settings = build_window()
        strip_legacy_settings()
    except SystemExit:
        raise
    except Exception:
        try:
            (data_dir() / "startup-error.log").write_text(traceback.format_exc(), encoding="utf-8")
        except Exception:
            pass
        raise

    tray_host = getattr(window, 'tray_host', None)

    def after_start():
        attach_tray(window)

    webview.start(
        func=after_start,
        gui="edgechromium",
        debug=os.environ.get("PT_DEBUG") == "1",
        private_mode=False,
        storage_path=str(data_dir() / "webview"),
        icon=icon_path(),
    )

    if tray_host:
        tray_host.stop()

    try:
        if window and not window.maximized:
            settings.update({"window_width": int(window.width), "window_height": int(window.height)})
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
