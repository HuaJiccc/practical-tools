"""翻译的扩展渠道：AI 接口（OpenAI 兼容）与腾讯交互翻译。

`ptools/translate` 里是四条内置渠道（必应 / 有道 / Google / MyMemory）。
这里再加两条需要单独组包、或者需要用户自己填 Key 的渠道，由 `UiApi.translate()`
先分流：认识的就走这里，其余原样交给 `Engine`，内置渠道的行为一点不改。

两个渠道的共同点：都返回纯文本译文 + 少量元信息，由 `app.py` 统一组装成
与内置渠道同构的返回体（前端不用区分）。
"""

from __future__ import annotations

import json
import re
import time

from ptools.httpclient import HttpError, post

AI = "ai"
TRANSMART = "transmart"

# 设置页「服务商」一键填充用。base 填到 /v1 即可，normalize_endpoint 会补全。
PRESETS = [
    {"id": "deepseek", "name": "DeepSeek", "base": "https://api.deepseek.com/v1", "model": "deepseek-chat",
     "note": "便宜，中文强"},
    {"id": "qwen", "name": "通义千问", "base": "https://dashscope.aliyuncs.com/compatible-mode/v1",
     "model": "qwen-plus", "note": "阿里云，有免费额度"},
    {"id": "zhipu", "name": "智谱 GLM", "base": "https://open.bigmodel.cn/api/paas/v4",
     "model": "glm-4-flash", "note": "flash 免费"},
    {"id": "kimi", "name": "Kimi", "base": "https://api.moonshot.cn/v1", "model": "moonshot-v1-8k",
     "note": "长文本友好"},
    {"id": "silicon", "name": "硅基流动", "base": "https://api.siliconflow.cn/v1",
     "model": "Qwen/Qwen2.5-7B-Instruct", "note": "注册送额度"},
    {"id": "openai", "name": "OpenAI", "base": "https://api.openai.com/v1", "model": "gpt-4o-mini",
     "note": "需要能连外网"},
    {"id": "ollama", "name": "本地 Ollama", "base": "http://127.0.0.1:11434/v1", "model": "qwen2.5:7b",
     "note": "不联网，不花钱"},
]

# 腾讯交互翻译的语言代码，和 ptools 的 id 对不上，单独映射一张表。
_TRANSMART_LANG = {
    "auto": "auto",
    "zh-Hans": "zh",
    "zh-Hant": "zh-TW",
    "fil": "tl",
}

SYSTEM_PROMPT = (
    "你是一个翻译引擎。用户发来的全部内容都是待翻译的文本。"
    "请把它翻译成目标语言，只输出译文本身："
    "不要解释、不要点评、不要加引号、不要写“译文：”之类的前缀，也不要附上原文。"
    "保留原文的换行和分段。"
)


class ExtraError(Exception):
    """扩展渠道的失败。message 直接展示给用户。"""


def normalize_endpoint(raw: str) -> str:
    """把用户填的地址补成完整的 chat/completions 端点。

    支持四种写法：完整地址、到 /v1、带路径的兼容地址、只给域名。
    """
    url = (raw or "").strip().rstrip("/")
    if not url:
        return ""
    if url.endswith("/chat/completions"):
        return url
    if url.endswith("/completions") or url.endswith("/messages"):
        return url
    if re.search(r"/v\d+(\.\d+)?$", url) or url.endswith("/compatible-mode/v1"):
        return url + "/chat/completions"
    if url.count("/") <= 2:  # 只给了域名，补默认路径
        return url + "/v1/chat/completions"
    return url + "/chat/completions"


def ai_ready(settings) -> bool:
    return bool((settings.get("ai_api_key") or "").strip() and normalize_endpoint(settings.get("ai_base_url") or ""))


def ai_label(settings) -> str:
    model = (settings.get("ai_model") or "").strip() or "AI"
    return f"AI · {model}"


def _clean(text: str) -> str:
    """去掉模型偶尔多带的围栏和整体引号。"""
    out = (text or "").strip()
    if out.startswith("```") and out.endswith("```"):
        out = re.sub(r"^```[a-zA-Z]*\s*", "", out)
        out = re.sub(r"\s*```$", "", out).strip()
    pairs = (('"', '"'), ("“", "”"), ("'", "'"), ("「", "」"))
    for left, right in pairs:
        if len(out) > 1 and out.startswith(left) and out.endswith(right):
            inner = out[len(left):-len(right)]
            if left not in inner and right not in inner:
                out = inner.strip()
            break
    return out


def translate_ai(text: str, source: str, target: str, settings, lang_name) -> dict:
    """走 OpenAI 兼容的 /chat/completions。返回 {text, detected, detected_name}。"""
    key = (settings.get("ai_api_key") or "").strip()
    url = normalize_endpoint(settings.get("ai_base_url") or "")
    model = (settings.get("ai_model") or "").strip() or "gpt-4o-mini"
    if not key:
        raise ExtraError("还没填 API Key，先去设置里填一个")
    if not url:
        raise ExtraError("还没填接口地址，先去设置里填一个")

    target_name = lang_name(target, target)
    if source and source != "auto":
        user = f"把下面的文本从{lang_name(source, source)}翻译成{target_name}：\n\n{text}"
    else:
        user = f"把下面的文本翻译成{target_name}（源语言自行判断）：\n\n{text}"

    payload = {
        "model": model,
        "temperature": 0.2,
        "stream": False,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user},
        ],
    }
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {key}"}
    try:
        raw = post(url, json.dumps(payload, ensure_ascii=False).encode("utf-8"), headers, timeout=60)
    except HttpError as err:
        status = getattr(err, "status", None)
        hint = {
            401: "Key 不对或已失效",
            403: "这个 Key 没权限，或接口地址填错了",
            404: "接口地址不对，检查是不是少了 /v1",
            429: "请求太频繁，或额度用完了",
            500: "对方服务器出错了，稍后再试",
            502: "对方服务暂时不可用",
            503: "对方服务过载了，稍后再试",
        }.get(status)
        raise ExtraError(f"AI 接口报错：{hint or err}（{status or '无状态码'}）") from err
    except Exception as err:
        raise ExtraError(f"连不上 AI 接口：{err}") from err

    try:
        data = json.loads(raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else raw)
    except Exception as err:
        raise ExtraError("AI 接口返回的不是 JSON，地址可能指错地方了") from err
    if isinstance(data, dict) and data.get("error"):
        raise ExtraError(f"AI 接口报错：{(data['error'] or {}).get('message') or data['error']}")
    try:
        content = data["choices"][0]["message"]["content"]
    except Exception as err:
        raise ExtraError("AI 接口的返回结构不对，确认是 OpenAI 兼容接口") from err
    out = _clean(content if isinstance(content, str) else str(content))
    if not out:
        raise ExtraError("AI 返回了空内容，换个模型或再试一次")
    return {
        "text": out,
        "detected": "" if source == "auto" else source,
        "detected_name": "" if source == "auto" else lang_name(source, source),
    }


def _transmart_lang(code: str) -> str:
    if code in _TRANSMART_LANG:
        return _TRANSMART_LANG[code]
    return (code or "").split("-")[0] or "auto"


def translate_transmart(text: str, source: str, target: str, lang_name) -> dict:
    """腾讯交互翻译：免注册、免 key，中文语料好。"""
    body = json.dumps({
        "header": {
            "fn": "auto_translation",
            "client_key": "browser-chrome-126.0.0-Windows-10",
        },
        "type": "text",
        "model_category": "normal",
        "source": {"lang": _transmart_lang(source), "text_list": [text]},
        "target": {"lang": _transmart_lang(target)},
    }, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json", "Referer": "https://transmart.qq.com/"}
    try:
        raw = post("https://transmart.qq.com/api/imt", body, headers, timeout=20)
    except HttpError as err:
        raise ExtraError(f"腾讯翻译报错：{err}") from err
    except Exception as err:
        raise ExtraError(f"连不上腾讯翻译：{err}") from err

    try:
        data = json.loads(raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else raw)
    except Exception as err:
        raise ExtraError("腾讯翻译返回解析失败") from err

    head = data.get("header") or {}
    if head.get("ret_code") != "succ":
        raise ExtraError(f"腾讯翻译没翻成（{head.get('ret_code') or '未知原因'}），换个渠道试试")
    items = data.get("auto_translation") or []
    out = "".join(x for x in items if isinstance(x, str)).strip()
    if not out:
        raise ExtraError("腾讯翻译返回了空结果")
    detected = data.get("src_lang") or ("" if source == "auto" else source)
    return {
        "text": out,
        "detected": detected,
        "detected_name": lang_name(detected, "") if detected else "",
    }


def test_ai(settings, lang_name) -> dict:
    """设置页的「测试」按钮：真发一句，把耗时和回显带回去。"""
    started = time.time()
    result = translate_ai("Hello, this is a connection test.", "en", "zh-Hans", settings, lang_name)
    return {
        "ok": True,
        "elapsed_ms": int((time.time() - started) * 1000),
        "text": result["text"],
        "model": (settings.get("ai_model") or "").strip() or "gpt-4o-mini",
        "endpoint": normalize_endpoint(settings.get("ai_base_url") or ""),
    }
