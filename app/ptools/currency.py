"""汇率：抓一次缓存起来，六个小时内不再问网络。

数据源按 ``PROVIDERS`` 的顺序挨个试，谁先回得来用谁。全部失败时把每条
失败原因攒起来一起返回，界面上能看清到底卡在哪。
"""

import json
import math
import threading
import time

from . import httpclient as http
from . import network

REFRESH_AFTER = 6 * 60 * 60   # 六小时
MIN_RATES = 5                 # 少于这个数就当没抓到，防止半截数据污染缓存

# (代码, 名字, 符号)
CURRENCIES = [
    ("CNY", "人民币", "¥"),
    ("USD", "美元", "$"),
    ("EUR", "欧元", "€"),
    ("JPY", "日元", "¥"),
    ("GBP", "英镑", "£"),
    ("HKD", "港币", "HK$"),
    ("TWD", "新台币", "NT$"),
    ("MOP", "澳门元", "MOP$"),
    ("KRW", "韩元", "₩"),
    ("SGD", "新加坡元", "S$"),
    ("AUD", "澳元", "A$"),
    ("CAD", "加元", "C$"),
    ("CHF", "瑞士法郎", "CHF"),
    ("NZD", "新西兰元", "NZ$"),
    ("THB", "泰铢", "฿"),
    ("MYR", "马来西亚林吉特", "RM"),
    ("IDR", "印尼盾", "Rp"),
    ("PHP", "菲律宾比索", "₱"),
    ("VND", "越南盾", "₫"),
    ("INR", "印度卢比", "₹"),
    ("RUB", "卢布", "₽"),
    ("AED", "阿联酋迪拉姆", "د.إ"),
    ("SAR", "沙特里亚尔", "﷼"),
    ("TRY", "土耳其里拉", "₺"),
    ("BRL", "巴西雷亚尔", "R$"),
    ("MXN", "墨西哥比索", "MX$"),
    ("ZAR", "南非兰特", "R"),
    ("SEK", "瑞典克朗", "kr"),
    ("NOK", "挪威克朗", "kr"),
    ("DKK", "丹麦克朗", "kr"),
    ("PLN", "波兰兹罗提", "zł"),
    ("CZK", "捷克克朗", "Kč"),
]
CURRENCY_IDS = [code for code, _name, _symbol in CURRENCIES]
CURRENCY_NAMES = {code: name for code, name, _symbol in CURRENCIES}
CURRENCY_SYMBOLS = {code: symbol for code, _name, symbol in CURRENCIES}

BASE = "USD"
PROVIDERS = ("open.er-api.com", "jsdelivr", "exchangerate-api")


def _fetch_er_api(base=BASE):
    """open.er-api.com：免费、不用 key，一天一次。"""
    payload = http.get_json(f"https://open.er-api.com/v6/latest/{base}", timeout=8)
    if not isinstance(payload, dict):
        raise ValueError("返回的不是 JSON 对象")
    if payload.get("result") not in (None, "success"):
        raise ValueError(str(payload.get("error-type") or "接口返回失败"))
    rates = payload.get("rates")
    if not isinstance(rates, dict):
        raise ValueError("返回里没有 rates")
    return rates, payload.get("time_last_update_unix"), payload.get("provider")


def _fetch_jsdelivr(base=BASE):
    """jsDelivr 上的 currency-api：国内能通，按日期分文件。"""
    name = base.lower()
    payload = http.get_json(
        f"https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/{name}.json",
        timeout=8)
    if not isinstance(payload, dict):
        raise ValueError("返回的不是 JSON 对象")
    rates = payload.get(name)
    if not isinstance(rates, dict):
        raise ValueError("返回里没有汇率表")
    return {code.upper(): value for code, value in rates.items()}, None, payload.get("date")


def _fetch_exchangerate_api(base=BASE):
    """exchangerate-api 的 v4 免费端点。"""
    payload = http.get_json(f"https://api.exchangerate-api.com/v4/latest/{base}", timeout=8)
    if not isinstance(payload, dict):
        raise ValueError("返回的不是 JSON 对象")
    rates = payload.get("rates")
    if not isinstance(rates, dict):
        raise ValueError("返回里没有 rates")
    return rates, payload.get("time_last_updated"), "exchangerate-api"


FETCHERS = {
    "open.er-api.com": _fetch_er_api,
    "jsdelivr": _fetch_jsdelivr,
    "exchangerate-api": _fetch_exchangerate_api,
}


class Currency:
    """汇率缓存。``path`` 是缓存文件，``refresh`` 失败时旧数据不会丢。"""

    def __init__(self, path):
        self._path = path
        self._lock = threading.RLock()
        self._base = BASE
        self._rates = {}
        self._fetched_at = 0.0
        self._source = None
        self._provider_updated = None
        self._load()

    # ---------------- 缓存 ----------------

    def _load(self):
        try:
            raw = self._path.read_text(encoding="utf-8")
            data = json.loads(raw)
        except (OSError, AttributeError, ValueError):
            return
        if not isinstance(data, dict):
            return
        rates = data.get("rates")
        if isinstance(rates, dict):
            # 原样收着，坏值留给用的人自己发现，别在背后悄悄改数字
            self._rates = {str(code).upper(): value for code, value in rates.items()}
        try:
            self._fetched_at = float(data.get("fetched_at") or 0)
        except (TypeError, ValueError):
            self._fetched_at = 0.0
        self._base = str(data.get("base") or BASE)
        self._source = data.get("source")
        self._provider_updated = data.get("provider_updated")

    def _save_locked(self):
        payload = {
            "base": self._base,
            "rates": self._rates,
            "fetched_at": self._fetched_at,
            "source": self._source,
            "provider_updated": self._provider_updated,
        }
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps(payload, ensure_ascii=False, indent=1),
                                  encoding="utf-8")
        except OSError:
            pass

    # ---------------- 对外 ----------------

    def state(self):
        """给界面看的快照：币种表带汇率，另附缓存新鲜度。"""
        with self._lock:
            rates = dict(self._rates)
            fetched_at = self._fetched_at
            base = self._base
            source = self._source
            updated = self._provider_updated
        age = None
        if fetched_at:
            age = max(0, int(time.time() - fetched_at))
        currencies = []
        for code, name, symbol in CURRENCIES:
            if code in rates:
                currencies.append({"id": code, "name": name, "symbol": symbol,
                                   "rate": rates[code]})
        return {
            "base": base,
            "fetched_at": fetched_at,
            "age_seconds": age,
            "source": source,
            "provider_updated": updated,
            "currencies": currencies,
            "stale": age is None or age > REFRESH_AFTER,
            "has_rates": bool(rates),
        }

    def convert(self, amount, from_code, to_code):
        """换算，返回 ``(金额, 用的是哪次的汇率)``。"""
        with self._lock:
            rates = dict(self._rates)
            fetched_at = self._fetched_at
        source, target = str(from_code or "").upper(), str(to_code or "").upper()
        if source not in rates or target not in rates:
            raise ValueError("汇率数据里没有这个币种")
        value = (amount / rates[source]) * rates[target]
        return value, fetched_at

    def refresh(self, force=True):
        """挨个源试，第一个成功的写进缓存。全都失败就把原因带回去。"""
        with self._lock:
            if not force and not self.state()["stale"]:
                return dict(self.state())
        if not network.online():
            result = dict(self.state())
            result.update({"ok": False, "errors": [],
                           "error": f"{network.OFFLINE_HINT}（正在使用上次缓存的汇率）"})
            return result

        errors = []
        for provider in PROVIDERS:
            fetcher = FETCHERS.get(provider)
            if not fetcher:
                continue
            try:
                rates, source, updated = fetcher(BASE)
                clean = {}
                for code, value in (rates or {}).items():
                    try:
                        number = float(value)
                    except (TypeError, ValueError):
                        continue
                    if number > 0 and not math.isnan(number) and not math.isinf(number):
                        clean[str(code).upper()] = number
                if len(clean) < MIN_RATES:
                    raise ValueError(f"only {len(clean)} usable rates")
            except Exception as exc:
                errors.append({"provider": provider, "error": f"{type(exc).__name__}: {exc}"})
                continue
            with self._lock:
                self._rates = clean
                self._base = BASE
                self._fetched_at = time.time()
                self._source = source
                self._provider_updated = updated
                self._save_locked()
            result = dict(self.state())
            result.update({"ok": True, "errors": [], "updated_now": True})
            return result

        result = dict(self.state())
        detail = "；".join(f"{row['provider']}：{row['error']}" for row in errors)
        result.update({"ok": False, "errors": errors, "error": detail or "没有可用的汇率源"})
        return result

    def ensure_fresh(self):
        """打开换算页时调一次：新鲜就直接给缓存，过期才去抓。"""
        snapshot = self.state()
        if not snapshot["has_rates"] or snapshot["stale"]:
            return self.refresh(force=True)
        result = dict(snapshot)
        result.update({"ok": True, "cached": True, "updated_now": False})
        return result
