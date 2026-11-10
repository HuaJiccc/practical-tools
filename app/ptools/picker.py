"""随机选择：选项、上次结果、最近几次抽签记录，全在一个 JSON 文件里。

完全本地，不联网。抽签本身在前端做（动画要跟着跑），
这里只负责把状态存住，以及记住抽出来的结果。
"""

import json
import threading
import time
from pathlib import Path

from .config import write_text

MIN_OPTIONS = 2
MAX_OPTIONS = 20
MAX_OPTION_LEN = 200
HISTORY_LIMIT = 60


def _clean_option(value):
    text = str(value or "").strip()
    if not text:
        return ""
    return text[:MAX_OPTION_LEN]


def normalize(payload):
    """把前端传来的任何东西整成一个合法的状态文档。"""
    data = payload if isinstance(payload, dict) else {}

    options = []
    for raw in data.get("options") or []:
        text = _clean_option(raw)
        if text and text not in options:
            options.append(text)
        if len(options) >= MAX_OPTIONS:
            break

    history = []
    for raw in data.get("history") or []:
        if not isinstance(raw, dict):
            continue
        value = _clean_option(raw.get("value"))
        if not value:
            continue
        try:
            at = float(raw.get("at") or 0)
        except (TypeError, ValueError):
            at = 0.0
        history.append({"value": value, "at": at})
        if len(history) >= HISTORY_LIMIT:
            break

    return {
        "options": options,
        "lastResult": _clean_option(data.get("lastResult")),
        "history": history,
        "updatedAt": float(data.get("updatedAt") or time.time()),
    }


class Picker:
    def __init__(self, path):
        self._path = Path(path)
        self._lock = threading.RLock()
        self._state = normalize({})
        self._load()

    def _load(self):
        with self._lock:
            try:
                raw = json.loads(self._path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                raw = {}
            self._state = normalize(raw if isinstance(raw, dict) else {})

    def _save_locked(self):
        self._state["updatedAt"] = time.time()
        write_text(self._path, json.dumps(self._state, ensure_ascii=False, indent=1))

    def get(self):
        with self._lock:
            return json.loads(json.dumps(self._state, ensure_ascii=False))

    def save(self, payload):
        """整份替换：前端每次提交的都是完整状态，不做局部合并。"""
        with self._lock:
            self._state = normalize(payload if isinstance(payload, dict) else {})
            self._save_locked()
            return json.loads(json.dumps(self._state, ensure_ascii=False))

    def record(self, value):
        """记一次抽签结果（最新的在前）。"""
        text = _clean_option(value)
        with self._lock:
            if text:
                self._state["lastResult"] = text
                self._state["history"].insert(0, {"value": text, "at": time.time()})
                del self._state["history"][HISTORY_LIMIT:]
            self._save_locked()
            return json.loads(json.dumps(self._state, ensure_ascii=False))

    def clear_history(self):
        with self._lock:
            # 只清抽签记录，上次结果留着 —— 界面上那行字还有用
            self._state["history"] = []
            self._save_locked()
            return json.loads(json.dumps(self._state, ensure_ascii=False))

    def stats(self):
        with self._lock:
            return {
                "options": len(self._state["options"]),
                "history": len(self._state["history"]),
                "lastResult": self._state["lastResult"],
            }
