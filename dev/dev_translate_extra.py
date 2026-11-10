"""翻译扩展渠道的自测：AI 接口（本地 mock）+ 腾讯交互翻译，以及内置渠道不被影响。

不开 GUI，直接构造 UiApi 打接口。
"""
import json
import os
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "app"))

os.environ["PERSONALTOOLS_DATA"] = tempfile.mkdtemp(prefix="pt_extra_")

from ptools.api import Api  # noqa: E402
from ptools.config import Settings, data_dir  # noqa: E402
from ptools.store import History  # noqa: E402

import app as appmod  # noqa: E402

root = data_dir()
settings = Settings(root / "settings.json")
history = History(root / "history.json", 300)
api = Api(settings=settings, history=history)
ui = appmod.UiApi(api)

ok = 0
fail = 0


def check(label, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1
        print(f"  PASS  {label}  {detail}")
    else:
        fail += 1
        print(f"  FAIL  {label}  {detail}")


# ---------- 1. 未配置时的 AI 渠道 ----------
print("\n[1] AI 未配置")
r = ui.translate("hello", "auto", "zh-Hans", "ai")
check("返回 ok:false 而不是抛异常", r.get("ok") is False, str(r.get("error"))[:60])
check("错误里提示去填 Key", "Key" in (r.get("error") or ""), r.get("error") or "")


# ---------- 2. 本地 mock 的 OpenAI 兼容服务 ----------
class Handler(BaseHTTPRequestHandler):
    last = {}

    def log_message(self, *a):
        pass

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n)
        Handler.last = {
            "path": self.path,
            "auth": self.headers.get("Authorization", ""),
            "json": json.loads(body or b"{}"),
        }
        if "dead" in self.path:
            self.send_response(404)
            self.end_headers()
            return
        payload = {
            "choices": [{"message": {"role": "assistant",
                                     "content": '```\n“你好，世界”\n```'}}],
            "model": "mock-model",
        }
        raw = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


srv = HTTPServer(("127.0.0.1", 0), Handler)
port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()

api.save_settings({
    "ai_base_url": f"http://127.0.0.1:{port}/v1",
    "ai_api_key": "sk-test-123",
    "ai_model": "mock-model",
})
settings.reload() if hasattr(settings, "reload") else None

print("\n[2] AI 渠道（本地 mock）")
r = ui.translate("hello world", "auto", "zh-Hans", "ai")
check("翻成功", r.get("ok") is True, str(r.get("error"))[:80])
check("译文去掉了代码围栏和引号", r.get("text") == "你好，世界", repr(r.get("text")))
check("provider 标记为 ai", r.get("provider") == "ai", str(r.get("provider")))
check("provider_label 带模型名", "mock-model" in (r.get("provider_label") or ""), r.get("provider_label"))
check("有耗时", isinstance(r.get("elapsed_ms"), int), str(r.get("elapsed_ms")))
check("写进了历史", (r.get("entry") or {}).get("result") == "你好，世界", str((r.get("entry") or {}).get("result")))

sent = Handler.last
check("端点自动补成 /chat/completions", sent["path"] == "/v1/chat/completions", sent["path"])
check("Authorization 带上了 Bearer", sent["auth"] == "Bearer sk-test-123", sent["auth"])
check("body 里有 model", sent["json"].get("model") == "mock-model", str(sent["json"].get("model")))
msgs = sent["json"].get("messages") or []
check("有 system + user 两条消息", len(msgs) == 2, str([m.get("role") for m in msgs]))
check("user 消息里点名目标语言", "中文（简体）" in msgs[1]["content"], msgs[1]["content"][:60])
check("user 消息里带原文", "hello world" in msgs[1]["content"], "")

# 指定源语言
ui.translate("hello", "en", "ja", "ai")
check("指定源语言时提示里写明语种",
      "英语" in Handler.last["json"]["messages"][1]["content"],
      Handler.last["json"]["messages"][1]["content"][:50])

# 端点写法兼容
for base in (f"http://127.0.0.1:{port}", f"http://127.0.0.1:{port}/v1/chat/completions"):
    api.save_settings({"ai_base_url": base})
    rr = ui.translate("hi", "en", "zh-Hans", "ai")
    check(f"地址写法 {base.split('/', 3)[-1] or '仅域名'} 也能通", rr.get("ok") is True, str(rr.get("error"))[:60])

api.save_settings({"ai_base_url": f"http://127.0.0.1:{port}/v1"})

# 测试连接接口
t = ui.ai_test()
check("ai_test 返回耗时与回显", t.get("ok") is True and t.get("elapsed_ms") is not None,
      f"{t.get('elapsed_ms')}ms {str(t.get('text'))[:20]}")

# 错误 Key 的提示
api.save_settings({"ai_base_url": f"http://127.0.0.1:{port}/dead"})
bad = ui.translate("hi", "en", "zh-Hans", "ai")
check("地址错时给出可读错误", bad.get("ok") is False and "AI 接口报错" in (bad.get("error") or ""),
      str(bad.get("error"))[:70])
api.save_settings({"ai_base_url": f"http://127.0.0.1:{port}/v1"})


# ---------- 3. 腾讯交互翻译 ----------
print("\n[3] 腾讯交互翻译（真实网络）")
cases = [("hello world", "auto", "zh-Hans"), ("今天天气不错", "auto", "en"),
         ("good morning", "en", "ko"), ("こんにちは", "ja", "zh-Hans")]
for text, src, tgt in cases:
    r = ui.translate(text, src, tgt, "transmart")
    check(f"{src}->{tgt} {text[:14]}", r.get("ok") is True and bool(r.get("text")),
          f"{r.get('text')!r} {r.get('elapsed_ms')}ms {str(r.get('error'))[:40]}")
    check("  provider 标记正确", r.get("provider") == "transmart", str(r.get("provider")))


# ---------- 4. 内置渠道没被影响 ----------
print("\n[4] 内置渠道回归")
r = ui.translate("hello world", "auto", "zh-Hans", "bing")
check("bing 仍然可用", r.get("ok") is True, f"{r.get('text')!r} {r.get('provider_label')}")
r = ui.translate("hello world", "auto", "zh-Hans", None)
check("传 None 走智能选择", r.get("ok") is True, f"{r.get('text')!r} {r.get('provider')}")

boot = ui.bootstrap()
keys = [p["key"] for p in boot["providers"]]
check("渠道表含 4 个内置", all(k in keys for k in ("bing", "youdao", "mymemory", "google")), str(keys))
check("渠道表含腾讯交互翻译", "transmart" in keys, "")
check("渠道表含 AI", "ai" in keys, "")
check("渠道表仍有智能选择", "auto" in keys, "")
check("bootstrap 带 ai 状态", boot["ai"]["ready"] is True and boot["ai"]["model"] == "mock-model",
      json.dumps({k: boot["ai"][k] for k in ("ready", "model", "endpoint")}, ensure_ascii=False))
check("bootstrap 带 7 个预设", len(boot["ai"]["presets"]) == 7, str(len(boot["ai"]["presets"])))


# ---------- 5. 智能选择的内置渠道兜底 ----------
print("\n[5] 智能选择兜底")
real = ui._api.translate
ui._api.translate = lambda *a, **k: {"ok": False, "error": "四个内置渠道都模拟失败"}
r = ui.translate("hello world", "auto", "zh-Hans", None)
check("内置全失败时用腾讯翻译顶上", r.get("ok") is True and bool(r.get("text")),
      f"{r.get('text')!r} provider={r.get('provider')}")
check("兜底时把原错误记进 attempts", bool(r.get("attempts")), str(r.get("attempts"))[:60])
ui._api.translate = real

r = ui.translate("hello world", "auto", "zh-Hans", None)
check("内置正常时不走兜底", r.get("provider") in ("bing", "youdao", "mymemory", "google"),
      f"provider={r.get('provider')}")


# ---------- 6. 检测通道可用性覆盖到新渠道 ----------
print("\n[6] probe 覆盖")
pr = ui.probe()
keys_p = [x["key"] for x in pr["results"]]
check("probe 结果含 6 条", len(pr["results"]) == 6, str(keys_p))
check("含腾讯交互翻译", "transmart" in keys_p, str([x for x in pr["results"] if x["key"] == "transmart"]))
check("含 AI 条目", "ai" in keys_p, str([x for x in pr["results"] if x["key"] == "ai"]))

srv.shutdown()
print(f"\n==== {ok} passed, {fail} failed ====")
sys.exit(0 if fail == 0 else 1)
