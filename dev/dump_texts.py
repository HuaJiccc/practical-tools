"""导出各页面真实渲染后的文案，用来校对中英文覆盖情况。

用法：python dev/_dump_texts.py [输出文件]
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
    "mood", "units", "picker", "history", "favorites", "settings",
]

COLLECT = """
(() => {
  const out = new Set();
  const skip = new Set(['SCRIPT', 'STYLE', 'SVG']);
  const walk = (node) => {
    if (skip.has(node.tagName)) return;
    for (const child of node.childNodes) {
      if (child.nodeType === 3) {
        const t = child.nodeValue.trim();
        if (t && /[\\u4e00-\\u9fa5]/.test(t)) out.add(t);
      } else if (child.nodeType === 1) {
        if (child.getAttribute) {
          for (const attr of ['placeholder', 'title', 'aria-label']) {
            const v = child.getAttribute(attr);
            if (v && /[\\u4e00-\\u9fa5]/.test(v)) out.add('@' + attr + ':' + v);
          }
        }
        walk(child);
      }
    }
  };
  walk(document.body);
  return Array.from(out);
})()
"""


def main():
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "dev" / "_texts.json"
    window = appmod.build_window()[0] if False else None  # noqa: F841  占位，避免误用
    built = appmod.build_window()
    win = built[0]

    collected = {}

    def on_start():
        end = time.time() + 40
        while time.time() < end:
            try:
                if win.evaluate_js("document.readyState") == "complete":
                    break
            except Exception:
                pass
            time.sleep(0.5)
        time.sleep(2)
        for page in PAGES:
            try:
                win.evaluate_js(f"location.hash = '#/{page}'")
            except Exception:
                continue
            time.sleep(0.7)
            try:
                items = win.evaluate_js(COLLECT) or []
            except Exception:
                items = []
            collected[page] = items
            print(f"{page}: {len(items)}")
        target.write_text(json.dumps(collected, ensure_ascii=False, indent=1), encoding="utf-8")
        print("写出:", target)
        win.destroy()

    webview.start(func=on_start, gui="edgechromium")
    total = sum(len(v) for v in collected.values())
    uniq = len({i for v in collected.values() for i in v})
    print(f"合计 {total} 条，去重 {uniq} 条")
    return 0


if __name__ == "__main__":
    sys.exit(main())
