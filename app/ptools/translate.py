"""翻译：几个免密钥的公共接口轮着用，谁通用谁。

长文本先按段落和句号切成小块并发去翻，再拼回来——单次请求太长会被
对方截断，拼出来就是半截话。
"""

import json
import re
import threading
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

from . import httpclient as http
from . import network

BING_CHUNK = 900
YOUDAO_CHUNK = 900
MYMEMORY_CHUNK = 460
GOOGLE_CHUNK = 1800

PROVIDER_ORDER = ("bing", "youdao", "mymemory", "google")
PROVIDER_LABELS = {
    "bing": "微软必应",
    "youdao": "网易有道",
    "mymemory": "MyMemory",
    "google": "Google",
}

# 朗读用的音色，认不出来的语种一律按英语念
TTS_VOICE = {
    "en": "en", "zh-Hans": "zh", "zh-Hant": "zh", "ja": "ja", "ko": "ko",
    "fr": "fr", "de": "de", "es": "es", "ru": "ru", "pt": "pt", "it": "it",
}

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

_SENTENCE_END = re.compile(r"([。！？；!?;\n])")
_IG = re.compile(r'params_AbusePreventionHelper\s*=\s*\[\s*(\d+)\s*,\s*"([^"]+)"')


class TranslateError(Exception):
    """这条路没走通，消息里写清是哪一家、卡在哪。"""


# ---------------- 文本切分 ----------------

def split_chunks(text, limit):
    """按句子边界切开，每块尽量接近但不超过 ``limit`` 个字符。"""
    raw = str(text or "")
    if not raw:
        return [""]
    if len(raw) <= limit:
        return [raw]

    pieces = []
    buffer = ""
    for part in _SENTENCE_END.split(raw):
        if not part:
            continue
        if len(part) > limit:
            if buffer:
                pieces.append(buffer)
                buffer = ""
            for start in range(0, len(part), limit):
                pieces.append(part[start:start + limit])
            continue
        if len(buffer) + len(part) > limit:
            pieces.append(buffer)
            buffer = part
        else:
            buffer += part
    if buffer:
        pieces.append(buffer)
    return pieces or [raw]


def run_chunks(func, chunks, workers=3):
    """多块并发翻，返回的顺序跟传进来的一致。"""
    items = list(chunks)
    if len(items) <= 1 or workers <= 1:
        return [func(chunk) for chunk in items]
    with ThreadPoolExecutor(max_workers=min(workers, len(items))) as pool:
        return list(pool.map(func, items))


def tts_url(text, lang):
    """朗读走有道的发音接口，够用且不用 key。"""
    voice = TTS_VOICE.get(str(lang or ""), "en")
    return ("https://dict.youdao.com/dictvoice?audio="
            f"{urllib.parse.quote_plus(str(text or ''))}&le={voice}")


def _lang_for(code, hans, hant, default=None):
    """各家对中文简繁的写法不一样，按 provider 各给各的。"""
    text = str(code or "").strip()
    if not text or text == "auto":
        return default or ("auto" if default is None else default)
    if text in ("zh-Hans", "zh-CN", "zh"):
        return hans
    if text in ("zh-Hant", "zh-TW", "zh-HK"):
        return hant
    return text


def _no_auto(code, fallback):
    return fallback if str(code or "") in ("", "auto") else str(code)


class Provider:
    """一家翻译源。子类实现 ``_translate_one``。"""

    key = ""
    label = ""
    chunk = 900
    supports_auto_source = True

    def translate(self, text, source, target):
        raw = str(text or "")
        if not raw.strip():
            return {"text": "", "detected": source or ""}
        if not network.online():
            raise TranslateError(f"{self.label}：{network.OFFLINE_HINT}")
        pieces = split_chunks(raw, self.chunk)
        if len(pieces) == 1:
            return self._translate_one(pieces[0], source, target)
        results = run_chunks(lambda piece: self._translate_one(piece, source, target),
                             pieces, workers=3)
        detected = ""
        for item in results:
            if item.get("detected"):
                detected = item["detected"]
                break
        return {"text": "".join(item.get("text") or "" for item in results),
                "detected": detected}

    def _translate_one(self, text, source, target):
        raise NotImplementedError


class BingProvider(Provider):
    """必应。得先抓一次网页拿防滥用令牌，令牌过期就重新抓。"""

    key = "bing"
    label = "微软必应"
    chunk = BING_CHUNK
    supports_auto_source = True

    _HOME = "https://cn.bing.com/translator"
    _API = "https://cn.bing.com/ttranslatev3?isVertical=1&IG={ig}&IID=translator.5024"
    _lock = threading.Lock()
    _token = None

    def _fetch_token(self):
        page = http.get(self._HOME, headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": "https://cn.bing.com/",
        }, timeout=15)
        if isinstance(page, (bytes, bytearray)):
            page = page.decode("utf-8", "replace")
        match = _IG.search(str(page or ""))
        if not match:
            raise TranslateError("必应未能返回访问令牌")
        return match.group(1), match.group(2)

    def _translate_one(self, text, source, target):
        with self._lock:
            if not BingProvider._token:
                BingProvider._token = self._fetch_token()
            ig, token = BingProvider._token
        body = {
            "fromLang": _lang_for(source, "zh-Hans", "zh-Hant", default="auto"),
            "text": text,
            "to": _lang_for(target, "zh-Hans", "zh-Hant"),
            "token": token,
            "key": ig,
        }
        try:
            raw = http.post(self._API.format(ig=ig), body, headers={
                "Referer": "https://cn.bing.com/translator",
                "Origin": "https://cn.bing.com",
            }, timeout=10)
        except http.HttpError:
            with self._lock:
                BingProvider._token = None
            raise
        data = json.loads(raw) if isinstance(raw, (str, bytes, bytearray)) else raw
        return self._read(data)

    @staticmethod
    def _read(data):
        if isinstance(data, dict) and data.get("statusCode"):
            raise TranslateError(f"必应拒绝了这次请求：{data.get('statusCode')}")
        rows = data.get("translation") if isinstance(data, dict) else None
        if not isinstance(rows, list) or not rows:
            raise TranslateError("必应返回了空结果")
        first = rows[0] if isinstance(rows[0], dict) else {}
        text = first.get("translatedText") or ""
        if not text:
            raise TranslateError("必应返回了空结果")
        detected = ""
        language = first.get("detectedLanguage")
        if isinstance(language, dict):
            detected = language.get("language") or ""
        elif isinstance(language, str):
            detected = language
        return {"text": text, "detected": detected}


class YoudaoProvider(Provider):
    """有道智云那个公开演示接口，不用 key。"""

    key = "youdao"
    label = "网易有道"
    chunk = YOUDAO_CHUNK
    supports_auto_source = True

    def _translate_one(self, text, source, target):
        query = urllib.parse.urlencode({
            "q": text,
            "from": _lang_for(source, "zh-CHS", "zh-CHT", default="auto"),
            "to": _lang_for(target, "zh-CHS", "zh-CHT"),
        })
        raw = http.get(f"https://aidemo.youdao.com/trans?{query}", timeout=10)
        data = json.loads(raw) if isinstance(raw, (str, bytes, bytearray)) else raw
        if not isinstance(data, dict):
            raise TranslateError("有道返回结构不对")
        code = str(data.get("errorCode") or "0")
        if code not in ("0", ""):
            raise TranslateError(f"有道返回错误 {code}")
        rows = data.get("translation")
        if isinstance(rows, list):
            text_out = "".join(str(item) for item in rows if isinstance(item, str))
        elif isinstance(rows, str):
            text_out = rows
        else:
            text_out = ""
        if not text_out:
            raise TranslateError("有道返回了空结果")
        basic = data.get("basic") if isinstance(data.get("basic"), dict) else {}
        return {"text": text_out, "detected": str(basic.get("exam_type") or "")}


class MyMemoryProvider(Provider):
    """MyMemory 免费额度按天算，块要切小一点。"""

    key = "mymemory"
    label = "MyMemory"
    chunk = MYMEMORY_CHUNK
    supports_auto_source = False

    def _translate_one(self, text, source, target):
        query = urllib.parse.urlencode({
            "q": text,
            "langpair": f"{_no_auto(source, 'en')}|{_lang_for(target, 'zh-CN', 'zh-TW')}",
        })
        raw = http.get(f"https://api.mymemory.translated.net/get?{query}", timeout=10)
        data = json.loads(raw) if isinstance(raw, (str, bytes, bytearray)) else raw
        if not isinstance(data, dict):
            raise TranslateError("MyMemory 返回结构不对")
        status = data.get("responseStatus")
        if status and int(status) != 200:
            raise TranslateError(f"MyMemory 返回 {status}：{data.get('responseDetails') or ''}".strip())
        body = data.get("responseData") if isinstance(data.get("responseData"), dict) else {}
        text_out = str(body.get("translatedText") or "")
        detected = str(body.get("detectedLanguage") or "")
        if not text_out:
            rows = data.get("matches")
            if isinstance(rows, list) and rows and isinstance(rows[0], dict):
                text_out = str(rows[0].get("translation") or "")
        if not text_out:
            raise TranslateError("MyMemory 返回了空结果")
        return {"text": text_out, "detected": detected}


class GoogleProvider(Provider):
    """Google 的 gtx 端点，返回的是嵌套数组。"""

    key = "google"
    label = "Google"
    chunk = GOOGLE_CHUNK
    supports_auto_source = True

    def _translate_one(self, text, source, target):
        query = urllib.parse.urlencode({
            "client": "gtx",
            "sl": _lang_for(source, "zh-CN", "zh-TW", default="auto"),
            "tl": _lang_for(target, "zh-CN", "zh-TW"),
            "dt": "t",
            "q": text,
        })
        raw = http.get(f"https://translate.googleapis.com/translate_a/single?{query}",
                       headers={"User-Agent": UA}, timeout=10)
        data = json.loads(raw) if isinstance(raw, (str, bytes, bytearray)) else raw
        if not isinstance(data, list) or not data:
            raise TranslateError("Google 返回结构不对")
        segments = data[0] if isinstance(data[0], list) else []
        text_out = "".join(str(seg[0]) for seg in segments
                           if isinstance(seg, list) and seg and seg[0])
        detected = str(data[2] if len(data) > 2 and isinstance(data[2], str) else "")
        if not text_out:
            raise TranslateError("Google 未返回译文")
        return {"text": text_out, "detected": detected}


PROVIDERS = {
    "bing": BingProvider(),
    "youdao": YoudaoProvider(),
    "mymemory": MyMemoryProvider(),
    "google": GoogleProvider(),
}


class Engine:
    """按偏好排个序，一家不行换下一家。"""

    def __init__(self, settings):
        self._settings = settings

    def order(self, preferred):
        """选中的那家排最前面，其余按默认顺序兜底。"""
        choice = str(preferred or "").strip()
        if not choice:
            choice = str((self._settings or {}).get("translate_provider") or "").strip()
        if choice in PROVIDERS:
            return [choice] + [key for key in PROVIDER_ORDER if key != choice]
        return list(PROVIDER_ORDER)

    def translate(self, text, source, target, provider="auto"):
        source = "auto" if source in (None, "", "auto") else str(source)
        target = str(target or "zh-Hans")
        if source != "auto" and source == target:
            return {"text": str(text or ""), "provider": "", "source": source,
                    "target": target, "detected": source, "skipped": True}

        errors = []
        for key in self.order(provider):
            item = PROVIDERS[key]
            codes = source
            if codes == "auto" and not item.supports_auto_source:
                codes = "en"
            try:
                result = item.translate(text, codes, target)
            except TranslateError as exc:
                errors.append(str(exc))
                continue
            except Exception as exc:
                errors.append(f"{item.label}：{type(exc).__name__}: {exc}")
                continue
            if not str(result.get("text") or "").strip():
                errors.append(f"{item.label}：返回了空译文")
                continue
            return {"text": result.get("text") or "", "provider": key,
                    "source": source, "target": target,
                    "detected": result.get("detected") or ("" if source == "auto" else source),
                    "skipped": False}
        raise TranslateError("；".join(errors) or "没有可用的翻译源")
