"""中英文切换自测。

做三件事：
1. 通过界面把语言切到英文，逐页收集「仍是中文」的文本，给出未覆盖清单
2. 切回中文，确认关键节点还原
3. 检查英文下有没有横向溢出（长英文撑破布局）
"""

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

import webview  # noqa: E402
import app as appmod  # noqa: E402

PAGES = [
    "home", "plan", "translate", "notes", "todo", "time", "chart", "image",
    "mood", "units", "picker", "history", "favorites",
]

COLLECT = """
(() => {
  const out = new Set();
  const walk = (node) => {
    if (node.nodeType === 3) {
      const t = node.nodeValue.trim();
      if (t && /[\\u4e00-\\u9fa5]/.test(t)) out.add(t);
      return;
    }
    if (node.nodeType !== 1) return;
    const tag = node.tagName;
    if (tag === 'SCRIPT' || tag === 'STYLE' || tag === 'svg' || tag === 'SVG') return;
    for (const attr of ['placeholder', 'title']) {
      const v = node.getAttribute(attr);
      if (v && /[\\u4e00-\\u9fa5]/.test(v)) out.add('@' + attr + ':' + v);
    }
    for (const child of node.childNodes) walk(child);
  };
  walk(document.querySelector('.set-pane.active') || document.body);
  walk(document.querySelector('.page.active') || document.body);
  return Array.from(out);
})()
"""

OVERFLOW = """
(() => {
  const bad = [];
  document.querySelectorAll('.page.active *, .set-pane.active *').forEach((el) => {
    if (el.scrollWidth > el.clientWidth + 4 && el.clientWidth > 0) {
      const t = (el.textContent || '').trim().slice(0, 40);
      if (t) bad.push(el.className + ' | ' + t);
    }
  });
  return bad.slice(0, 15);
})()
"""

checks = []


def check(name, ok, detail=""):
    checks.append((name, bool(ok), detail))
    print(("PASS  " if ok else "FAIL  ") + name + (f"  ({detail})" if detail else ""))


def main():
    built = appmod.build_window()
    win = built[0]
    leftover = {}
    overflow = {}
    restored = {}

    def js(code, default=None):
        try:
            return win.evaluate_js(code)
        except Exception:
            return default

    def on_start():
        end = time.time() + 40
        while time.time() < end:
            if js("document.readyState") == "complete":
                break
            time.sleep(0.4)
        time.sleep(2.5)

        js("location.hash = '#/settings'")
        time.sleep(0.8)
        js("document.querySelector('#langSeg button[data-lang=\"en\"]').click()")
        time.sleep(1.2)

        lang_now = js("window.PTI18n && window.PTI18n.lang")
        check("切到英文", lang_now == "en", str(lang_now))
        check("html lang 属性", js("document.documentElement.lang") == "en",
              str(js("document.documentElement.lang")))
        check("页面标题已英文化", js("document.querySelector('#pageTitle').textContent") == "Settings",
              str(js("document.querySelector('#pageTitle').textContent")))
        check("侧栏已英文化",
              (js("document.querySelector('[data-nav=home]').textContent") or "").strip() == "Overview",
              str(js("document.querySelector('[data-nav=home]').textContent")))

        # 逐页收集残留中文
        for pane in ["look", "general", "trans", "ai", "data", "about"]:
            js(f"document.querySelector('#setRail .set-tab[data-set-tab=\"{pane}\"]').click()")
            time.sleep(0.35)
            items = js(COLLECT) or []
            if items:
                leftover[f"settings/{pane}"] = items
            over = js(OVERFLOW) or []
            if over:
                overflow[f"settings/{pane}"] = over

        for page in PAGES:
            js(f"location.hash = '#/{page}'")
            time.sleep(0.6)
            items = js(COLLECT) or []
            if items:
                leftover[page] = items
            over = js(OVERFLOW) or []
            if over:
                overflow[page] = over

        # 截图：英文下的真实排版
        shots = ROOT / "dev" / "_shots" / "v10en"
        shots.mkdir(parents=True, exist_ok=True)
        sys.path.insert(0, str(ROOT / "dev"))
        try:
            from shot_util import find, shot as grab
            hwnd = find("实用工具")
            js("location.hash = '#/settings'")
            time.sleep(0.5)
            js("document.querySelector('#setRail .set-tab[data-set-tab=\"look\"]').click()")
            time.sleep(0.5)
            grab(hwnd, shots / "settings_look.png")
            js("location.hash = '#/home'")
            time.sleep(0.8)
            grab(hwnd, shots / "home.png")
            js("location.hash = '#/translate'")
            time.sleep(0.6)
            grab(hwnd, shots / "translate.png")
            js("location.hash = '#/image'")
            time.sleep(0.6)
            grab(hwnd, shots / "image.png")
            print("截图：dev/_shots/v10en")
        except Exception as exc:
            print("截图失败:", exc)

        total = sum(len(v) for v in leftover.values())
        uniq = len({i for v in leftover.values() for i in v})
        print(f"\n未翻译：{total} 处，去重 {uniq} 条")

        # 切回中文
        js("location.hash = '#/settings'")
        time.sleep(0.5)
        js("document.querySelector('#langSeg button[data-lang=\"zh\"]').click()")
        time.sleep(1.0)
        check("切回中文", js("window.PTI18n.lang") == "zh", str(js("window.PTI18n.lang")))
        restored["title"] = js("document.querySelector('#pageTitle').textContent")
        restored["nav"] = (js("document.querySelector('[data-nav=home]').textContent") or "").strip()
        check("标题还原", restored["title"] == "设置", restored["title"])
        check("侧栏还原", restored["nav"] == "概览", restored["nav"])
        check("英文残留清理", "Settings" not in (js("document.body.innerText") or ""),
              "正文仍有 Settings" if "Settings" in (js("document.body.innerText") or "") else "")

        (ROOT / "dev" / "_lang_report.json").write_text(
            json.dumps({"leftover": leftover, "overflow": overflow, "restored": restored},
                       ensure_ascii=False, indent=1),
            encoding="utf-8",
        )
        print("报告：dev/_lang_report.json")
        win.destroy()

    webview.start(func=on_start, gui="edgechromium")
    failed = [c for c in checks if not c[1]]
    print(f"\n{len(checks) - len(failed)}/{len(checks)} 通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
