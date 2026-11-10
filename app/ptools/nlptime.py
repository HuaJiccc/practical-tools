"""中文待办的自然语言解析。

全在本地用规则完成，不联网。只有连时间都没识别出来时，调用方才需要考虑
用 AI 兜底（见 ``api.todo_parse``）。

能认的写法大致是：

    明天下午三点开会 / 今晚八点吃饭 / 后天 / 3 天后 / 下周三上午 9 点
    12 月 25 日 / 每月 5 号 / 每天跑步 / 每周一开会 / 十点半提醒我
    1 小时后 / 30 分钟后 / 紧急：马上处理 / 不急 有空再看
    开会 #工作 #生活

识别出的时间词会从标题里摘掉，剩下的就是任务名。
"""

import datetime
import re

CN_DIGITS = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
             "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}

# 这些词只是口语铺垫，不构成任务名
NOISE = ["提醒我一下", "提醒一下", "提醒我", "提醒", "记一下", "记住", "记得",
         "帮我", "我要去", "我要", "需要", "别忘", "不要忘", "到点"]

# (正则, 加小时数, 是否"下午一点"要按 13 点算)
PERIODS = [
    ("凌晨", 0, False),
    ("清晨|早上|早晨|上午|早", 0, False),
    ("中午|正午", 12, True),
    ("下午|傍晚|午后", 12, False),
    ("晚上|夜里|晚间|晚", 12, False),
]

# 只说了"早上/下午/晚上"没说几点时，按那一段的惯常时间给一个
PERIOD_DEFAULT_HOUR = [
    ("凌晨|深夜", 5),
    ("清晨|早上|早晨|早", 8),
    ("上午", 9),
    ("中午|正午", 12),
    ("下午|午后", 15),
    ("傍晚", 18),
    ("晚上|晚间", 20),
    ("夜里|夜间", 21),
]

# "今晚/明早"这类"日期字 + 时段字"的缩写，单独成词才好认
# 值 = (相对今天的天数, 该时段的默认小时)
DAY_PERIOD_WORDS = {
    "今晚": (0, 20), "今夜": (0, 21), "今早": (0, 8), "今晨": (0, 8),
    "明晚": (1, 20), "明夜": (1, 21), "明早": (1, 8), "明晨": (1, 8),
    "后晚": (2, 20), "后早": (2, 8),
}

WEEKDAYS = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6, "七": 6}

REPEAT_PATTERNS = [
    ("每天|每日|天天", "daily"),
    ("每周|每星期|每礼拜|每个星期", "weekly"),
    ("每月|每个月", "monthly"),
    ("每年|每年一度|年度", "yearly"),
]

PRIORITY_HIGH = "重要|紧急|急|尽快|马上"
PRIORITY_LOW = "不急|随便|有空|闲时|低优先"

DEFAULT_HOUR = 9  # 只说了日期没说时间，默认早上 9 点

_DAY_PERIOD = re.compile("|".join(sorted(DAY_PERIOD_WORDS, key=len, reverse=True)))
_DATE_CN = re.compile(r"(?:(明年)|(\d{4})年)?\s*(\d{1,2}|[一二三四五六七八九十]{1,2})月\s*"
                      r"(\d{1,2}|[一二三四五六七八九十]{1,2})[日号]")
_TIME_CN = re.compile(r"(凌晨|清晨|早上|早晨|上午|中午|正午|下午|傍晚|午后|晚上|夜里|晚间|晚|早)?\s*"
                      r"([零〇一二两三四五六七八九十\d]{1,3})\s*[点时]"
                      r"(?:\s*(半|一刻|三刻|[\d零〇一二两三四五六七八九十]{1,2})\s*分?)?")
_TIME_COLON = re.compile(r"(凌晨|清晨|早上|早晨|上午|中午|正午|下午|傍晚|午后|晚上|夜里|晚间|晚|早)?\s*"
                         r"(\d{1,2})\s*[:：]\s*(\d{2})")
_SPAN_LATER = re.compile(r"(\d+(?:\.\d+)?|[零〇一二两三四五六七八九十]{1,3})\s*个?\s*"
                         r"(小时|钟头|分钟|分|天|日)\s*(?:以)?后")
_DAY_OFFSET = re.compile(r"(\d+|[零〇一二两三四五六七八九十]{1,3})\s*天(?:以)?后")
_DAY_WORD = re.compile(r"(今天|今日|明天|明日|后天|大后天)")
_WEEK_WORD = re.compile(r"(下下|下|这|本)?\s*(?:周|星期|礼拜)\s*([一二三四五六日天七])")
_MONTH_DAY = re.compile(r"每(?:个)?月\s*(\d{1,2}|[一二三四五六七八九十]{1,2})\s*[日号]")
_TAG = re.compile(r"#([^\s#]+)")


def cn_number(text):
    """中文数字转整数：三 -> 3，十五 -> 15，二十 -> 20，2 -> 2。"""
    raw = str(text or "").strip()
    if not raw:
        return None
    if raw.isdigit():
        return int(raw)
    if raw in CN_DIGITS:
        return CN_DIGITS[raw]
    if "十" in raw:
        head, _, tail = raw.partition("十")
        tens = CN_DIGITS.get(head, 1) if head else 1
        ones = CN_DIGITS.get(tail, 0) if tail else 0
        return tens * 10 + ones
    # 二十以上没有"十"字的情况（例如 二五）按位拼
    total = 0
    for ch in raw:
        if ch not in CN_DIGITS:
            return None
        total = total * 10 + CN_DIGITS[ch]
    return total


def _period_of(text):
    """返回 (加的小时数, 是否是"下午一点"这种)。"""
    for pattern, plus, afternoon in PERIODS:
        if re.search(pattern, text):
            return plus, afternoon
    return 0, False


def _default_hour(text, fallback=DEFAULT_HOUR):
    """只说了"早上/下午/晚上"没说几点时，按那一段的惯常时间给一个。"""
    for pattern, hour in PERIOD_DEFAULT_HOUR:
        if re.search(pattern, str(text or "")):
            return hour
    return fallback


def _next_weekday(now, weekday, which=''):
    """算出下一个周几。``which`` 为 下 / 下下 / 这 时按"自然周"计算。"""
    today = now.weekday()
    if which == '下下':
        days = (6 - today) + 8 + weekday
    elif which == '下':
        days = (6 - today) + 1 + weekday
    elif which in ('这', '本'):
        days = weekday - today
        if days <= 0:          # 就是今天（或已经过去）算下周
            days += 7
    else:
        days = (weekday - today) % 7 or 7
    return now + datetime.timedelta(days=days)


def _fmt(moment):
    return moment.strftime("%Y-%m-%dT%H:%M")


def _blank(title=""):
    return {"title": title, "notes": "", "due_at": None, "remind_at": None,
            "repeat_rule": "none", "priority": "medium", "tags": [],
            "matched_time": False, "source": "local"}


def _span_later(work, moment):
    """1 小时后 / 30 分钟后 / 3 天后。返回 (新的 due, 处理过的文本) 或 (None, work)。"""
    m = _SPAN_LATER.search(work)
    if not m:
        return None, work
    amount = m.group(1)
    try:
        value = float(amount)
    except ValueError:
        number = cn_number(amount)
        if not number:
            return None, work
        value = float(number)
    unit = m.group(2)
    if unit in ("小时", "钟头"):
        due = moment + datetime.timedelta(hours=value)
    elif unit == "天":
        # 只说了几天后，时间按默认的早上 9 点算，跟"明天"一个待遇
        base = moment + datetime.timedelta(days=value)
        due = base.replace(hour=DEFAULT_HOUR, minute=0, second=0, microsecond=0)
        if due <= moment:
            due += datetime.timedelta(days=1)
    else:
        due = moment + datetime.timedelta(minutes=value)
    rest = work[:m.start()] + " " + work[m.end():]
    return due.replace(second=0, microsecond=0), rest


def parse(text, now=None):
    """解析一条自然语言待办。"""
    raw = str(text or "").strip()
    moment = now or datetime.datetime.now()
    if not raw:
        return _blank()

    work = raw

    tags = []
    for name in _TAG.findall(work):
        name = name.strip()
        if name and name not in tags:
            tags.append(name)
    work = _TAG.sub(" ", work)

    repeat = "none"
    for pattern, rule in REPEAT_PATTERNS:
        if re.search(pattern, work):
            repeat = rule
            break

    priority = "medium"
    if re.search(PRIORITY_HIGH, work):
        priority = "high"
    elif re.search(PRIORITY_LOW, work):
        priority = "low"

    # ---- 相对时间（"1 小时后""30 分钟后"）独立成套，不再叠日期 ----
    due, work = _span_later(work, moment)
    if due is not None:
        return {
            "title": _clean_title(work),
            "notes": "",
            "due_at": _fmt(due),
            "remind_at": _fmt(due),
            "repeat_rule": repeat,
            "priority": priority,
            "tags": tags,
            "matched_time": True,
            "source": "local",
        }

    date_hit = None   # (年, 月, 日)
    time_hit = None   # (时, 分)
    hinted_hour = None  # "今晚"这种词自带的小时

    # ---- 日期 ----
    # "今晚/明早"先当整体认，免得"今""明"被日期的正则拆开
    m = _DAY_PERIOD.search(work)
    if m:
        offset, hour = DAY_PERIOD_WORDS[m.group(0)]
        target = moment + datetime.timedelta(days=offset)
        date_hit = (target.year, target.month, target.day)
        hinted_hour = hour
        work = work.replace(m.group(0), " ")

    if not date_hit:
        m = _DATE_CN.search(work)
        if m:
            next_year, year_text, month_text, day_text = m.groups()
            month = cn_number(month_text)
            day = cn_number(day_text)
            if month and day and 1 <= month <= 12 and 1 <= day <= 31:
                year = moment.year
                if year_text:
                    year = int(year_text)
                elif next_year or (month, day) < (moment.month, moment.day):
                    # "12 月 25 日"指下一个 12 月 25 日，不是今年的那一天
                    year += 1
                date_hit = (year, month, day)
                work = work.replace(m.group(0), " ")

    if not date_hit:
        m = _DAY_OFFSET.search(work)
        if m:
            days = cn_number(m.group(1))
            if days:
                target = moment + datetime.timedelta(days=days)
                date_hit = (target.year, target.month, target.day)
                work = work.replace(m.group(0), " ")

    if not date_hit:
        m = _DAY_WORD.search(work)
        if m:
            offset = {"今天": 0, "今日": 0, "明天": 1, "明日": 1,
                      "后天": 2, "大后天": 3}[m.group(1)]
            target = moment + datetime.timedelta(days=offset)
            date_hit = (target.year, target.month, target.day)
            work = work.replace(m.group(0), " ")

    if not date_hit:
        m = _WEEK_WORD.search(work)
        if m:
            weekday = WEEKDAYS.get(m.group(2))
            if weekday is not None:
                target = _next_weekday(moment, weekday, m.group(1) or '')
                date_hit = (target.year, target.month, target.day)
                work = work.replace(m.group(0), " ")

    # 每月 5 号：跟 repeat_rule 一起用，日期取最近一次
    if repeat == "monthly":
        m = _MONTH_DAY.search(work)
        if m:
            day = cn_number(m.group(1))
            if day:
                year, month = moment.year, moment.month
                if day < moment.day:
                    month += 1
                    if month > 12:
                        month, year = 1, year + 1
                try:
                    datetime.date(year, month, day)
                    date_hit = (year, month, day)
                    work = work.replace(m.group(0), " ")
                except ValueError:
                    pass

    # ---- 时间 ----
    m = _TIME_COLON.search(work)
    if m:
        period, hour_text, minute_text = m.groups()
        hour = cn_number(hour_text)
        minute = cn_number(minute_text)
        if hour is not None and minute is not None and 0 <= hour <= 23 and 0 <= minute <= 59:
            plus, afternoon = _period_of(period or "")
            if plus and hour < 12:
                hour += plus
            elif not plus and afternoon and hour < 12:
                hour += 12
            if hour <= 23:
                time_hit = (hour, minute)
                work = work.replace(m.group(0), " ")
            else:
                time_hit = None
    if time_hit is None:
        m = _TIME_CN.search(work)
        if m:
            period, hour_text, minute_text = m.groups()
            hour = cn_number(hour_text)
            if hour is not None and 0 <= hour <= 24:
                minute = 0
                if minute_text:
                    if minute_text == "半":
                        minute = 30
                    elif minute_text == "一刻":
                        minute = 15
                    elif minute_text == "三刻":
                        minute = 45
                    else:
                        minute = cn_number(minute_text) or 0
                plus, afternoon = _period_of(period or "")
                if plus and hour < 12:
                    hour += plus
                elif not plus and afternoon and hour < 12:
                    hour += 12
                if hour == 24:
                    hour = 0
                if 0 <= hour <= 23 and 0 <= minute <= 59:
                    time_hit = (hour, minute)
                    work = work.replace(m.group(0), " ")

    # ---- 拼成时间点 ----
    if time_hit and hinted_hour is not None and hinted_hour >= 12 and time_hit[0] < 12:
        # "明晚八点"：八点是晚上那个八点，不是早上八点
        time_hit = (time_hit[0] + 12, time_hit[1])
    if date_hit:
        if time_hit:
            hour, minute = time_hit
        elif hinted_hour is not None:
            hour, minute = hinted_hour, 0
        else:
            hour, minute = _default_hour(work), 0
        try:
            due = datetime.datetime(date_hit[0], date_hit[1], date_hit[2], hour, minute)
            if due < moment:      # "今天"说了个已经过去的点，顺到明天
                due += datetime.timedelta(days=1)
        except ValueError:
            due = None
    elif time_hit:
        hour, minute = time_hit
        due = moment.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if due < moment:
            due += datetime.timedelta(days=1)
    elif hinted_hour is not None:
        due = moment.replace(hour=hinted_hour, minute=0, second=0, microsecond=0)
        if due < moment:
            due += datetime.timedelta(days=1)
    else:
        # 只说了"下午"没说几点：按那一段的惯常时间给一个
        guess = _default_hour(work, fallback=None)
        due = None
        if guess is not None:
            due = moment.replace(hour=guess, minute=0, second=0, microsecond=0)
            if due < moment:
                due += datetime.timedelta(days=1)

    return {
        "title": _clean_title(work),
        "notes": "",
        "due_at": _fmt(due) if due else None,
        "remind_at": _fmt(due) if due else None,
        "repeat_rule": repeat,
        "priority": priority,
        "tags": tags,
        "matched_time": bool(due),
        "source": "local",
    }


def _clean_title(text):
    """把摘掉时间词之后剩下的残渣收拾干净。"""
    value = str(text or "")
    for word in NOISE:
        value = value.replace(word, " ")
    for pattern, _rule in REPEAT_PATTERNS:
        value = re.sub(pattern, " ", value)
    value = re.sub(PRIORITY_HIGH, " ", value)
    value = re.sub(PRIORITY_LOW, " ", value)
    value = _DAY_PERIOD.sub(" ", value)
    for pattern, _plus, _afternoon in PERIODS:
        value = re.sub(pattern, " ", value)
    value = re.sub(r"[\s　]+", " ", value).strip(" ，,、:：;；-—·")
    # 摘掉时间词之后可能剩下孤零零的"每""今"，看着像错字
    value = re.sub(r"每(?=\s|$)", " ", value)
    value = re.sub(r"今(?=\s|$)", " ", value)
    value = re.sub(r"[\s　]+", " ", value).strip(" ，,、:：;；-—·")
    return value.strip()


def next_occurrence(when, rule):
    """按重复规则推下一次时间，返回 datetime；规则不认识时返回 None。

    ``when`` 接受 'YYYY-MM-DDTHH:MM' 字符串或 datetime，格式化的活交给调用方，
    这样"算时间"和"显示时间"两件事不搅在一起。
    """
    if isinstance(when, datetime.datetime):
        base = when
    else:
        try:
            base = datetime.datetime.fromisoformat(str(when))
        except (TypeError, ValueError):
            return None
    if rule == "daily":
        return base + datetime.timedelta(days=1)
    if rule == "weekly":
        return base + datetime.timedelta(days=7)
    if rule == "monthly":
        year, month = base.year, base.month + 1
        if month > 12:
            year, month = year + 1, 1
        day = min(base.day, _days_in_month(year, month))
        return base.replace(year=year, month=month, day=day)
    if rule == "yearly":
        year = base.year + 1
        day = min(base.day, _days_in_month(year, base.month))
        return base.replace(year=year, day=day)
    return None


def _days_in_month(year, month):
    if month == 12:
        return 31
    return (datetime.date(year, month + 1, 1) - datetime.timedelta(days=1)).day
