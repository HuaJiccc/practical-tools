"""静态自检：不开程序，只查前端资源是否完整、图标引用是否悬空。

CI 里跑这个，本地改完 HTML 也可以先跑一遍再开窗口。

    python dev/dev_check_assets.py
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "app" / "web"

REQUIRED = ("index.html", "app.js", "style.css")


def main() -> int:
    bad = 0

    for name in REQUIRED:
        p = WEB / name
        if not p.is_file() or p.stat().st_size == 0:
            print(f"FAIL  缺少或为空：app/web/{name}")
            bad += 1
    if bad:
        return 1

    html = (WEB / "index.html").read_text(encoding="utf-8")
    js = (WEB / "app.js").read_text(encoding="utf-8")

    defs = re.findall(r'<symbol[^>]*\bid="([^"]+)"', html)
    dup = sorted({d for d in defs if defs.count(d) > 1})

    # href="#sym-x" 是图标引用；href="#/home" 是路由，不参与比对
    refs = {r for r in re.findall(r'href="#([^"]+)"', html) if not r.startswith("/")}
    missing = sorted(refs - set(defs))
    unused = sorted(set(defs) - refs)

    ids = set(re.findall(r'\bid="([^"]+)"', html))
    js_ids = set(re.findall(r"getElementById\(['\"]([^'\"]+)['\"]\)", js))
    js_missing = sorted(js_ids - ids)

    print(f"symbol    定义 {len(defs)}，引用 {len(refs)}")
    if dup:
        print(f"FAIL  重复定义：{', '.join(dup)}")
        bad += 1
    if missing:
        print(f"FAIL  引用不存在的 symbol：{', '.join(missing)}")
        bad += 1
    if unused:
        print(f"WARN  已定义但没人用：{', '.join(unused)}")

    # app.js 里可能引用了运行时才插入的节点，只提示不判失败
    if js_missing:
        print(f"WARN  app.js 取了 HTML 里不存在的 id：{', '.join(js_missing)}")

    print("OK" if not bad else f"失败 {bad} 项")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
