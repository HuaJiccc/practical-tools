"""语言表：内部 id + 各渠道自己的语言代码。

每一项是 (内部 id, 中文名, 英文名, 必应, 有道, MyMemory, Google)。
某个渠道用 None 表示它不支持这门语言 —— 比如 MyMemory 不接受"自动检测"，
必应和谷歌则有自己的 auto 代码。
"""

# (id, 中文名, 英文名, bing, youdao, mymemory, google)
LANGUAGES = [
    ("auto", "自动检测", "Auto Detect", "auto-detect", "auto", None, "auto"),
    ("zh-Hans", "中文（简体）", "Chinese (Simplified)", "zh-Hans", "zh-CHS", "zh-CN", "zh-CN"),
    ("zh-Hant", "中文（繁体）", "Chinese (Traditional)", "zh-Hant", "zh-CHT", "zh-TW", "zh-TW"),
    ("en", "英语", "English", "en", "en", "en", "en"),
    ("ja", "日语", "Japanese", "ja", "ja", "ja", "ja"),
    ("ko", "韩语", "Korean", "ko", "ko", "ko", "ko"),
    ("fr", "法语", "French", "fr", "fr", "fr", "fr"),
    ("de", "德语", "German", "de", "de", "de", "de"),
    ("es", "西班牙语", "Spanish", "es", "es", "es", "es"),
    ("ru", "俄语", "Russian", "ru", "ru", "ru", "ru"),
    ("pt", "葡萄牙语", "Portuguese", "pt", "pt", "pt", "pt"),
    ("it", "意大利语", "Italian", "it", "it", "it", "it"),
    ("ar", "阿拉伯语", "Arabic", "ar", "ar", "ar", "ar"),
    ("th", "泰语", "Thai", "th", "th", "th", "th"),
    ("vi", "越南语", "Vietnamese", "vi", "vi", "vi", "vi"),
    ("id", "印尼语", "Indonesian", "id", "id", "id", "id"),
    ("ms", "马来语", "Malay", "ms", "ms", "ms", "ms"),
    ("hi", "印地语", "Hindi", "hi", "hi", "hi", "hi"),
    ("nl", "荷兰语", "Dutch", "nl", "nl", "nl", "nl"),
    ("pl", "波兰语", "Polish", "pl", "pl", "pl", "pl"),
    ("tr", "土耳其语", "Turkish", "tr", "tr", "tr", "tr"),
    ("sv", "瑞典语", "Swedish", "sv", "sv", "sv", "sv"),
    ("da", "丹麦语", "Danish", "da", "da", "da", "da"),
    ("fi", "芬兰语", "Finnish", "fi", "fi", "fi", "fi"),
    ("no", "挪威语", "Norwegian", "nb", "no", "no", "no"),
    ("cs", "捷克语", "Czech", "cs", "cs", "cs", "cs"),
    ("el", "希腊语", "Greek", "el", "el", "el", "el"),
    ("he", "希伯来语", "Hebrew", "he", "he", "he", "iw"),
    ("hu", "匈牙利语", "Hungarian", "hu", "hu", "hu", "hu"),
    ("ro", "罗马尼亚语", "Romanian", "ro", "ro", "ro", "ro"),
    ("uk", "乌克兰语", "Ukrainian", "uk", "uk", "uk", "uk"),
    ("bg", "保加利亚语", "Bulgarian", "bg", "bg", "bg", "bg"),
    ("sk", "斯洛伐克语", "Slovak", "sk", "sk", "sk", "sk"),
    ("hr", "克罗地亚语", "Croatian", "hr", "hr", "hr", "hr"),
    ("sr", "塞尔维亚语", "Serbian", "sr-Cyrl", "sr", "sr", "sr"),
    ("ca", "加泰罗尼亚语", "Catalan", "ca", "ca", "ca", "ca"),
    ("af", "南非荷兰语", "Afrikaans", "af", "af", "af", "af"),
    ("sw", "斯瓦希里语", "Swahili", "sw", "sw", "sw", "sw"),
    ("fa", "波斯语", "Persian", "fa", "fa", "fa", "fa"),
    ("ur", "乌尔都语", "Urdu", "ur", "ur", "ur", "ur"),
    ("bn", "孟加拉语", "Bengali", "bn", "bn", "bn", "bn"),
    ("ta", "泰米尔语", "Tamil", "ta", "ta", "ta", "ta"),
    ("te", "泰卢固语", "Telugu", "te", "te", "te", "te"),
    ("fil", "菲律宾语", "Filipino", "tl", "tl", "tl", "tl"),
    ("my", "缅甸语", "Burmese", "my", "my", "my", "my"),
    ("km", "高棉语", "Khmer", "km", "km", "km", "km"),
    ("lo", "老挝语", "Lao", "lo", "lo", "lo", "lo"),
    ("ne", "尼泊尔语", "Nepali", "ne", "ne", "ne", "ne"),
    ("si", "僧伽罗语", "Sinhala", "si", "si", "si", "si"),
    ("et", "爱沙尼亚语", "Estonian", "et", "et", "et", "et"),
    ("lv", "拉脱维亚语", "Latvian", "lv", "lv", "lv", "lv"),
    ("lt", "立陶宛语", "Lithuanian", "lt", "lt", "lt", "lt"),
    ("sl", "斯洛文尼亚语", "Slovenian", "sl", "sl", "sl", "sl"),
]

PROVIDER_FIELDS = ("bing", "youdao", "mymemory", "google")
_FALLBACK = "en"


def _entry(row):
    return {
        "id": row[0],
        "name": row[1],
        "en": row[2],
        "bing": row[3],
        "youdao": row[4],
        "mymemory": row[5],
        "google": row[6],
    }


_BY_ID = {row[0]: _entry(row) for row in LANGUAGES}


def catalogue():
    """给前端的整张表。"""
    return [_entry(row) for row in LANGUAGES]


def get(lang_id):
    """按 id 取条目；不认识的 id 退回到英语，界面不会因此空一块。"""
    return _BY_ID.get(str(lang_id or "")) or _BY_ID[_FALLBACK]


def _codes_for(lang_id):
    row = _BY_ID.get(str(lang_id or ""))
    return row or _BY_ID[_FALLBACK]


def code_for(lang_id, provider):
    """某个渠道下这门语言的代码；该渠道不支持时返回 None。"""
    if provider not in PROVIDER_FIELDS:
        return None
    return _codes_for(lang_id)[provider]


def name_of(lang_id):
    return _codes_for(lang_id)["name"]


_FIELD_INDEX = {"bing": 3, "youdao": 4, "mymemory": 5, "google": 6}


def _key(text):
    """比较用的规范化：小写，并且抹掉书写体系后缀。

    塞尔维亚语这类语言，同一门语言会以 sr / sr-Cyrl / sr-Latn 三种形式回来，
    对用户来说是同一个东西。
    """
    value = str(text or "").strip().lower().replace("_", "-")
    for suffix in ("-cyrl", "-latn"):
        if value.endswith(suffix):
            value = value[: -len(suffix)]
    return value


def normalize(provider, code):
    """把渠道回报的语言代码映射回内部 id，认不出返回 None。

    先按该渠道自己的代码表精确匹配（"自动检测"不算，它不是一门语言），
    再兜一层中文：各家写法五花八门（zh / zh-CN / zh-CHS），一律当简体。
    """
    index = _FIELD_INDEX.get(provider)
    text = _key(code)
    if index is None or not text:
        return None

    for row in LANGUAGES:
        if row[0] == "auto":
            continue
        if _key(row[index]) == text:
            return row[0]

    # 渠道回报的代码常带地区（en-US / pt-BR / nb-NO），退一步按语言主体再找
    base = text.split("-")[0]
    if base != text:
        for row in LANGUAGES:
            if row[0] == "auto":
                continue
            if _key(row[index]) == base:
                return row[0]

    if base == "zh":
        return "zh-Hans"
    return None


def detect(text):
    """按字符集猜语言，只在前端需要显式源语言时才用得上。"""
    sample = str(text or "")
    seen = set()
    for ch in sample:
        point = ord(ch)
        if 0x3040 <= point <= 0x30FF or 0x31F0 <= point <= 0x31FF:
            seen.add("ja")
        elif 0xAC00 <= point <= 0xD7AF or 0x1100 <= point <= 0x11FF:
            seen.add("ko")
        elif 0x4E00 <= point <= 0x9FFF or 0x3400 <= point <= 0x4DBF:
            seen.add("zh")
        elif 0x0400 <= point <= 0x04FF:
            seen.add("ru")
        elif 0x0600 <= point <= 0x06FF:
            seen.add("ar")
        elif 0x0E00 <= point <= 0x0E7F:
            seen.add("th")
        elif 0x0900 <= point <= 0x097F:
            seen.add("hi")

    if "ja" in seen:
        return "ja"
    if "ko" in seen:
        return "ko"
    if "zh" in seen:
        return "zh-Hans"
    for lang in ("ru", "ar", "th", "hi"):
        if lang in seen:
            return lang
    return "en"
