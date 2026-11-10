"""新旧 ptools 对照测试（oracle 对照）。

背景：`app/ptools` 原本是一批没有源码的 `.pyc`，1.0.0 用纯标准库重写成了 `.py`。
「重写」最容易犯的错是照着自己以为的行为写，而不是照着实际行为写。所以这里把旧
字节码的副本放在 `dev/_oracle/ptools_old/`，让新旧两套实现跑**完全相同的一串操作**，
把 id / 时间戳这类必然不同的字段抹掉后比对——返回值要比，落盘 JSON 也要比。

这个目录不进仓库（`.gitignore` 里有 `dev/_oracle/`），所以脚本找不到副本时会直接
跳过并返回 0。要复现，把旧版的 `ptools` 解出来放到 `dev/_oracle/ptools_old/` 即可。

    python dev/dev_ptools_diff.py

输出 PASS / FAIL 逐项，末尾给通过数。有 FAIL 时退出码为 1。
"""

import json
import shutil
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ORACLE = ROOT / "dev" / "_oracle"

sys.path.insert(0, str(ROOT / "app"))
sys.path.insert(0, str(ORACLE))

# 每次运行都不一样、比较时没有意义的字段
VOLATILE = {
    "id", "ts", "updated", "updatedAt", "at",
    "created_at", "completed_at", "remind_fired_at",
    "fetched_at", "age_seconds", "elapsed_ms", "token", "started_at",
}

CHECKS = []
SECTION = {"name": ""}


# ---------------------------------------------------------------- 比较工具

def section(name):
    SECTION["name"] = name
    print(f"\n=== {name} ===")


def check(name, ok, detail=""):
    CHECKS.append((SECTION["name"] + " / " + name, bool(ok), detail))
    print(("PASS  " if ok else "FAIL  ") + name + (f"  ({detail})" if detail else ""))


def strip(value):
    """递归抹掉易变字段与浮点误差，好拿来比较。"""
    if isinstance(value, dict):
        return {k: strip(v) for k, v in value.items() if k not in VOLATILE}
    if isinstance(value, (list, tuple)):
        return [strip(v) for v in value]
    if isinstance(value, float):
        return round(value, 9)
    return value


def same(name, left, right):
    a, b = strip(left), strip(right)
    ok = a == b
    detail = "" if ok else f"新={json.dumps(a, ensure_ascii=False)[:150]} 旧={json.dumps(b, ensure_ascii=False)[:150]}"
    check(name, ok, detail)
    return ok


def brief(value):
    """错误对象只比类型和文案，不整段塞进输出。"""
    return f"{type(value).__name__}: {value}"


def attempt(fn, *args, **kwargs):
    """跑一次，异常也当成一种可比较的返回值。"""
    try:
        return {"ok": strip(fn(*args, **kwargs))}
    except Exception as exc:  # noqa: BLE001
        return {"err": brief(exc)}


def load(name):
    return "ptools." + name


def load_old(name):
    return "ptools_old." + name


def mod(name):
    return __import__(load(name), fromlist=["*"])


def old(name):
    return __import__(load_old(name), fromlist=["*"])


def tmpdir():
    return Path(tempfile.mkdtemp(prefix="pt-diff-"))


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


# ---------------------------------------------------------------- 存储类

def diff_history():
    nstore, ostore = mod("store"), old("store")
    tmp = tmpdir()
    nf, of = tmp / "h-new.json", tmp / "h-old.json"
    nh, oh = nstore.History(nf), ostore.History(of)

    same("历史初始为空", nh.list(), oh.list())
    same("历史初始统计", nh.stats(), oh.stats())
    for i in range(5):
        same(f"新增历史 {i}",
             nh.add(f"原文 {i}", f"译文 {i}", "en", "zh-Hans", "bing", "微软必应"),
             oh.add(f"原文 {i}", f"译文 {i}", "en", "zh-Hans", "bing", "微软必应"))
    same("历史列表", nh.list(), oh.list())
    same("搜索命中", nh.list(query="原文 3"), oh.list(query="原文 3"))
    same("搜索无果", nh.list(query="不存在"), oh.list(query="不存在"))
    same("条数限制", nh.list(limit=2), oh.list(limit=2))

    ids_new = [x["id"] for x in nh.list()]
    ids_old = [x["id"] for x in oh.list()]
    same("收藏切换", nh.toggle_favorite(ids_new[0]), oh.toggle_favorite(ids_old[0]))
    same("只看收藏", nh.list(only_favorites=True), oh.list(only_favorites=True))
    same("收藏后统计", nh.stats(), oh.stats())
    same("删一条", nh.delete(ids_new[1]), oh.delete(ids_old[1]))
    same("删不存在的", nh.delete("nope"), oh.delete("nope"))
    same("删后列表", nh.list(), oh.list())

    nh.set_limit(20)
    oh.set_limit(20)
    same("下限钳到 20", nh.list(limit=999), oh.list(limit=999))
    same("清空保留收藏（返回剩余条数）", nh.clear(True), oh.clear(True))
    same("清空后列表", nh.list(), oh.list())
    same("历史落盘", read_json(nf), read_json(of))

    nf2, of2 = tmp / "t-new.json", tmp / "t-old.json"
    nh2, oh2 = nstore.History(nf2), ostore.History(of2)
    nh2.set_limit(20)
    oh2.set_limit(20)
    for i in range(30):
        nh2.add(f"t{i}", "r", "en", "zh", "bing", "Bing")
        oh2.add(f"t{i}", "r", "en", "zh", "bing", "Bing")
    same("超上限裁剪", nh2.list(limit=999), oh2.list(limit=999))

    nf3, of3 = tmp / "l-new.json", tmp / "l-old.json"
    nl, ol = nstore.LastRecord(nf3), ostore.LastRecord(of3)
    same("上次换算为空", nl.get(), ol.get())
    same("保存换算", nl.save({"category": "length", "value": "1"}), ol.save({"category": "length", "value": "1"}))
    same("读回换算", nl.get(), ol.get())
    same("清空换算", nl.clear(), ol.clear())
    same("清空后读取", nl.get(), ol.get())
    shutil.rmtree(tmp, ignore_errors=True)


def diff_notes():
    nnotes, onotes = mod("notes"), old("notes")
    tmp = tmpdir()
    nf, of = tmp / "n-new.json", tmp / "n-old.json"
    nn, on = nnotes.Notes(nf), onotes.Notes(of)

    same("空记事本", nn.list(), on.list())
    same("空白标题", nnotes.derive_title("   \n\n  "), onotes.derive_title("   \n\n  "))
    same("长标题截断", nnotes.derive_title("标题" * 60), onotes.derive_title("标题" * 60))
    same("新建笔记", nn.create("第一行\n第二行"), on.create("第一行\n第二行"))
    same("新建空笔记", nn.create(""), on.create(""))
    same("新建带标题", nn.create("正文", title="自定义"), on.create("正文", title="自定义"))
    same("笔记列表", nn.list(), on.list())
    same("笔记统计", nn.stats(), on.stats())

    ids_new = [x["id"] for x in nn.list()]
    ids_old = [x["id"] for x in on.list()]
    same("改内容", nn.update(ids_new[0], content="改过\n的内容"), on.update(ids_old[0], content="改过\n的内容"))
    # 只传 title 不传 content 时，旧实现会把标题按内容重算成「无标题」
    same("只改标题", nn.update(ids_new[1], title="只改标题"), on.update(ids_old[1], title="只改标题"))
    same("置顶", nn.toggle_pin(ids_new[2]), on.toggle_pin(ids_old[2]))
    same("置顶后排序", [x["title"] for x in nn.list()], [x["title"] for x in on.list()])
    same("取单条", nn.get(ids_new[0]), on.get(ids_old[0]))
    same("取不存在的", nn.get("nope"), on.get("nope"))
    same("搜索", nn.list(query="改过"), on.list(query="改过"))
    same("删除笔记", nn.delete(ids_new[0]), on.delete(ids_old[0]))
    same("删后统计", nn.stats(), on.stats())
    same("笔记落盘", read_json(nf), read_json(of))

    check("笔记常量一致",
          (nnotes.MAX_TITLE, nnotes.UNTITLED) == (onotes.MAX_TITLE, onotes.UNTITLED),
          f"{nnotes.MAX_TITLE} / {nnotes.UNTITLED}")
    shutil.rmtree(tmp, ignore_errors=True)


def diff_picker():
    npicker, opicker = mod("picker"), old("picker")
    tmp = tmpdir()
    nf, of = tmp / "p-new.json", tmp / "p-old.json"
    np_, op = npicker.Picker(nf), opicker.Picker(of)

    same("初始状态", np_.get(), op.get())
    same("初始统计", np_.stats(), op.stats())
    same("存选项",
         np_.save({"options": [" 甲 ", "", "乙", "甲"], "question": "选谁"}),
         op.save({"options": [" 甲 ", "", "乙", "甲"], "question": "选谁"}))
    same("抽一次", np_.record("甲"), op.record("甲"))
    same("再抽一次", np_.record("乙"), op.record("乙"))
    same("抽不存在的值", np_.record("丙"), op.record("丙"))
    same("状态", np_.get(), op.get())
    same("统计", np_.stats(), op.stats())
    same("清空历史（保留上次结果）", np_.clear_history(), op.clear_history())
    same("清空后状态", np_.get(), op.get())
    # 旧实现是整份替换而不是合并，传空对象会把选项清空
    same("整份替换", np_.save({"options": ["x" * 500, "y"]}), op.save({"options": ["x" * 500, "y"]}))
    same("选项落盘", read_json(nf), read_json(of))

    check("选择器常量一致",
          (npicker.MIN_OPTIONS, npicker.MAX_OPTIONS, npicker.MAX_OPTION_LEN, npicker.HISTORY_LIMIT)
          == (opicker.MIN_OPTIONS, opicker.MAX_OPTIONS, opicker.MAX_OPTION_LEN, opicker.HISTORY_LIMIT))
    shutil.rmtree(tmp, ignore_errors=True)


def diff_config():
    ncfg, ocfg = mod("config"), old("config")
    tmp = tmpdir()

    check("设置键白名单一致", sorted(ncfg.DEFAULT_SETTINGS) == sorted(ocfg.DEFAULT_SETTINGS),
          f"{len(ncfg.DEFAULT_SETTINGS)} 项")
    same("默认设置值", ncfg.DEFAULT_SETTINGS, ocfg.DEFAULT_SETTINGS)

    ns = ncfg.Settings(tmp / "s-new.json")
    os_ = ocfg.Settings(tmp / "s-old.json")
    same("初始设置", ns.all(), os_.all())
    same("读单键", ns.get("theme"), os_.get("theme"))
    same("读不存在的键", ns.get("nope", "fallback"), os_.get("nope", "fallback"))

    same("写入已知键", ns.update({"theme": "dark"}), os_.update({"theme": "dark"}))
    same("写入未知键（应被丢弃）", ns.update({"nope": 1}), os_.update({"nope": 1}))
    same("类型不符（应被丢弃）", ns.update({"window_width": "宽"}), os_.update({"window_width": "宽"}))
    same("写后全量", ns.all(), os_.all())
    same("设置落盘", read_json(tmp / "s-new.json"), read_json(tmp / "s-old.json"))
    same("重置", ns.reset(), os_.reset())
    same("重置后", ns.all(), os_.all())
    shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------- 计算类

def diff_units():
    nunits, ounits = mod("units"), old("units")

    check("单位目录一致",
          strip(nunits.catalogue()) == strip(ounits.catalogue()),
          f"{len(nunits.CATEGORIES)} 类")

    import random
    random.seed(20261110)
    samples = [0, 1, -1, 0.1, 1e-7, 1e16, 1e17, 123456789, 0.000001, 999999.999999,
               2.5, -0.0, 1 / 3, 1e-6, 1e15, 6.02e23]
    samples += [random.uniform(-1e9, 1e9) for _ in range(400)]
    samples += [random.uniform(-1, 1) for _ in range(200)]
    bad = [v for v in samples if nunits.format_number(v) != ounits.format_number(v)]
    check(f"数字格式化（{len(samples)} 个样本）", not bad,
          f"{len(bad)} 处不同，如 {bad[:3]}")

    pairs = []
    for cat in ounits.CATEGORIES:
        units = list(cat.get("units") or {})
        for i, u in enumerate(units):
            for v in units[i + 1:]:
                pairs.append((1, cat["id"], u, v))
                pairs.append((100, cat["id"], v, u))
    diffs = []
    for args in pairs:
        a, b = attempt(nunits.convert, *args), attempt(ounits.convert, *args)
        if a != b:
            diffs.append((args, a, b))
    check(f"单位换算（{len(pairs)} 组）", not diffs, f"{len(diffs)} 处不同，如 {diffs[:1]}")


def diff_languages():
    nlang, olang = mod("languages"), old("languages")

    check("语言表一致", strip(nlang.LANGUAGES) == strip(olang.LANGUAGES),
          f"{len(nlang.LANGUAGES)} 种")

    providers = sorted(nlang.PROVIDER_FIELDS)
    codes = ["", "auto", "zh", "zh-Hans", "zh-Hant", "zh-CN", "zh-TW", "en", "en-US",
             "en-GB", "ja", "ja-JP", "ko", "fr", "de", "es", "ru", "ar", "he",
             "sr", "sr-Cyrl", "sr-Latn", "pt-BR", "bogus", "xx", "nb", "iw", "tlh"]
    codes += [row[0] for row in nlang.LANGUAGES]
    codes = list(dict.fromkeys(codes))

    diffs = []
    for provider in providers:
        for code in codes:
            a = attempt(nlang.normalize, provider, code)
            b = attempt(olang.normalize, provider, code)
            if a != b:
                diffs.append((provider, code, a, b))
    check(f"语言码归一（{len(providers)} 渠道 × {len(codes)} 码）", not diffs,
          f"{len(diffs)} 处不同，如 {diffs[:2]}")

    diffs = []
    for code in codes:
        for fn_name in ("code_for", "name_of", "get"):
            for provider in (None,) + tuple(providers):
                args = (code, provider) if fn_name == "code_for" else (code,)
                a = attempt(getattr(nlang, fn_name), *args)
                b = attempt(getattr(olang, fn_name), *args)
                if a != b:
                    diffs.append((fn_name, args, a, b))
    check("语言辅助函数", not diffs, f"{len(diffs)} 处不同，如 {diffs[:2]}")


# 旧实现在这几条上的结果是错的（时段词被算错、标题残留时间碎片、跨年日期不跨年），
# 新版按正确语义实现，因此不再拿旧版当标准，而是把新版的期望值钉在这里。
# 键是用例，值是（due_at, title）；matched_time 由 due_at 是否存在推出来，一并校验。
NLPTIME_FIXED = {
    "今晚八点吃饭": ("2026-11-10T20:00", "吃饭"),
    "后天中午12:30": ("2026-11-12T12:30", ""),
    "明早七点跑步": ("2026-11-11T07:00", "跑步"),
    "明晚八点看电影": ("2026-11-11T20:00", "看电影"),
    "今晚": ("2026-11-10T20:00", ""),
    "明晚": ("2026-11-11T20:00", ""),
    "明早": ("2026-11-11T08:00", ""),
    "今早": ("2026-11-11T08:00", ""),
    "明早八点": ("2026-11-11T08:00", ""),
    "后晚九点": ("2026-11-12T21:00", ""),
    "下午3:30": ("2026-11-10T15:30", ""),
    "晚上8:00": ("2026-11-10T20:00", ""),
    "明天 下午16:00": ("2026-11-11T16:00", ""),
    "零点": ("2026-11-11T00:00", ""),
}

NLPTIME_CASES = [
    "明天下午三点开会", "今天18:00下班", "明天早上", "今晚八点吃饭",
    "每周一开会", "12月25日圣诞", "下周三交报告", "3天后复查",
    "每月1号交房租", "后天中午12:30", "十点半提醒我", "周五下午两点半",
    "明早七点跑步", "下个月5号交材料", "每天早上八点吃药",
    "下午三点", "晚上", "今天", "明天", "后天", "大后天",
    "凌晨两点睡觉", "中午", "傍晚六点", "周末买菜",
    "2026-12-01 体检", "12/25 聚会", "每天晚上十点写日记",
    "周三", "周一", "本周五", "下周一",
    "明天上午10点30分", "周五下班前", "明晚八点看电影",
    "1小时后", "30分钟后", "3天后", "一周后",
    "今天下午", "明天下午四点", "下下周一",
    "生日12月3日", "12月底对账", "每月15号发工资",
    "早上", "晚上八点", "深夜一点",
    # 以下为额外覆盖：时段单独出现、复合时段词、冒号时间
    "今晚", "明晚", "明早", "今早", "今晚21:00", "明早八点", "后晚九点",
    "下午3:30", "晚上8:00", "3:30", "明天 下午16:00",
    "今天16:00", "今天15:30", "今天15:31", "09:00", "08:00",
    "", "   ", "开会", "#工作 明天开会", "明天开会 #工作 #生活",
    "紧急 明天交报告", "不急", "尽快", "每天", "每周", "每月", "每年",
    "工作日", "每个工作日", "星期一", "礼拜一", "周天", "周末", "下周末",
    "12月25号", "12/25", "12-25", "1月1日", "每月15日", "这个月15号",
    "25:00", "24:00", "0:30", "零点", "二十四点", "下午十三点", "晚上十二点",
]


def diff_nlptime():
    nlp, onlp = mod("nlptime"), old("nlptime")
    now = datetime(2026, 11, 10, 15, 30)

    diffs, fixed = [], 0
    for case in NLPTIME_CASES:
        a, b = attempt(nlp.parse, case, now=now), attempt(onlp.parse, case, now=now)
        if case in NLPTIME_FIXED:
            fixed += 1
            want_due, want_title = NLPTIME_FIXED[case]
            got = a.get("ok") or {}
            got_triple = (got.get("due_at"), got.get("title"), got.get("matched_time"))
            if got_triple != (want_due, want_title, bool(want_due)):
                check(f"修正 {case!r}", False, f"新={got_triple} 期望={(want_due, want_title, bool(want_due))}")
        elif a != b:
            diffs.append((case, a, b))
    check(f"解析结果（{len(NLPTIME_CASES)} 条，另 {fixed} 条钉住旧 bug）", not diffs,
          f"{len(diffs)} 处不同，如 {diffs[:1]}")

    # 同一时刻的 next_occurrence 也要一致
    base = datetime(2026, 11, 10, 10, 0)
    diffs = []
    for rule in ("none", "daily", "weekly", "monthly", "yearly", ""):
        for seed in (base, datetime(2026, 1, 31, 10, 0), datetime(2024, 2, 29, 10, 0)):
            a = attempt(nlp.next_occurrence, seed, rule)
            b = attempt(onlp.next_occurrence, seed, rule)
            if a != b:
                diffs.append((rule, seed.isoformat(), a, b))
    check("下一次重复时间", not diffs, f"{len(diffs)} 处不同，如 {diffs[:1]}")

    # 组合与随机串只验「不抛异常、结构完整」，不比对旧版（旧版在这类输入上会崩）
    import itertools
    import random
    heads = ["", "今天", "明天", "后天", "今晚", "明晚", "下周三", "12月25日",
             "每月5号", "3天后", "1小时后", "每天", "每周一"]
    bells = ["", "早上八点", "下午三点", "晚上八点", "8:30", "十点半", "中午", "凌晨两点"]
    tails = ["", "开会", "买菜做饭", " 15:00", " #工作", " 备注:带材料"]
    keys = {"title", "notes", "due_at", "remind_at", "repeat_rule", "priority",
            "tags", "matched_time", "source"}
    broken = []
    count = 0
    for parts in itertools.product(heads, bells, tails):
        text = "".join(parts).strip()
        if not text:
            continue
        count += 1
        try:
            got = nlp.parse(text, now=now)
            if set(got) != keys:
                broken.append((text, "键不符"))
            elif got["due_at"]:
                datetime.strptime(got["due_at"], "%Y-%m-%dT%H:%M")
        except Exception as exc:  # noqa: BLE001
            broken.append((text, brief(exc)))
    check(f"组合输入不崩（{count} 条）", not broken, f"{len(broken)} 处异常，如 {broken[:2]}")

    random.seed(7)
    pool = "今天明天后天今晚明早晚下周上午下午晚上点分半一刻月日号每年个小时后8:3012:00开会买菜写周报紧急重要不急随便#工作"
    broken = []
    for _ in range(2000):
        text = "".join(random.choice(pool) for _ in range(random.randint(1, 12)))
        try:
            nlp.parse(text, now=now)
        except Exception as exc:  # noqa: BLE001
            broken.append((text, brief(exc)))
            break
    check("随机输入不崩（2000 条）", not broken, f"{broken[:1]}")


# ---------------------------------------------------------------- 业务类

class _FakeClock(datetime):
    """把模块里的 datetime 换成冻结在当前时刻的版本。"""

    frozen = datetime(2026, 11, 10, 9, 0, 0)

    @classmethod
    def now(cls, tz=None):
        return cls.frozen


def diff_todo():
    ntodo, otodo = mod("todo"), old("todo")
    ntodo.datetime = _FakeClock
    otodo.datetime = _FakeClock

    def run(module):
        tmp = tmpdir()
        todo = module.Todo(tmp / "todo.json")
        log = []
        ids = {}

        def rec(tag, value):
            log.append((tag, strip(value)))

        def add(key, payload):
            result = todo.create(dict(payload))
            ids[key] = result["id"]
            rec("create:" + str(payload.get("title")), result)

        add("A", {"title": "A 过期", "due_at": "2026-11-09T10:00", "priority": "high", "tags": ["工作", "急"]})
        add("B", {"title": "B 今早", "due_at": "2026-11-10T07:00", "priority": "low", "tags": ["工作"]})
        add("C", {"title": "C 今晚", "due_at": "2026-11-10T20:00"})
        add("D", {"title": "D 明天", "due_at": "2026-11-11T10:00", "priority": "high"})
        add("E", {"title": "E 无时间"})
        add("F", {"title": ""})
        add("G", {"title": "G 重复", "due_at": "2026-11-10T10:00", "repeat_rule": "weekly",
                  "priority": "high", "tags": ["t1"], "notes": "记"})
        add("H", {"title": "H 提醒", "due_at": "2026-11-10T12:00", "remind_at": "2026-11-10T08:00"})
        add("I", {"title": "I 非法", "due_at": "bad", "priority": "bogus", "status": "bogus", "tags": None})
        add("J", {"title": "J 标签串", "tags": "单"})

        for view in ("today", "all", "done", "upcoming", "overdue", "week", "tomorrow", "", None):
            rec(f"list:{view}", todo.list(view))
        rec("list:tag", todo.list("all", tag="工作"))
        rec("list:priority", todo.list("all", priority="high"))
        rec("list:query", todo.list("all", query="今晚"))
        rec("stats", todo.stats())

        rec("complete:B", list(todo.complete(ids["B"])))
        rec("complete:G", list(todo.complete(ids["G"])))
        rec("reopen:B", todo.reopen(ids["B"]))
        rec("cancel:D", todo.cancel(ids["D"]))
        rec("postpone:C", todo.postpone(ids["C"], days=2))
        rec("postpone:E", todo.postpone(ids["E"], days=1))
        rec("postpone:H", todo.postpone(ids["H"], days=0, minutes=30))

        rec("update:title", todo.update(ids["A"], {"title": "A2"}))
        rec("update:blank", todo.update(ids["A"], {"title": "  "}))
        rec("update:priority", todo.update(ids["A"], {"priority": "bogus"}))
        rec("update:due", todo.update(ids["A"], {"due_at": ""}))
        rec("update:tags", todo.update(ids["A"], {"tags": "x"}))
        rec("update:repeat", todo.update(ids["A"], {"repeat_rule": "monthly"}))
        rec("update:missing", todo.update("nope", {"title": "x"}))
        rec("get:A", todo.get(ids["A"]))
        rec("get:missing", todo.get("nope"))
        rec("complete:missing", list(todo.complete("nope")))
        rec("delete:missing", todo.delete("nope"))

        rec("pending", todo.pending_reminders())
        rec("pop", todo.pop_due_notifications())
        rec("pop2", todo.pop_due_notifications())
        rec("mark:H", todo.mark_reminded(ids["H"]))
        rec("pending2", todo.pending_reminders())
        rec("mark:missing", todo.mark_reminded("nope"))

        rec("delete_many", todo.delete_many([ids["J"], "nope"]))
        rec("delete_many:empty", todo.delete_many([]))
        rec("clear_done", todo.clear_done())
        rec("list:after", todo.list("all"))

        exported = todo.export()
        rec("export", json.loads(exported))
        other = module.Todo(tmpdir() / "t.json")
        rec("import:empty", other.import_data(exported))
        rec("import:merge", other.import_data(exported))
        rec("import:replace", other.import_data(exported, merge=False))
        rec("import:after", other.list("all"))
        rec("import:broken", attempt(other.import_data, "not json"))
        rec("disk", read_json(tmp / "todo.json"))
        shutil.rmtree(tmp, ignore_errors=True)
        return log

    left, right = run(ntodo), run(otodo)
    if len(left) != len(right):
        check("步骤数一致", False, f"新 {len(left)} 步 / 旧 {len(right)} 步")
        return
    bad = []
    for (tag_a, val_a), (tag_b, val_b) in zip(left, right):
        if tag_a != tag_b or json.dumps(val_a, ensure_ascii=False, sort_keys=True) != \
                json.dumps(val_b, ensure_ascii=False, sort_keys=True):
            bad.append(tag_a)
    check(f"待办全流程（{len(left)} 步）", not bad, f"{len(bad)} 步不同：{bad[:6]}")


class _FakeNet:
    ok = True
    OFFLINE_HINT = "离线了"

    @staticmethod
    def online(force=False):
        return _FakeNet.ok

    @staticmethod
    def snapshot():
        return {"online": _FakeNet.ok}


def diff_currency():
    ncur, ocur = mod("currency"), old("currency")
    ncur.network = _FakeNet
    ocur.network = _FakeNet
    _FakeNet.ok = True

    rates = {"USD": 1, "CNY": 7.1, "EUR": 0.9, "JPY": 150, "GBP": 0.8}

    def conv(currency, *args):
        value, stamp = currency.convert(*args)
        return [round(value, 9), bool(stamp)]

    def run(module):
        tmp = tmpdir()
        path = tmp / "cur.json"
        currency = module.Currency(path)
        log = []

        def rec(tag, value):
            log.append((tag, strip(value)))

        rec("state:empty", currency.state())
        rec("convert:empty", attempt(currency.convert, 100, "USD", "CNY"))

        path.write_text(json.dumps({"base": "USD", "rates": dict(rates),
                                    "fetched_at": time.time() - 100, "source": "seed",
                                    "provider_updated": 1794300000}), encoding="utf-8")
        currency = module.Currency(path)
        rec("state:seeded", currency.state())
        for tag, args in (("usd-cny", (100, "USD", "CNY")), ("cny-usd", (100, "CNY", "USD")),
                          ("jpy-cny", (1, "JPY", "CNY")), ("zero", (0, "USD", "CNY")),
                          ("negative", (-5, "USD", "CNY")), ("big", (1e9, "USD", "JPY"))):
            rec("convert:" + tag, conv(currency, *args))
        for bad_pair in (("XXX", "CNY"), ("USD", "XXX")):
            rec(f"convert:{bad_pair}", attempt(currency.convert, 1, *bad_pair))
        rec("ensure:cached", currency.ensure_fresh())

        module.FETCHERS = {k: (lambda base="USD": (dict(rates, KRW=1350), 1794300000, "标注"))
                           for k in module.PROVIDERS}
        rec("refresh:ok", currency.refresh(force=True))
        rec("disk", read_json(path))

        for n in (2, 3, 4, 5):
            subset = dict(list(rates.items())[:n])
            module.FETCHERS = {k: (lambda base="USD", s=subset: (dict(s), 1, 2))
                               for k in module.PROVIDERS}
            rec(f"refresh:{n}rates", currency.refresh(force=True).get("ok"))

        def boom(base="USD"):
            raise RuntimeError("网络挂了")

        module.FETCHERS = {k: boom for k in module.PROVIDERS}
        rec("refresh:fail", {k: v for k, v in currency.refresh(force=True).items()
                             if k in ("ok", "error", "errors")})

        _FakeNet.ok = False
        rec("refresh:offline", {k: v for k, v in currency.refresh(force=True).items()
                                if k in ("ok", "error")})
        _FakeNet.ok = True

        for bad_text in ("not json", "{}", '{"rates": "x"}', '{"rates": {"USD": "abc", "CNY": -1}}'):
            broken = tmp / "bad.json"
            broken.write_text(bad_text, encoding="utf-8")
            rec("bad:" + bad_text[:16], module.Currency(broken).state())
        shutil.rmtree(tmp, ignore_errors=True)
        return log

    left, right = run(ncur), run(ocur)
    bad = []
    for (tag_a, val_a), (tag_b, val_b) in zip(left, right):
        if tag_a != tag_b or json.dumps(val_a, ensure_ascii=False, sort_keys=True) != \
                json.dumps(val_b, ensure_ascii=False, sort_keys=True):
            bad.append(tag_a)
    check(f"汇率全流程（{len(left)} 步）", not bad, f"{len(bad)} 步不同：{bad[:6]}")


def diff_aihint():
    nai, oai = mod("aihint"), old("aihint")
    now = datetime(2026, 11, 10, 9, 0)

    class Settings(dict):
        def get(self, key, default=None):
            return dict.get(self, key, default)

    settings = Settings({"ai_base_url": "https://x/v1/", "ai_api_key": "sek", "ai_model": "m1"})

    def content(text):
        return json.dumps({"choices": [{"message": {"content": text}}]})

    cases = {
        "正常": content('{"title":"开会","notes":"带材料","due_at":"2026-11-11T15:00",'
                       '"remind_at":null,"repeat_rule":"weekly","priority":"high","tags":["工作"]}'),
        "只有标题": content('{"title":"开会"}'),
        "围栏": content('```json\n{"title":"开会","priority":"low"}\n```'),
        "前后有客套话": content('好的：{"title":"开会","priority":"high","tags":"a,b"} 希望有用'),
        "非法枚举": content('{"title":"x","priority":"bogus","repeat_rule":"monthly ",'
                          '"due_at":"bad","tags":null}'),
        "空内容": content(""),
        "非 JSON 内容": content("抱歉我不知道"),
        "顶层数组": json.dumps([{"title": "x"}]),
        "空 choices": json.dumps({"choices": []}),
        "error 对象": json.dumps({"error": {"message": "额度用完了"}}),
        "error 字符串": json.dumps({"error": "no key"}),
        "响应不是 JSON": "not json at all",
        "HTTP 异常": RuntimeError("连接被重置"),
    }

    def probe(module, responder):
        captured = {}

        class Http:
            @staticmethod
            def request(*args, **kwargs):
                captured["url"] = args[0] if args else kwargs.get("url")
                captured["kwargs"] = kwargs
                if isinstance(responder, Exception):
                    raise responder
                return responder

        module.http = Http
        out = attempt(module.parse, "明天三点开会", settings, now=now)
        body = None
        data = (captured.get("kwargs") or {}).get("data")
        if isinstance(data, (bytes, bytearray)):
            try:
                body = json.loads(data.decode("utf-8"))
            except ValueError:
                body = None
        request = None
        if body:
            request = {"keys": sorted(body), "model": body.get("model"),
                       "temperature": body.get("temperature"),
                       "messages": body.get("messages")}
        return {"result": out, "request": request}

    diffs = []
    for name, responder in cases.items():
        left, right = probe(nai, responder), probe(oai, responder)
        if strip(left) != strip(right):
            diffs.append((name, left, right))
    check(f"AI 识别（{len(cases)} 例）", not diffs, f"{len(diffs)} 处不同，如 {diffs[:1]}")

    blanks = [Settings(), Settings({"ai_api_key": "k"}), Settings({"ai_base_url": "u"}),
              Settings({"ai_base_url": "u", "ai_api_key": "k"})]
    diffs = [(cfg, nai.configured(cfg), oai.configured(cfg)) for cfg in blanks
             if nai.configured(cfg) != oai.configured(cfg)]
    check("配置判定", not diffs, f"{diffs[:2]}")


def diff_server():
    nserver, oserver = mod("server"), old("server")

    class FakeApi:
        def ping(self):
            return {"ok": True}

        def echo(self, *args, **kwargs):
            return {"ok": True, "args": list(args), "kwargs": kwargs}

        def boom(self):
            raise RuntimeError("炸了")

        def plain(self):
            return "纯字符串"

        def nothing(self):
            return None

        def _hidden(self):
            return {"ok": True}

    def run(module):
        web = tmpdir()
        (web / "index.html").write_text("<html><head></head><body>x</body></html>", encoding="utf-8")
        (web / "app.js").write_text("console.log(1)", encoding="utf-8")
        (web / "style.css").write_text("body{}", encoding="utf-8")
        covers = tmpdir()
        (covers / "a.jpg").write_bytes(b"\xff\xd8\xff")

        server = module.ApiServer(FakeApi(), web, cover_root=covers).start()
        base = server.url.rstrip("/")
        token = server.token
        log = []

        def call(tag, path, payload=None, headers=None, raw=None, method="POST"):
            merged = {"Content-Type": "application/json"}
            if token:
                merged["X-Token"] = token
            merged.update(headers or {})
            body = raw if raw is not None else (
                json.dumps(payload).encode() if payload is not None else b"")
            request = urllib.request.Request(
                base + path, data=(body if method == "POST" else None),
                headers=merged, method=method)
            try:
                with urllib.request.urlopen(request, timeout=5) as response:
                    log.append((tag, response.status,
                                response.read()[:300].decode("utf-8", "replace"),
                                response.headers.get("Content-Type")))
            except urllib.error.HTTPError as exc:
                log.append((tag, exc.code, exc.read()[:300].decode("utf-8", "replace"),
                            exc.headers.get("Content-Type")))
            except Exception as exc:  # noqa: BLE001
                log.append((tag, "EXC", brief(exc), ""))

        call("ping", "/api/ping", {"args": []})
        call("echo", "/api/echo", {"args": [1, "a"]})
        call("echo-list-body", "/api/echo", [1, 2])
        call("boom", "/api/boom", {"args": []})
        call("plain", "/api/plain", {"args": []})
        call("nothing", "/api/nothing", {"args": []})
        call("unknown", "/api/nope", {"args": []})
        call("underscore", "/api/_hidden", {"args": []})
        call("bad-json", "/api/ping", raw=b"{bad")
        call("empty-body", "/api/ping", raw=b"")
        call("no-token", "/api/ping", {"args": []}, {"X-Token": ""})
        call("wrong-token", "/api/ping", {"args": []}, {"X-Token": "abc"})
        call("get-api", "/api/ping", method="GET")
        call("index", "/", method="GET")
        call("index-html", "/index.html", method="GET")
        call("js", "/app.js", method="GET")
        call("css", "/style.css", method="GET")
        call("missing", "/nope.txt", method="GET")
        call("traversal", "/../app.py", method="GET")
        call("cover", "/covers/a.jpg", method="GET")
        call("cover-missing", "/covers/b.jpg", method="GET")
        call("root-post", "/", {"args": []})
        server.stop()
        shutil.rmtree(web, ignore_errors=True)
        shutil.rmtree(covers, ignore_errors=True)
        return log

    left, right = run(nserver), run(oserver)
    import re

    # 旧版收到非对象的请求体时，do_POST 会在发响应之前抛异常，连接被直接掐断。
    # 前端只会发 {"args": [...]}，走不到这条路；新版按"没有参数"处理并正常回包。
    # 这一条不拿旧版当标准，单独钉住新版行为。
    EXPECTED = {
        "echo-list-body": (200, '{"ok": true, "args": [], "kwargs": {}}'),
    }

    bad = []
    for (tag_a, status_a, body_a, type_a), (tag_b, status_b, body_b, type_b) in zip(left, right):
        # 页面里注入的 token 每次都不同
        body_a = re.sub(r'__TOKEN__="[^"]*"', '__TOKEN__="T"', body_a)
        body_b = re.sub(r'__TOKEN__="[^"]*"', '__TOKEN__="T"', body_b)
        if tag_a in EXPECTED:
            want_status, want_body = EXPECTED[tag_a]
            if (status_a, body_a) != (want_status, want_body):
                bad.append((tag_a + "（新版行为）", (status_a, body_a[:80]), (want_status, want_body[:80])))
            continue
        if (tag_a, status_a, body_a, type_a) != (tag_b, status_b, body_b, type_b):
            bad.append((tag_a, (status_a, body_a[:80]), (status_b, body_b[:80])))
    check(f"本地服务路由（{len(left)} 例）", not bad, f"{len(bad)} 例不同，如 {bad[:2]}")


def diff_api():
    def build(pkg):
        config = __import__(pkg + ".config", fromlist=["*"])
        api_mod = __import__(pkg + ".api", fromlist=["*"])
        store = __import__(pkg + ".store", fromlist=["*"])
        notes = __import__(pkg + ".notes", fromlist=["*"])
        picker = __import__(pkg + ".picker", fromlist=["*"])
        currency = __import__(pkg + ".currency", fromlist=["*"])
        todo = __import__(pkg + ".todo", fromlist=["*"])
        root = tmpdir()
        return api_mod.Api(
            config.Settings(root / "s.json"), store.History(root / "h.json", 300),
            notes=notes.Notes(root / "n.json"), picker=picker.Picker(root / "p.json"),
            currency=currency.Currency(root / "c.json"), convert_store=None, media=None,
            todo=todo.Todo(root / "t.json"), startup={"moved": [], "removed": False})

    def keys(value):
        return sorted(value) if isinstance(value, dict) else type(value).__name__

    def run(api):
        log = []

        def rec(tag, value):
            log.append((tag, strip(value)))

        rec("ping", api.ping())
        rec("net_state", keys(api.net_state()))
        rec("save_settings", keys(api.save_settings({"theme": "dark"})))
        rec("reset_settings", keys(api.reset_settings()))
        rec("clipboard_read", keys(api.clipboard_read()))
        rec("clipboard_write", keys(api.clipboard_write("hi")))

        note = api.notes_create("内容")["item"]
        rec("notes_list", keys(api.notes_list()))
        rec("notes_update", keys(api.notes_update(note["id"], "改")))
        rec("notes_pin", keys(api.notes_pin(note["id"])))
        rec("notes_delete", keys(api.notes_delete(note["id"])))
        rec("notes_update_missing", keys(api.notes_update("nope", "x")))

        rec("save_conversion", keys(api.save_conversion({"text": "a", "result": "b"})))
        rec("history_list", keys(api.history_list()))
        rec("history_toggle_missing", keys(api.history_toggle("nope")))
        rec("history_clear", keys(api.history_clear()))

        rec("picker_load", keys(api.picker_load()))
        rec("picker_save", keys(api.picker_save({"options": ["a", "b"]})))
        rec("picker_record", keys(api.picker_record("a")))
        rec("picker_clear", keys(api.picker_clear_history()))

        rec("currency_ensure_keys", keys(api.currency_ensure()))

        item = api.todo_create({"title": "T"})["item"]
        rec("todo_list", keys(api.todo_list("today")))
        rec("todo_parse", keys(api.todo_parse("明天三点开会")))
        rec("todo_parse_draft", keys(api.todo_parse("明天三点开会")["draft"]))
        rec("todo_update", keys(api.todo_update(item["id"], {"title": "T2"})))
        rec("todo_complete", keys(api.todo_complete(item["id"])))
        rec("todo_reopen", keys(api.todo_reopen(item["id"])))
        rec("todo_postpone", keys(api.todo_postpone(item["id"], 1)))
        rec("todo_delete", keys(api.todo_delete(item["id"])))
        rec("todo_delete_many", keys(api.todo_delete_many([])))
        rec("todo_clear_done", keys(api.todo_clear_done()))
        rec("todo_update_missing", keys(api.todo_update("nope", {})))

        rec("detect_language", keys(api.detect_language("hello")))
        rec("media_list", keys(api.media_list()))
        rec("media_ready", api.media_ready())
        rec("window_control", keys(api.window_control("x")))
        rec("speak", keys(api.speak("hi", "en")))
        return log

    left, right = run(build("ptools")), run(build("ptools_old"))
    bad = []
    for (tag_a, val_a), (tag_b, val_b) in zip(left, right):
        if tag_a != tag_b or json.dumps(val_a, ensure_ascii=False, sort_keys=True) != \
                json.dumps(val_b, ensure_ascii=False, sort_keys=True):
            bad.append((tag_a, val_a, val_b))
    check(f"Api 方法（{len(left)} 项）", not bad, f"{len(bad)} 项不同，如 {bad[:2]}")


# ---------------------------------------------------------------- 入口

SECTIONS = [
    ("历史记录 / 上次换算", diff_history),
    ("记事本", diff_notes),
    ("随机选择", diff_picker),
    ("设置", diff_config),
    ("单位换算", diff_units),
    ("语言表", diff_languages),
    ("自然语言时间", diff_nlptime),
    ("待办", diff_todo),
    ("汇率", diff_currency),
    ("AI 识别", diff_aihint),
    ("本地服务", diff_server),
    ("Api 组装", diff_api),
]


def main():
    if not (ORACLE / "ptools_old").is_dir():
        print(f"跳过：没有找到旧实现副本 {ORACLE / 'ptools_old'}")
        print("这个目录不进仓库，只在本机做对照测试时用。参见本文件开头的说明。")
        return 0

    for name, runner in SECTIONS:
        section(name)
        try:
            runner()
        except Exception as exc:  # noqa: BLE001
            import traceback

            traceback.print_exc()
            check(name + " 未跑完", False, brief(exc))

    failed = [c for c in CHECKS if not c[1]]
    print(f"\n{len(CHECKS) - len(failed)}/{len(CHECKS)} 通过")
    for name, _, detail in failed:
        print("  FAIL " + name + (f"  ({detail})" if detail else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
