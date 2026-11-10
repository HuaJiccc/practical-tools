"""界面与 Python 之间的那层门面。

网页只会说 ``POST /api/<方法名>``，参数是一个列表，这里的每个方法就是对
应的处理函数。约定：成功回 ``{"ok": True, ...}``，失败回 ``{"ok": False,
"error": "给人看的一句话"}``，界面不用再判断别的。
"""

import ctypes
import functools
import os

from . import aihint, clipboard, languages, network, nlptime, notify, units
from . import media as media_module
from . import metadata
from . import todo as todo_module
from .config import APP_ID, data_dir, write_text
from .currency import Currency
from .picker import MAX_OPTION_LEN, MAX_OPTIONS, MIN_OPTIONS, Picker
from .todo import Todo
from .translate import (PROVIDER_LABELS, PROVIDER_ORDER, TTS_VOICE, Engine,
                        TranslateError, tts_url)

APP_NAME = "个人工具"
VERSION = "1.0.0"

SW_MAXIMIZE = 3
SW_RESTORE = 9

NO_MEDIA = "影视书籍模块未初始化"
PROBE_SAMPLE = "你好"


def _guard(func):
    """别让一个异常把整个界面带崩，转成一条能看懂的错误。"""
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        try:
            return func(self, *args, **kwargs)
        except Exception as exc:
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    return wrapper


def _fail(message):
    return {"ok": False, "error": str(message)}


class Api:
    def __init__(self, settings, history, notes=None, picker=None, currency=None,
                 convert_store=None, media=None, todo=None, startup=None, covers=None):
        self.settings = settings
        self.history = history
        self.notes = notes
        self.picker = picker
        self.currency = currency or Currency(data_dir() / "currency_rates.json")
        self.convert_store = convert_store
        self.media = media
        self.todo = todo
        self.covers = covers
        self.startup = startup
        self.engine = None      # 第一次翻译时再建，省得启动就 import
        self.window = None
        self.icon = None
        self.version = VERSION

    # ---------------- 启动 ----------------

    @_guard
    def ping(self):
        return {"ok": True, "ts": __import__("time").time()}

    @_guard
    def bootstrap(self):
        """首屏要的全部东西，一次给完。"""
        settings = self.settings.all() if self.settings else {}
        history = self.history.list() if self.history else []
        hist_stats = self.history.stats() if self.history else {"total": 0, "favorites": 0}
        note_items = self.notes.list() if self.notes else []
        note_stats = self.notes.stats() if self.notes else {"total": 0, "pinned": 0, "chars": 0}
        return {
            "ok": True,
            "app": {"name": APP_NAME, "version": VERSION},
            "settings": settings,
            "languages": languages.catalogue(),
            "providers": [{"id": key, "label": PROVIDER_LABELS.get(key, key)}
                          for key in PROVIDER_ORDER],
            "history": {"items": history[:20], "stats": hist_stats},
            "notes": {"items": note_items[:20], "stats": note_stats},
            "picker": self.picker.get() if self.picker else None,
            "units": units.catalogue(),
            "currency": self.currency.state() if self.currency else None,
            "conversion": self.convert_store.get() if self.convert_store else None,
            "media": {"ready": False, "types": [], "groups": [], "statuses": [],
                      "platforms": [], "reason": NO_MEDIA},
            "todo": {
                "priorities": [{"id": k, "name": n} for k, n in todo_module.PRIORITIES],
                "repeats": [{"id": k, "name": n} for k, n in todo_module.REPEATS],
                "statuses": [{"id": k, "name": n} for k, n in todo_module.STATUSES],
            },
            "ai": {"ready": aihint.configured(settings)},
            "notify": {"available": notify.available()},
            "data_dir": str(data_dir()),
            "startup": self.startup or {},
            "online": network.online(),
        }

    @_guard
    def net_state(self, force=False):
        state = network.snapshot()
        return {"ok": True, "online": bool(state.get("online")),
                "hint": network.OFFLINE_HINT}

    @_guard
    def probe(self):
        """挨个通道发一句"你好"看看通不通，设置页拿来显示信号灯。"""
        import time
        if self.engine is None:
            self.engine = Engine(self.settings)
        results = []
        for key in PROVIDER_ORDER:
            row = {"key": key, "label": PROVIDER_LABELS.get(key, key)}
            started = time.time()
            try:
                out = self.engine.translate(PROBE_SAMPLE, "zh-Hans", "en", provider=key)
                row.update({"ok": True, "sample": out.get("text") or ""})
            except TranslateError as exc:
                row.update({"ok": False, "error": str(exc)})
            except Exception as exc:
                row.update({"ok": False, "error": f"{type(exc).__name__}: {exc}"})
            row["latency_ms"] = int((time.time() - started) * 1000)
            results.append(row)
        return {"ok": True, "results": results}

    # ---------------- 设置 ----------------

    @_guard
    def save_settings(self, patch):
        values = self.settings.update(patch if isinstance(patch, dict) else {})
        return {"ok": True, "settings": values}

    @_guard
    def reset_settings(self):
        return {"ok": True, "settings": self.settings.reset()}

    @_guard
    def open_data_dir(self):
        target = data_dir()
        target.mkdir(parents=True, exist_ok=True)
        os.startfile(str(target))       # noqa: S606 - Windows 上就这一种打开方式
        return {"ok": True}

    @_guard
    def open_url(self, url):
        text = str(url or "").strip()
        if not text.startswith(("http://", "https://")):
            return _fail("只允许打开 http/https 链接")
        os.startfile(text)              # noqa: S606
        return {"ok": True}

    @_guard
    def window_control(self, action):
        """最小化 / 最大化 / 还原，交给 Win32。"""
        if self.window is None:
            return _fail("窗口还没准备好")
        handle = ctypes.windll.user32.FindWindowW(None, APP_NAME)
        if not handle:
            return _fail("找不到窗口句柄")
        choice = str(action or "").lower()
        if choice in ("minimize", "min"):
            ctypes.windll.user32.ShowWindow(handle, 6)
        elif choice in ("maximize", "max"):
            ctypes.windll.user32.ShowWindow(handle, SW_MAXIMIZE)
        elif choice in ("restore", "normal"):
            ctypes.windll.user32.ShowWindow(handle, SW_RESTORE)
        elif choice in ("hide", "close"):
            ctypes.windll.user32.ShowWindow(handle, 0)
        else:
            return _fail(f"不认识的操作：{action}")
        return {"ok": True}

    # ---------------- 剪贴板 ----------------

    @_guard
    def clipboard_read(self):
        return {"ok": True, "text": clipboard.read_text()}

    @_guard
    def clipboard_write(self, text):
        ok = clipboard.write_text(str(text or ""))
        return {"ok": bool(ok), "error": None if ok else "写入剪贴板失败"}

    # ---------------- 翻译 ----------------

    @_guard
    def detect_language(self, text):
        return {"ok": True, "lang": languages.detect(text)}

    @_guard
    def translate(self, text, source="auto", target="zh-Hans", provider=None, remember=True):
        import time
        raw = str(text or "")
        if not raw.strip():
            return _fail("没有要翻译的内容")
        if self.engine is None:
            self.engine = Engine(self.settings)
        started = time.time()
        try:
            result = self.engine.translate(raw, source, target, provider or "auto")
        except TranslateError as exc:
            return _fail(str(exc))
        elapsed = int((time.time() - started) * 1000)

        src = result.get("source") or source
        dst = result.get("target") or target
        detected = result.get("detected") or ""
        entry = None
        stats = self.history.stats() if self.history else {"total": 0, "favorites": 0}
        if remember and self.history and not result.get("skipped"):
            entry = self.history.add(raw, result.get("text") or "", source=src, target=dst,
                                     provider=result.get("provider") or "",
                                     provider_label=PROVIDER_LABELS.get(result.get("provider"), ""),
                                     translit=None, favorite=False)
            stats = self.history.stats()
        return {
            "ok": True,
            "text": result.get("text") or "",
            "translit": "",
            "tts": self._tts(result.get("text") or "", dst),
            "source": src,
            "target": dst,
            "detected": detected,
            "detected_name": languages.name_of(detected),
            "same_language": bool(result.get("skipped")),
            "provider": result.get("provider") or "",
            "provider_label": PROVIDER_LABELS.get(result.get("provider"), ""),
            "elapsed_ms": elapsed,
            "attempts": [],
            "entry": entry,
            "stats": stats,
        }

    def _tts(self, text, lang):
        if not text:
            return ""
        try:
            return tts_url(text, lang)
        except Exception:
            return ""

    @_guard
    def speak(self, text, lang="en"):
        voice = TTS_VOICE.get(str(lang or ""), "en")
        return {"ok": True, "url": tts_url(text, voice)}

    # ---------------- 历史 ----------------

    @_guard
    def history_list(self, query="", only_favorites=False, limit=200):
        return {"ok": True,
                "items": self.history.list(query=query, only_favorites=only_favorites,
                                           limit=limit),
                "stats": self.history.stats()}

    @_guard
    def history_delete(self, entry_id):
        removed = self.history.delete(entry_id)
        return {"ok": True, "deleted": bool(removed), "stats": self.history.stats()}

    @_guard
    def history_clear(self, keep_favorites=True):
        remaining = self.history.clear(keep_favorites=keep_favorites)
        return {"ok": True, "remaining": int(remaining), "stats": self.history.stats()}

    @_guard
    def history_toggle(self, entry_id):
        item = self.history.toggle_favorite(entry_id)
        if item is None:
            return _fail("记录不存在")
        return {"ok": True, "item": item, "stats": self.history.stats()}

    # ---------------- 笔记 ----------------

    @_guard
    def notes_list(self, query=""):
        return {"ok": True, "items": self.notes.list(query=query), "stats": self.notes.stats()}

    @_guard
    def notes_create(self, content="", title=None):
        item = self.notes.create(content=content, title=title)
        return {"ok": True, "item": item, "stats": self.notes.stats()}

    @_guard
    def notes_update(self, note_id, content):
        item = self.notes.update(note_id, content=content)
        if item is None:
            return _fail("笔记不存在")
        return {"ok": True, "item": item, "stats": self.notes.stats()}

    @_guard
    def notes_delete(self, note_id):
        removed = self.notes.delete(note_id)
        return {"ok": True, "deleted": bool(removed), "stats": self.notes.stats()}

    @_guard
    def notes_pin(self, note_id):
        item = self.notes.toggle_pin(note_id)
        if item is None:
            return _fail("笔记不存在")
        return {"ok": True, "item": item, "stats": self.notes.stats()}

    # ---------------- 随机选择 ----------------

    @_guard
    def picker_load(self):
        return {"ok": True, "state": self.picker.get(),
                "limits": {"min": MIN_OPTIONS, "max": MAX_OPTIONS,
                           "max_length": MAX_OPTION_LEN}}

    @_guard
    def picker_save(self, payload):
        return {"ok": True, "state": self.picker.save(payload)}

    @_guard
    def picker_clear_history(self):
        return {"ok": True, "state": self.picker.clear_history()}

    @_guard
    def picker_record(self, value):
        return {"ok": True, "state": self.picker.record(value)}

    # ---------------- 汇率 ----------------

    @_guard
    def currency_ensure(self):
        return self.currency.ensure_fresh()

    @_guard
    def currency_refresh(self):
        return self.currency.refresh(force=True)

    @_guard
    def save_conversion(self, record):
        if not self.convert_store:
            return _fail("还没有记录位置")
        return {"ok": True, "record": self.convert_store.save(record or {})}

    # ---------------- 待办 ----------------

    def _stats(self):
        return self.todo.stats()

    @_guard
    def todo_list(self, view="today", tag=None, priority=None, query=""):
        return {"ok": True, "items": self.todo.list(view, tag, priority, query),
                "stats": self.todo.stats()}

    @_guard
    def todo_create(self, payload):
        return {"ok": True, "item": self.todo.create(payload), "stats": self._stats()}

    @_guard
    def todo_parse(self, text):
        """先按本地规则拆；一个字都没认出来才问 AI。"""
        draft = nlptime.parse(text)
        ai_used = False
        ai_error = None
        if not draft.get("title") and not draft.get("matched_time"):
            if aihint.configured(self.settings.all()):
                try:
                    draft = aihint.parse(text, self.settings.all())
                    ai_used = True
                except aihint.AIError as exc:
                    ai_error = str(exc)
        draft["ai_used"] = ai_used
        draft["ai_error"] = ai_error
        return {"ok": True, "draft": draft}

    @_guard
    def todo_update(self, item_id, payload):
        item = self.todo.update(item_id, payload)
        if item is None:
            return _fail("任务不存在")
        return {"ok": True, "item": item, "stats": self._stats()}

    @_guard
    def todo_complete(self, item_id):
        item, follow = self.todo.complete(item_id)
        if item is None:
            return _fail("任务不存在")
        return {"ok": True, "item": item, "follow_up": follow, "stats": self._stats()}

    @_guard
    def todo_reopen(self, item_id):
        item = self.todo.reopen(item_id)
        if item is None:
            return _fail("任务不存在")
        return {"ok": True, "item": item, "stats": self._stats()}

    @_guard
    def todo_postpone(self, item_id, days=1, minutes=0):
        item = self.todo.postpone(item_id, days, minutes)
        if item is None:
            return _fail("任务不存在")
        return {"ok": True, "item": item, "stats": self._stats()}

    @_guard
    def todo_delete(self, item_id):
        removed = self.todo.delete(item_id)
        return {"ok": True, "deleted": bool(removed), "stats": self._stats()}

    @_guard
    def todo_delete_many(self, ids):
        return {"ok": True, "removed": self.todo.delete_many(ids), "stats": self._stats()}

    @_guard
    def todo_clear_done(self):
        return {"ok": True, "removed": self.todo.clear_done(), "stats": self._stats()}

    @_guard
    def todo_test_notification(self):
        ok = notify.toast("提醒测试", "看到这条说明系统通知是通的", self.icon)
        return {"ok": bool(ok), "error": None if ok else "通知没有弹出来"}

    # ---------------- 影视书籍（已下线，保留接口不让老页面报错） ----------------

    def _no_media(self, *_args, **_kwargs):
        return _fail(NO_MEDIA)

    @_guard
    def media_ready(self):
        return False

    media_list = _no_media
    media_get = _no_media
    media_create = _no_media
    media_update = _no_media
    media_delete = _no_media
    media_clear = _no_media
    media_stats = _no_media
    media_search = _no_media
    media_guess = _no_media
    media_refresh = _no_media
    media_cover_one = _no_media
    media_cover_start = _no_media
    media_cover_stop = _no_media
    media_cover_status = _no_media
    media_fetch_details = _no_media
    media_import = _no_media
    media_export = _no_media
    media_add_record = _no_media
    media_update_record = _no_media
    media_delete_record = _no_media
    media_xlsx_preview = _no_media
    media_xlsx_import = _no_media
