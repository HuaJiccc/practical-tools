"""待办清单：存储、筛选、重复任务、到点提醒。

一条待办长得像这样（字段顺序就是落盘的顺序）::

    {"title", "notes", "due_at", "remind_at", "repeat_rule", "priority",
     "tags", "status", "completed_at", "postponed_count",
     "remind_fired_at", "id", "created_at"}

时间一律用本地时间的 ``YYYY-MM-DDTHH:MM``，比较也按本地时间算。
``is_today`` / ``is_overdue`` 是查出来时临时算的，不落盘。
"""

import json
import threading
import time
import uuid
from datetime import datetime, timedelta

from .config import write_text
from .nlptime import next_occurrence

CHECK_INTERVAL = 30     # 提醒线程多久看一次表
LATE_GRACE = 300        # 迟到这个秒数内还补发，再晚就算了，免得一开电脑弹一屏

PRIORITIES = [("low", "低"), ("medium", "中"), ("high", "高")]
PRIORITY_IDS = [key for key, _name in PRIORITIES]
PRIORITY_NAMES = dict(PRIORITIES)

REPEATS = [("none", "不重复"), ("daily", "每天"), ("weekly", "每周"),
           ("monthly", "每月"), ("yearly", "每年")]
REPEAT_IDS = [key for key, _name in REPEATS]
REPEAT_NAMES = dict(REPEATS)

STATUSES = [("todo", "待办"), ("done", "已完成"), ("cancelled", "已取消")]
STATUS_IDS = [key for key, _name in STATUSES]
STATUS_NAMES = dict(STATUSES)

UNTITLED = "未命名任务"
PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2}
FIELDS = ("title", "notes", "due_at", "remind_at", "repeat_rule", "priority",
          "tags", "status", "completed_at", "postponed_count",
          "remind_fired_at", "id", "created_at")


def _now():
    return datetime.now()


def _normalize_time(value):
    """把各种写法的时间收拾成 ``YYYY-MM-DDTHH:MM``，认不出来就是 None。"""
    if not value:
        return None
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%dT%H:%M")
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text).strftime("%Y-%m-%dT%H:%M")
    except ValueError:
        pass
    for pattern in ("%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(text, pattern).strftime("%Y-%m-%dT%H:%M")
        except ValueError:
            continue
    return None


def _as_datetime(value):
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _day_of(value):
    moment = _as_datetime(value)
    return moment.date() if moment else None


def _normalize_tags(value):
    """标签可以给字符串、列表或者什么都不给。不去重，用户写两次就存两次。"""
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip().lstrip("#")
        return [text] if text else []
    if isinstance(value, (list, tuple, set)):
        tags = []
        for item in value:
            text = str(item or "").strip().lstrip("#")
            if text:
                tags.append(text)
        return tags
    text = str(value).strip().lstrip("#")
    return [text] if text else []


def _clean_item(raw):
    """读盘时把缺的字段补齐，坏数据挡在外面。"""
    if not isinstance(raw, dict):
        return None
    title = str(raw.get("title") or "").strip() or UNTITLED
    priority = raw.get("priority")
    repeat = raw.get("repeat_rule")
    status = raw.get("status")
    try:
        created = float(raw.get("created_at") or 0)
    except (TypeError, ValueError):
        created = 0.0
    try:
        postponed = int(raw.get("postponed_count") or 0)
    except (TypeError, ValueError):
        postponed = 0
    return {
        "title": title,
        "notes": str(raw.get("notes") or ""),
        "due_at": _normalize_time(raw.get("due_at")),
        "remind_at": _normalize_time(raw.get("remind_at")),
        "repeat_rule": repeat if repeat in REPEAT_IDS else "none",
        "priority": priority if priority in PRIORITY_IDS else "medium",
        "tags": _normalize_tags(raw.get("tags")),
        "status": status if status in STATUS_IDS else "todo",
        "completed_at": _normalize_time(raw.get("completed_at")),
        "postponed_count": max(0, postponed),
        "remind_fired_at": _normalize_time(raw.get("remind_fired_at")),
        "id": str(raw.get("id") or uuid.uuid4().hex[:12]),
        "created_at": created or time.time(),
    }


class Todo:
    """待办清单。``path`` 是 jsON 文件，``notifier(title, body)`` 用来弹系统通知。"""

    def __init__(self, path, notifier=None, icon_path=None):
        self._path = path
        self._notifier = notifier
        self._icon_path = icon_path
        self._lock = threading.RLock()
        self._items = []
        self._thread = None
        self._stop = threading.Event()
        self._load()

    # ---------------- 存储 ----------------

    def _load(self):
        try:
            raw = self._path.read_text(encoding="utf-8")
        except (OSError, AttributeError):
            self._items = []
            return
        try:
            data = json.loads(raw)
        except ValueError:
            self._items = []
            return
        items = data.get("items") if isinstance(data, dict) else data
        rows = []
        if isinstance(items, list):
            for row in items:
                clean = _clean_item(row)
                if clean:
                    rows.append(clean)
        self._items = rows

    def _save_locked(self):
        write_text(self._path, json.dumps({"items": self._items},
                                          ensure_ascii=False, indent=2))

    # ---------------- 小工具 ----------------

    def _find_locked(self, item_id):
        for item in self._items:
            if item["id"] == item_id:
                return item
        return None

    @staticmethod
    def _decorate(item, today=None):
        """查出来的每条都带上 is_today / is_overdue，界面直接用。"""
        today = today or _now().date()
        due_day = _day_of(item.get("due_at"))
        row = dict(item)
        row["tags"] = list(item.get("tags") or [])
        row["is_today"] = bool(due_day and due_day == today)
        row["is_overdue"] = bool(due_day and due_day < today)
        return row

    @staticmethod
    def _sort_key(item):
        """先按截止时间，再按优先级，最后新的排前面；没有截止时间的垫底。"""
        due = item.get("due_at") or ""
        return (not due, due, PRIORITY_RANK.get(item.get("priority"), 1),
                -(item.get("created_at") or 0))

    def _materialize(self, due, rule):
        """按重复规则算下一次的时间。没有原来那个点时从现在起算一个周期。"""
        if rule not in REPEAT_IDS or rule == "none":
            return None
        base = _as_datetime(due) if due else _now()
        if not due:
            base = _now().replace(second=0, microsecond=0)
        moved = next_occurrence(base, rule)
        return moved.strftime("%Y-%m-%dT%H:%M") if moved else None

    def _spawn_next_locked(self, item):
        """重复任务做完一条，排下一条。"""
        rule = item.get("repeat_rule")
        moved = self._materialize(item.get("due_at"), rule)
        if not moved:
            return None
        fresh = {
            "title": item["title"],
            "notes": item.get("notes") or "",
            "due_at": moved,
            "remind_at": moved,
            "repeat_rule": rule,
            "priority": item.get("priority") or "medium",
            "tags": list(item.get("tags") or []),
            "status": "todo",
            "completed_at": None,
            "postponed_count": 0,
            "remind_fired_at": None,
            "id": uuid.uuid4().hex[:12],
            "created_at": time.time(),
        }
        self._items.append(fresh)
        return dict(fresh)

    # ---------------- 增删改查 ----------------

    def create(self, payload):
        payload = payload if isinstance(payload, dict) else {}
        title = str(payload.get("title") or "").strip() or UNTITLED
        due = _normalize_time(payload.get("due_at")) or _normalize_time(payload.get("remind_at"))
        remind = _normalize_time(payload.get("remind_at")) or None
        priority = payload.get("priority")
        repeat = payload.get("repeat_rule")
        status = payload.get("status")
        item = {
            "title": title,
            "notes": str(payload.get("notes") or "").strip(),
            "due_at": due,
            "remind_at": remind,
            "repeat_rule": repeat if repeat in REPEAT_IDS else "none",
            "priority": priority if priority in PRIORITY_IDS else "medium",
            "tags": _normalize_tags(payload.get("tags")),
            "status": status if status in STATUS_IDS else "todo",
            "completed_at": _normalize_time(payload.get("completed_at")),
            "postponed_count": 0,
            "remind_fired_at": None,
            "id": uuid.uuid4().hex[:12],
            "created_at": time.time(),
        }
        with self._lock:
            self._items.append(item)
            self._save_locked()
        return dict(item)

    def get(self, item_id):
        with self._lock:
            item = self._find_locked(item_id)
            return dict(item) if item else None

    def list(self, view="today", tag=None, priority=None, query=""):
        """``view`` 只认 today / done，其它都当"全部未完成"。"""
        now = _now()
        today = now.date()
        needle = str(query or "").strip().lower()
        with self._lock:
            rows = [dict(item) for item in self._items]

        picked = []
        for item in rows:
            status = item.get("status")
            if view == "done":
                if status != "done":
                    continue
            elif view == "today":
                due_day = _day_of(item.get("due_at"))
                if status != "todo" or not due_day or due_day > today:
                    continue
            else:
                if status != "todo":
                    continue
            if tag and tag not in (item.get("tags") or []):
                continue
            if priority and item.get("priority") != priority:
                continue
            if needle:
                haystack = " ".join([item.get("title") or "", item.get("notes") or "",
                                     " ".join(item.get("tags") or [])]).lower()
                if needle not in haystack:
                    continue
            picked.append(item)

        picked.sort(key=self._sort_key)
        return [self._decorate(item, today) for item in picked]

    def update(self, item_id, payload):
        payload = payload if isinstance(payload, dict) else {}
        with self._lock:
            item = self._find_locked(item_id)
            if not item:
                return None
            if "title" in payload:
                title = str(payload.get("title") or "").strip()
                if title:
                    item["title"] = title
            if "notes" in payload:
                item["notes"] = str(payload.get("notes") or "").strip()
            if "due_at" in payload:
                item["due_at"] = _normalize_time(payload.get("due_at"))
            if "remind_at" in payload:
                item["remind_at"] = _normalize_time(payload.get("remind_at"))
            if "repeat_rule" in payload:
                rule = payload.get("repeat_rule")
                item["repeat_rule"] = rule if rule in REPEAT_IDS else "none"
            if "priority" in payload:
                level = payload.get("priority")
                item["priority"] = level if level in PRIORITY_IDS else "medium"
            if "tags" in payload:
                item["tags"] = _normalize_tags(payload.get("tags"))
            if "status" in payload:
                status = payload.get("status")
                item["status"] = status if status in STATUS_IDS else "todo"
            self._save_locked()
            return dict(item)

    def delete(self, item_id):
        with self._lock:
            for index, item in enumerate(self._items):
                if item["id"] == item_id:
                    del self._items[index]
                    self._save_locked()
                    return True
        return False

    def delete_many(self, ids):
        wanted = set(ids or [])
        if not wanted:
            return 0
        with self._lock:
            before = len(self._items)
            self._items = [item for item in self._items if item["id"] not in wanted]
            removed = before - len(self._items)
            if removed:
                self._save_locked()
            return removed

    # ---------------- 状态流转 ----------------

    def complete(self, item_id):
        """勾掉一条。重复任务会顺手排下一条，返回 ``(完成的, 新的)``。"""
        with self._lock:
            item = self._find_locked(item_id)
            if not item:
                return None, None
            was_open = item.get("status") == "todo"
            item["status"] = "done"
            item["completed_at"] = _now().strftime("%Y-%m-%dT%H:%M")
            following = None
            if was_open and item.get("repeat_rule") not in (None, "none"):
                following = self._spawn_next_locked(item)
            finished = dict(item)
            self._save_locked()
        return finished, following

    def reopen(self, item_id):
        with self._lock:
            item = self._find_locked(item_id)
            if not item:
                return None
            item["status"] = "todo"
            item["completed_at"] = None
            self._save_locked()
            return dict(item)

    def cancel(self, item_id):
        with self._lock:
            item = self._find_locked(item_id)
            if not item:
                return None
            item["status"] = "cancelled"
            item["completed_at"] = None
            self._save_locked()
            return dict(item)

    def postpone(self, item_id, days=1, minutes=0):
        """往后推一推，并记一笔"这事推过几次"。没有截止时间的只记账不补时间。"""
        delta = timedelta(days=int(days or 0), minutes=int(minutes or 0))
        with self._lock:
            item = self._find_locked(item_id)
            if not item:
                return None
            due = _as_datetime(item.get("due_at"))
            if due:
                item["due_at"] = (due + delta).strftime("%Y-%m-%dT%H:%M")
            remind = _as_datetime(item.get("remind_at"))
            if remind:
                item["remind_at"] = (remind + delta).strftime("%Y-%m-%dT%H:%M")
                item["remind_fired_at"] = None
            item["postponed_count"] = int(item.get("postponed_count") or 0) + 1
            self._save_locked()
            return dict(item)

    def clear_done(self):
        with self._lock:
            before = len(self._items)
            self._items = [item for item in self._items if item.get("status") != "done"]
            removed = before - len(self._items)
            if removed:
                self._save_locked()
            return removed

    # ---------------- 提醒 ----------------

    def pending_reminders(self, now=None):
        """到点但还没提醒过的那些。"""
        moment = now or _now()
        with self._lock:
            rows = [dict(item) for item in self._items]
        found = []
        for item in rows:
            if item.get("status") != "todo" or item.get("remind_fired_at"):
                continue
            remind = _as_datetime(item.get("remind_at"))
            if remind and remind <= moment:
                found.append(item)
        found.sort(key=self._sort_key)
        return found

    def mark_reminded(self, item_id, when=None):
        moment = when or _now()
        with self._lock:
            item = self._find_locked(item_id)
            if not item:
                return None
            item["remind_fired_at"] = moment.strftime("%Y-%m-%dT%H:%M")
            self._save_locked()
            return dict(item)

    def pop_due_notifications(self, now=None):
        """把到点的通知弹出去，弹过的记上，同一条不会弹第二次。"""
        moment = now or _now()
        announced = []
        for item in self.pending_reminders(moment):
            notified = True
            if self._notifier:
                title = item["title"]
                body = "该动手了" if not item.get("notes") else item["notes"]
                try:
                    if self._icon_path:
                        notified = bool(self._notifier(title, body, self._icon_path))
                    else:
                        notified = bool(self._notifier(title, body))
                except TypeError:
                    notified = bool(self._notifier(title, body))
                except Exception:
                    notified = False
            self.mark_reminded(item["id"], moment)
            announced.append({"item": dict(item), "notified": notified})
        return announced

    def start_scheduler(self):
        """开个后台线程盯着提醒。重复调用不会起第二个。"""
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop.clear()
            self._thread = threading.Thread(target=self._loop, name="pt-todo-reminder",
                                            daemon=True)
            self._thread.start()

    def stop_scheduler(self):
        with self._lock:
            self._stop.set()
            self._thread = None

    def _loop(self):
        while not self._stop.is_set():
            try:
                self.pop_due_notifications()
            except Exception:
                pass
            self._stop.wait(CHECK_INTERVAL)

    # ---------------- 统计与迁移 ----------------

    def stats(self):
        today = _now().date()
        open_items = [item for item in self._items if item.get("status") == "todo"]
        today_count = overdue_count = 0
        for item in open_items:
            due_day = _day_of(item.get("due_at"))
            if not due_day:
                continue
            if due_day < today:
                overdue_count += 1
                today_count += 1
            elif due_day == today:
                today_count += 1
        tags = {}
        for item in open_items:
            for tag in item.get("tags") or []:
                tags[tag] = tags.get(tag, 0) + 1
        return {
            "today_count": today_count,
            "todo_count": len(open_items),
            "done_count": sum(1 for item in self._items if item.get("status") == "done"),
            "overdue_count": overdue_count,
            "high_count": sum(1 for item in open_items if item.get("priority") == "high"),
            "tags": tags,
            "total": len(self._items),
        }

    def export(self):
        with self._lock:
            return json.dumps({"items": self._items}, ensure_ascii=False, indent=2)

    def import_data(self, text, merge=True):
        """吃一份导出过的 JSON。``merge=False`` 就是整份替换。"""
        if isinstance(text, (bytes, bytearray)):
            text = text.decode("utf-8", "replace")
        try:
            data = json.loads(text)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"JSON 解析失败：{exc}") from None
        items = data.get("items") if isinstance(data, dict) else data
        if not isinstance(items, list):
            raise ValueError("JSON 里没有 items 列表")
        rows = []
        for row in items:
            clean = _clean_item(row)
            if clean:
                rows.append(clean)
        with self._lock:
            if merge:
                known = {item["id"] for item in self._items}
                for row in rows:
                    if row["id"] in known:
                        row = dict(row, id=uuid.uuid4().hex[:12])
                    self._items.append(row)
            else:
                self._items = rows
            self._save_locked()
            return {"added": len(rows), "total": len(self._items)}
