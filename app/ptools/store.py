"""两个 JSON 小仓库：翻译历史，和"上次换算"那一行。

历史会按上限裁剪（默认 300 条，下限 20 条）；收藏的记录不会被裁掉。
数据文件是 JSON 数组，字段固定，换版本时老文件照样能读。
"""

import json
import threading
import time
import uuid
from pathlib import Path

from .config import write_text

DEFAULT_LIMIT = 300
MIN_LIMIT = 20


def _entry_id():
    return uuid.uuid4().hex[:12]


class LastRecord:
    """就一个 dict 存盘 —— 够放"上次换算"这种一行数据。"""

    def __init__(self, path):
        self._path = Path(path)
        self._lock = threading.RLock()

    def get(self):
        with self._lock:
            try:
                data = json.loads(self._path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                return None
            return data if isinstance(data, dict) and data else None

    def save(self, payload):
        with self._lock:
            data = payload if isinstance(payload, dict) else {}
            write_text(self._path, json.dumps(data, ensure_ascii=False, indent=1))
            return data

    def clear(self):
        with self._lock:
            try:
                self._path.unlink()
            except OSError:
                pass
            return None


class History:
    """翻译历史：新记录在前，按上限裁剪，收藏的不裁。"""

    def __init__(self, path, limit=DEFAULT_LIMIT):
        self._path = Path(path)
        self._lock = threading.RLock()
        self._limit = max(MIN_LIMIT, int(limit or DEFAULT_LIMIT))
        self._items = []
        self._load()

    # ------- 内部 -------

    def _load(self):
        with self._lock:
            try:
                raw = json.loads(self._path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                raw = []
            items = []
            if isinstance(raw, list):
                for item in raw:
                    if not isinstance(item, dict) or not item.get("id"):
                        continue
                    items.append({
                        "id": str(item.get("id")),
                        "text": str(item.get("text") or ""),
                        "result": str(item.get("result") or ""),
                        "source": str(item.get("source") or "auto"),
                        "target": str(item.get("target") or ""),
                        "provider": str(item.get("provider") or ""),
                        "provider_label": str(item.get("provider_label") or ""),
                        "translit": item.get("translit") or None,
                        "favorite": bool(item.get("favorite")),
                        "ts": float(item.get("ts") or 0),
                    })
            self._items = items

    def _save_locked(self):
        write_text(self._path, json.dumps(self._items, ensure_ascii=False, indent=1))

    def set_limit(self, limit):
        try:
            value = int(limit)
        except (TypeError, ValueError):
            value = DEFAULT_LIMIT
        with self._lock:
            self._limit = max(MIN_LIMIT, value)
            self._trim_locked()
            return self._limit

    def _trim_locked(self):
        """超出上限就从最旧的开始扔；收藏的记录跳过，但最多留一小撮。"""
        if len(self._items) <= self._limit:
            return
        keep = []
        dropped = 0
        # 从后往前保留到上限；收藏项即使超限也优先留下
        for item in self._items:
            if len(keep) < self._limit or item["favorite"]:
                keep.append(item)
            else:
                dropped += 1
        if dropped:
            self._items = keep
            self._save_locked()

    # ------- 对外 -------

    def add(self, text, result, source, target, provider, provider_label,
            translit=None, favorite=False):
        entry = {
            "id": _entry_id(),
            "text": str(text or ""),
            "result": str(result or ""),
            "source": str(source or "auto"),
            "target": str(target or ""),
            "provider": str(provider or ""),
            "provider_label": str(provider_label or ""),
            "translit": translit or None,
            "favorite": bool(favorite),
            "ts": time.time(),
        }
        with self._lock:
            self._items.insert(0, entry)
            self._trim_locked()
            self._save_locked()
            return dict(entry)

    def list(self, query="", only_favorites=False, limit=200):
        needle = str(query or "").strip().lower()
        try:
            cap = max(1, int(limit))
        except (TypeError, ValueError):
            cap = 200
        out = []
        with self._lock:
            for item in self._items:
                if only_favorites and not item["favorite"]:
                    continue
                if needle and needle not in item["text"].lower() and needle not in item["result"].lower():
                    continue
                out.append(dict(item))
                if len(out) >= cap:
                    break
        return out

    def toggle_favorite(self, entry_id):
        with self._lock:
            for item in self._items:
                if item["id"] == entry_id:
                    item["favorite"] = not item["favorite"]
                    self._save_locked()
                    return dict(item)
        return None

    def delete(self, entry_id):
        with self._lock:
            keep = [item for item in self._items if item["id"] != entry_id]
            if len(keep) == len(self._items):
                return False
            self._items = keep
            self._save_locked()
            return True

    def clear(self, keep_favorites=True):
        with self._lock:
            if keep_favorites:
                self._items = [item for item in self._items if item["favorite"]]
            else:
                self._items = []
            self._save_locked()
            return len(self._items)

    def stats(self):
        with self._lock:
            return {
                "total": len(self._items),
                "favorites": sum(1 for item in self._items if item["favorite"]),
            }
