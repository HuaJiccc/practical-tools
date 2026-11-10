"""记事本：所有笔记存在一个 JSON 文件里。

笔记从不按条数裁剪 —— 翻译历史丢了只是不方便，笔记丢了是数据丢失。
置顶的排前面，其余按最近修改排。
"""

import json
import threading
import time
import uuid
from pathlib import Path

from .config import write_text

MAX_TITLE = 60
UNTITLED = "无标题"


def derive_title(content):
    """标题取第一段有内容的文字，省得每条笔记还要手动起名。"""
    for line in str(content or "").splitlines():
        text = line.strip().strip("#").strip()
        if not text:
            continue
        if len(text) > MAX_TITLE:
            return text[:MAX_TITLE] + "…"
        return text
    return UNTITLED


def _note_id():
    return uuid.uuid4().hex[:12]


class Notes:
    def __init__(self, path):
        self._path = Path(path)
        self._lock = threading.RLock()
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
                    created = float(item.get("ts") or 0)
                    items.append({
                        "id": str(item.get("id")),
                        "title": str(item.get("title") or UNTITLED),
                        "content": str(item.get("content") or ""),
                        "pinned": bool(item.get("pinned")),
                        "ts": created,
                        "updated": float(item.get("updated") or created),
                    })
            self._items = items

    def _save_locked(self):
        # 落盘顺序也是置顶在前、新的在前，文件直接看就是界面上的顺序
        self._items.sort(key=self._sort_key, reverse=True)
        write_text(self._path, json.dumps(self._items, ensure_ascii=False, indent=1))

    @staticmethod
    def _sort_key(note):
        return (1 if note["pinned"] else 0, note["updated"])

    # ------- 对外 -------

    def list(self, query=""):
        needle = str(query or "").strip().lower()
        with self._lock:
            items = [dict(item) for item in self._items]
        if needle:
            items = [
                item for item in items
                if needle in item["title"].lower() or needle in item["content"].lower()
            ]
        items.sort(key=self._sort_key, reverse=True)
        return items

    def get(self, note_id):
        with self._lock:
            for item in self._items:
                if item["id"] == note_id:
                    return dict(item)
        return None

    def create(self, content="", title=None):
        body = str(content or "")
        now = time.time()
        note = {
            "id": _note_id(),
            "title": str(title).strip() if title else derive_title(body),
            "content": body,
            "pinned": False,
            "ts": now,
            "updated": now,
        }
        if not note["title"]:
            note["title"] = UNTITLED
        with self._lock:
            self._items.insert(0, note)
            self._save_locked()
            return dict(note)

    def update(self, note_id, content=None, pinned=None, title=None):
        with self._lock:
            for item in self._items:
                if item["id"] != note_id:
                    continue
                if content is not None:
                    item["content"] = str(content)
                    # 标题跟着内容第一行走；只有同时改了内容，显式标题才生效
                    item["title"] = str(title).strip() if title else derive_title(item["content"])
                else:
                    item["title"] = derive_title(item["content"])
                if pinned is not None:
                    item["pinned"] = bool(pinned)
                if not item["title"]:
                    item["title"] = UNTITLED
                item["updated"] = time.time()
                self._save_locked()
                return dict(item)
        return None

    def toggle_pin(self, note_id):
        with self._lock:
            for item in self._items:
                if item["id"] == note_id:
                    item["pinned"] = not item["pinned"]
                    self._save_locked()
                    return dict(item)
        return None

    def delete(self, note_id):
        with self._lock:
            keep = [item for item in self._items if item["id"] != note_id]
            if len(keep) == len(self._items):
                return False
            self._items = keep
            self._save_locked()
            return True

    def stats(self):
        with self._lock:
            return {
                "total": len(self._items),
                "pinned": sum(1 for item in self._items if item["pinned"]),
                "chars": sum(len(item["content"]) for item in self._items),
            }
