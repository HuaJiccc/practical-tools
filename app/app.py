"""个人工具 2.0 —— 桌面外壳。

界面是纯本地 HTML/CSS/JS，通过本机回环 HTTP 服务和 Python 后端通信。
本版本移除了「影视书籍」模块，并重做了整套界面（无玻璃/模糊材质）。
"""

import base64
import ctypes
import json
import os
import re
import sys
import time
import traceback
from pathlib import Path

BASE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import webview  # noqa: E402

from ptools import APP_NAME, notify  # noqa: E402
from ptools.api import Api  # noqa: E402
from ptools.config import (  # noqa: E402
    Settings,
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

VERSION = "2.5.0"
APP_ID = "PersonalToolkit.DesktopApp"

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

    def __init__(self, api, plan=None, note_meta=None, focus=None, countdown=None, mood=None, chart=None, exports=None, prefs=None):
        object.__setattr__(self, "_api", api)
        object.__setattr__(self, "_plan", plan)
        object.__setattr__(self, "_note_meta", note_meta)
        object.__setattr__(self, "_focus", focus)
        object.__setattr__(self, "_countdown", countdown)
        object.__setattr__(self, "_mood", mood)
        object.__setattr__(self, "_chart", chart)
        object.__setattr__(self, "_exports", exports)
        object.__setattr__(self, "_prefs", prefs)

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
        """把前端生成的图片/GIF 落盘到 data/exports，文件名去危险字符、重名自动加序号。"""
        if not self._exports or not data_b64:
            return {"ok": False, "error": "没有可写入的位置"}
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
        target_dir = Path(self._exports)
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
        """打开导出目录（保存后想马上看看结果）。"""
        if not self._exports:
            return {"ok": False}
        path = Path(self._exports)
        path.mkdir(parents=True, exist_ok=True)
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
        return {"ok": True, "prefs": self._prefs.update(patch)}

    # ---- v2.5：通用 / 数据 / 关于 设置项 ----
    def sys_autostart(self, enabled=None):
        """读写开机自启（HKCU\\...\\Run，不需要管理员，不弹黑窗）。"""
        name = "个人工具"
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
                    return {"ok": True, "enabled": False, "command": command}
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
        exports = root / "exports"
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
            edge = "未读取到"
        items = [
            ["版本", VERSION],
            ["系统", f"{platform.system()} {platform.release()} ({platform.version()})"],
            ["Python", f"{platform.python_version()} {platform.machine()}"],
            ["WebView2", edge],
            ["运行方式", "打包版" if getattr(sys, "frozen", False) else "源码"],
            ["数据目录", str(root)],
            ["数据占用", f"{total / 1048576:.2f} MB"],
            ["翻译通道", settings.get("provider") or "auto"],
            ["AI 接口", ("已配置 " + (settings.get("ai_model") or "")).strip() if (settings.get("ai_api_key") or "").strip() else "未配置"],
            ["待办提醒", "开" if settings.get("reminders_enabled", True) else "关"],
        ]
        text = "\n".join(f"{name}：{value}" for name, value in items)
        return {"ok": True, "items": items, "text": text}


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
        from ptools import APP_NAME, aihint, languages, network, notify, translate, units
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
            "exports_dir": str(data_dir() / "exports"),
            "ui_prefs": self._prefs.all() if self._prefs else {},
            "migration": api.startup or {},
            "online": network.online(),
        }


def icon_path():
    for name in ("icon.ico", "icon.png"):
        candidate = resource_dir() / "assets" / name
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
    server = ApiServer(
        UiApi(api, plan, note_meta, focus, countdown, mood, chart, exports, prefs), web_dir()
    ).start()

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
    return window, settings


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

    webview.start(
        gui="edgechromium",
        debug=os.environ.get("PT_DEBUG") == "1",
        private_mode=False,
        storage_path=str(data_dir() / "webview"),
        icon=icon_path(),
    )

    try:
        if window and not window.maximized:
            settings.update({"window_width": int(window.width), "window_height": int(window.height)})
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
