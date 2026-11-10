"""界面层的补充存储。

这里存的是「界面上看到的状态」：每日规划、笔记分类、番茄钟记录、倒数日、
心情日记、图表数据、界面偏好。内核 `ptools` 只管程序自己的数据（笔记正文、
待办、历史），两边各存各的 JSON，谁的字段变了都不牵连另一边。
"""

import json
import os
import tempfile
import time
import uuid
from pathlib import Path

PLAN_CATEGORIES = {"work", "life", "study", "idea", "other"}
FOCUS_KINDS = {"focus", "break"}
COUNTDOWN_REPEATS = {"none", "year", "month"}
MOOD_RANGE = {1, 2, 3, 4, 5}


def _read_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else default
    except Exception:
        return default


def _write_json(path, data):
    """先写临时文件再替换，避免写一半断电把数据弄坏。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except Exception:
            pass
        raise


def _minutes(value, fallback):
    """"09:30" -> 570；非法值返回 fallback。"""
    try:
        hour, minute = str(value).split(":")[:2]
        return max(0, min(24 * 60, int(hour) * 60 + int(minute)))
    except Exception:
        return fallback


def _hhmm(minutes):
    minutes = max(0, min(24 * 60, int(minutes)))
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _normalize_items(raw):
    items = []
    for entry in raw if isinstance(raw, list) else []:
        if not isinstance(entry, dict):
            continue
        title = str(entry.get("title") or "").strip()
        if not title:
            continue
        start = _minutes(entry.get("start"), 9 * 60)
        end = _minutes(entry.get("end"), start + 60)
        if end <= start:
            end = min(24 * 60, start + 30)
        category = entry.get("category")
        items.append({
            "id": str(entry.get("id") or uuid.uuid4().hex[:12]),
            "title": title[:120],
            "start": _hhmm(start),
            "end": _hhmm(end),
            "category": category if category in PLAN_CATEGORIES else "work",
            "notes": str(entry.get("notes") or "")[:400],
            "done": bool(entry.get("done")),
        })
    items.sort(key=lambda it: it["start"])
    return items


class PlanStore:
    """按天存时间块：{"2026-11-09": [ {...}, ... ]}"""

    def __init__(self, path):
        self.path = Path(path)
        self.data = _read_json(self.path, {})

    def get(self, date):
        return _normalize_items(self.data.get(str(date)))

    def save(self, date, items):
        key = str(date)
        normalized = _normalize_items(items)
        if normalized:
            self.data[key] = normalized
        else:
            self.data.pop(key, None)
        # 只保留最近 400 天，防止文件无限增长
        if len(self.data) > 400:
            for old in sorted(self.data)[:-400]:
                self.data.pop(old, None)
        _write_json(self.path, self.data)
        return normalized

    def stats(self, date):
        items = self.get(date)
        return {
            "total": len(items),
            "done": sum(1 for it in items if it["done"]),
            "minutes": sum(
                _minutes(it["end"], 0) - _minutes(it["start"], 0) for it in items
            ),
        }

    def search(self, query, limit=10, days=180):
        """在最近的日程里找标题/备注，供全局搜索使用。"""
        q = str(query or "").lower()
        out = []
        for date in sorted(self.data, reverse=True)[:days]:
            for item in _normalize_items(self.data.get(date)):
                if q in item["title"].lower() or q in item["notes"].lower():
                    out.append({"date": date, **item})
                    if len(out) >= limit:
                        return out
        return out


class NoteMetaStore:
    """笔记附加信息：{"notes": {"<note_id>": {"category": "work"}}}"""

    def __init__(self, path):
        self.path = Path(path)
        self.data = _read_json(self.path, {})
        if not isinstance(self.data.get("notes"), dict):
            self.data["notes"] = {}

    @property
    def notes(self):
        return self.data["notes"]

    def all(self):
        return dict(self.notes)

    def set(self, note_id, category):
        note_id = str(note_id)
        if not note_id:
            return
        if category in (None, "", "none"):
            self.notes.pop(note_id, None)
        else:
            self.notes[note_id] = {"category": str(category), "at": int(time.time())}
        _write_json(self.path, self.data)

    def remove(self, note_id):
        if str(note_id) in self.notes:
            self.notes.pop(str(note_id), None)
            _write_json(self.path, self.data)

    def prune(self, valid_ids):
        valid = {str(i) for i in valid_ids}
        stale = [key for key in self.notes if key not in valid]
        if stale:
            for key in stale:
                self.notes.pop(key, None)
            _write_json(self.path, self.data)
        return len(stale)

    # ---- v2.2：给全局搜索用 ----
    def categories(self):
        return {key: value.get("category") for key, value in self.notes.items()}


def _day_key(value):
    """规范成 YYYY-MM-DD；非法值退回今天。"""
    text = str(value or "")[:10]
    try:
        time.strptime(text, "%Y-%m-%d")
        return text
    except Exception:
        return time.strftime("%Y-%m-%d")


def _snippet(text, query, width=34):
    """截取关键词附近的一小段，供搜索结果展示。"""
    text = " ".join(str(text or "").split())
    if not text:
        return ""
    pos = text.lower().find(str(query).lower())
    if pos < 0:
        return text[: width * 2] + ("…" if len(text) > width * 2 else "")
    start = max(0, pos - width)
    end = min(len(text), pos + width)
    return ("…" if start else "") + text[start:end] + ("…" if end < len(text) else "")


class FocusStore:
    """番茄钟记录：{"sessions": [{kind, minutes, label, started, ended}]}"""

    def __init__(self, path):
        self.path = Path(path)
        self.data = _read_json(self.path, {})
        if not isinstance(self.data.get("sessions"), list):
            self.data["sessions"] = []

    @property
    def sessions(self):
        return self.data["sessions"]

    def add(self, entry):
        if not isinstance(entry, dict):
            return None
        minutes = int(entry.get("minutes") or 0)
        minutes = max(1, min(180, minutes))
        kind = entry.get("kind") if entry.get("kind") in FOCUS_KINDS else "focus"
        now = time.time()
        item = {
            "id": str(entry.get("id") or uuid.uuid4().hex[:12]),
            "kind": kind,
            "minutes": minutes,
            "label": str(entry.get("label") or "").strip()[:60],
            "started": float(entry.get("started") or now - minutes * 60),
            "ended": float(entry.get("ended") or now),
            "completed": bool(entry.get("completed", True)),
        }
        self.sessions.insert(0, item)
        del self.sessions[500:]
        _write_json(self.path, self.data)
        return item

    def recent(self, limit=20):
        return self.sessions[: max(1, int(limit))]

    def stats(self, day=None):
        day = _day_key(day or time.strftime("%Y-%m-%d"))
        focus = [s for s in self.sessions if s.get("kind") == "focus" and s.get("completed")]
        today = [s for s in focus if _day_key(time.strftime("%Y-%m-%d", time.localtime(s["started"]))) == day]
        days = {_day_key(time.strftime("%Y-%m-%d", time.localtime(s["started"]))) for s in focus}
        # 连续天数：从今天（或昨天）往前数，断了就停
        streak = 0
        cursor = time.strptime(day, "%Y-%m-%d")
        base = time.mktime((cursor.tm_year, cursor.tm_mon, cursor.tm_mday, 12, 0, 0, 0, 0, -1))
        today_key = time.strftime("%Y-%m-%d")
        if day not in days and day == today_key:
            base -= 86400  # 今天还没开始，允许从昨天算
        while True:
            key = time.strftime("%Y-%m-%d", time.localtime(base))
            if key in days:
                streak += 1
                base -= 86400
            else:
                break
        return {
            "date": day,
            "today_minutes": sum(int(s["minutes"]) for s in today),
            "today_rounds": len(today),
            "total_rounds": len(focus),
            "total_minutes": sum(int(s["minutes"]) for s in focus),
            "streak": streak,
            "days": len(days),
        }


class CountdownStore:
    """倒数日：{"items": [{id, title, date, repeat, note}]}"""

    def __init__(self, path):
        self.path = Path(path)
        self.data = _read_json(self.path, {})
        if not isinstance(self.data.get("items"), list):
            self.data["items"] = []

    def all(self):
        return list(self.data["items"])

    def upsert(self, item):
        if not isinstance(item, dict):
            return None
        title = str(item.get("title") or "").strip()
        if not title:
            return None
        repeat = item.get("repeat") if item.get("repeat") in COUNTDOWN_REPEATS else "none"
        entry = {
            "id": str(item.get("id") or uuid.uuid4().hex[:12]),
            "title": title[:60],
            "date": _day_key(item.get("date")),
            "repeat": repeat,
            "note": str(item.get("note") or "")[:200],
            "created": float(item.get("created") or time.time()),
        }
        items = self.data["items"]
        has_id = bool(str(item.get("id") or "").strip())
        for index, old in enumerate(items):
            if old.get("id") == entry["id"]:
                entry["created"] = old.get("created", entry["created"])
                items[index] = entry
                break
        else:
            # 新增时挡掉完全重复的一条（同标题 + 同日期 + 同重复规则）
            for old in (items if not has_id else ()):
                if (str(old.get("title") or "").strip().lower() == entry["title"].lower()
                        and old.get("date") == entry["date"]
                        and old.get("repeat") == entry["repeat"]):
                    return old
            items.append(entry)
        _write_json(self.path, self.data)
        return entry

    def remove(self, item_id):
        before = len(self.data["items"])
        self.data["items"] = [it for it in self.data["items"] if it.get("id") != str(item_id)]
        if len(self.data["items"]) != before:
            _write_json(self.path, self.data)
        return before - len(self.data["items"])

    def search(self, query, limit=10):
        q = str(query or "").lower()
        out = []
        for item in self.data["items"]:
            if q in item.get("title", "").lower() or q in item.get("note", "").lower():
                out.append(item)
                if len(out) >= limit:
                    break
        return out


class MoodStore:
    """心情日记：{"days": {"2026-11-09": {mood, text, at}}}"""

    def __init__(self, path):
        self.path = Path(path)
        self.data = _read_json(self.path, {})
        if not isinstance(self.data.get("days"), dict):
            self.data["days"] = {}

    @property
    def days(self):
        return self.data["days"]

    def month(self, ym):
        key = str(ym or time.strftime("%Y-%m"))[:7]
        return {day: entry for day, entry in self.days.items() if day.startswith(key)}

    def get(self, day):
        return self.days.get(_day_key(day))

    def set(self, day, mood, text=""):
        day = _day_key(day)
        mood = int(mood) if str(mood).isdigit() else 0
        text = str(text or "").strip()[:120]
        if mood not in MOOD_RANGE and not text:
            self.days.pop(day, None)
        elif mood in MOOD_RANGE:
            self.days[day] = {"mood": mood, "text": text, "at": time.time()}
        else:
            # 只写文字不选心情：沿用当天已有心情，没有就记成中性
            old = self.days.get(day) or {}
            self.days[day] = {"mood": old.get("mood", 3), "text": text, "at": time.time()}
        _write_json(self.path, self.data)
        return self.days.get(day)

    def remove(self, day):
        day = _day_key(day)
        if day in self.days:
            self.days.pop(day, None)
            _write_json(self.path, self.data)
            return True
        return False

    def recent(self, limit=7):
        keys = sorted(self.days, reverse=True)[: max(1, int(limit))]
        return [{"date": key, **self.days[key]} for key in keys]

    def stats(self, ym):
        month = self.month(ym)
        moods = [entry.get("mood", 0) for entry in month.values() if entry.get("mood")]
        # 连续记录天数：从今天往前数
        streak = 0
        cursor = time.time()
        while time.strftime("%Y-%m-%d", time.localtime(cursor)) in self.days:
            streak += 1
            cursor -= 86400
        return {
            "days": len(month),
            "avg": round(sum(moods) / len(moods), 1) if moods else 0,
            "streak": streak,
            "total": len(self.days),
            "best": max(moods) if moods else 0,
        }

    def search(self, query, limit=10):
        q = str(query or "").lower()
        out = []
        for day, entry in sorted(self.days.items(), reverse=True):
            if q in entry.get("text", "").lower():
                out.append({"date": day, **entry})
                if len(out) >= limit:
                    break
        return out


class ChartStore:
    """数据成图：只留最近一次粘贴的原始文本，方便下次接着改。"""

    def __init__(self, path):
        self.path = Path(path)
        self.data = _read_json(self.path, {})

    def get(self):
        last = self.data.get("last")
        return last if isinstance(last, dict) else None

    def save(self, payload):
        if not isinstance(payload, dict):
            return None
        entry = {
            "raw": str(payload.get("raw") or "")[:20000],
            "type": str(payload.get("type") or "bar")[:10],
            "title": str(payload.get("title") or "")[:80],
            "at": time.time(),
        }
        self.data["last"] = entry
        _write_json(self.path, self.data)
        return entry



class PrefsStore:
    """界面偏好单独存一个文件。

    `ptools.config.Settings` 只认自己的键白名单（那是给后端用的配置），
    而 localStorage 又因为本地服务每次换端口（源不同）没法跨启动保留。
    所以主题色、密度、动效、启动页、关闭行为这类纯界面偏好放这里。
    """

    MAX_BYTES = 32 * 1024

    def __init__(self, path):
        self._path = Path(path)
        raw = _read_json(self._path, {})
        self._data = {str(k): v for k, v in raw.items() if isinstance(k, str)}

    def all(self):
        return dict(self._data)

    def update(self, patch):
        if not isinstance(patch, dict):
            return self.all()
        for key, value in patch.items():
            name = str(key)[:40]
            if value is None:
                self._data.pop(name, None)
            elif isinstance(value, (str, int, float, bool)):
                self._data[name] = value[:200] if isinstance(value, str) else value
        try:
            if len(json.dumps(self._data, ensure_ascii=False)) <= self.MAX_BYTES:
                _write_json(self._path, self._data)
        except Exception:
            pass
        return self.all()
