"""AI 兜底解析：本地规则认不出来时，问一次大模型。

只认 OpenAI 兼容的 ``/chat/completions``，地址、密钥、模型都从设置里取。
没配好就抛 ``AIError``，调用方会退回到"只填标题"。
"""

import json
import re
from datetime import datetime

from . import httpclient as http

SYSTEM_PROMPT = """你是一个待办解析器。将用户输入解析为JSON，只输出JSON，不要任何解释。
JSON字段：
{
  "title": "任务标题",
  "notes": "备注",
  "due_at": "截止时间，ISO格式或null",
  "remind_at": "提醒时间，ISO格式或null",
  "repeat_rule": "none|daily|weekly|monthly|yearly",
  "priority": "low|medium|high",
  "tags": ["标签"]
}"""

VALID_PRIORITIES = ("low", "medium", "high")
VALID_REPEATS = ("none", "daily", "weekly", "monthly", "yearly")

TIMEOUT = 25
_FENCE = re.compile(r"```(?:json)?\s*(.+?)\s*```", re.S)


class AIError(Exception):
    """问 AI 这一路没走通，消息里写清卡在哪一步。"""


def configured(settings):
    """地址和密钥都填了才算配好。"""
    if not settings:
        return False
    base = str(settings.get("ai_base_url") or "").strip()
    key = str(settings.get("ai_api_key") or "").strip()
    return bool(base and key)


def _endpoint(base_url):
    base = str(base_url or "").strip().rstrip("/")
    if not base:
        raise AIError("还没有填 AI 接口地址")
    if base.endswith("/chat/completions"):
        return base
    return base + "/chat/completions"


def _extract(content):
    """模型爱把 JSON 包在 ``` 里，或者前后带几句客套话，都得扒出来。"""
    text = str(content or "").strip()
    fence = _FENCE.search(text)
    if fence:
        text = fence.group(1).strip()
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise AIError("AI 没有返回 JSON")
    try:
        return json.loads(text[start:end + 1])
    except ValueError:
        raise AIError("AI 没有返回 JSON") from None


def _tags(value):
    """标签可以是数组，也可以是一串用空白/逗号隔开的字。"""
    if isinstance(value, str):
        parts = re.split(r"(\s|,|，)", value)
        return [part.strip().lstrip("#") for part in parts if part.strip()]
    if isinstance(value, (list, tuple)):
        return [str(item).strip().lstrip("#") for item in value if str(item or "").strip()]
    return []


def parse(text, settings, now=None):
    """把一句话丢给模型，拿回结构化的一条待办。"""
    if not configured(settings):
        raise AIError("还没有配置 AI 接口，去设置里填一下地址和密钥")
    moment = now or datetime.now()
    payload = {
        "model": str(settings.get("ai_model") or "gpt-4o-mini"),
        "temperature": 0,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"当前时间：{moment.strftime('%Y-%m-%dT%H:%M')}\n"
                                        f"用户输入：{text}"},
        ],
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {str(settings.get('ai_api_key') or '').strip()}",
    }
    raw = http.request(_endpoint(settings.get("ai_base_url")),
                       data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                       headers=headers, timeout=TIMEOUT)

    try:
        reply = json.loads(raw) if isinstance(raw, (str, bytes, bytearray)) else raw
    except ValueError:
        raise AIError("AI 接口返回内容无法解析") from None

    if not isinstance(reply, dict):
        raise AIError("AI 返回结构不完整")
    if reply.get("error"):
        detail = reply["error"]
        if isinstance(detail, dict):
            detail = detail.get("message") or detail
        raise AIError(f"AI 接口报错：{detail}")

    choices = reply.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise AIError("AI 返回结构不完整")
    message = choices[0].get("message") or {}
    data = _extract(message.get("content"))
    if not isinstance(data, dict):
        raise AIError("AI 没有返回 JSON")

    repeat = data.get("repeat_rule")
    priority = data.get("priority")
    # 模型给的时间原样往回带，落库前由 todo 那边统一收拾格式
    due = data.get("due_at") or data.get("remind_at") or None
    remind = data.get("remind_at") or None
    return {
        "title": str(data.get("title") or "").strip(),
        "notes": str(data.get("notes") or "").strip(),
        "due_at": due,
        "remind_at": remind,
        "repeat_rule": repeat if repeat in VALID_REPEATS else "none",
        "priority": priority if priority in VALID_PRIORITIES else "medium",
        "tags": _tags(data.get("tags")),
        "matched_time": bool(due),
        "source": "ai",
    }
