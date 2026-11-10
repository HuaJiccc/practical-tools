"""v2.5 设置页后端接口自测：开机自启 / 占用统计 / 备份 / 诊断。"""
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "_data_set25"
if DATA.exists():
    import shutil
    shutil.rmtree(DATA, ignore_errors=True)
DATA.mkdir(parents=True, exist_ok=True)
os.environ["PERSONALTOOLS_DATA"] = str(DATA)
sys.path.insert(0, str(ROOT.parent / "app"))

from ptools.api import Api  # noqa: E402
from ptools.config import Settings, data_dir  # noqa: E402
from ptools.store import History  # noqa: E402
import app as appmod  # noqa: E402

fails = []
def check(name, cond, detail=""):
    print(("PASS  " if cond else "FAIL  ") + name + (f"   {detail}" if detail else ""))
    if not cond:
        fails.append(name)

root = data_dir()
api = Api(settings=Settings(root / "settings.json"), history=History(root / "history.json", 300))
ui = appmod.UiApi(api)

# ---- 开机自启 ----
before = ui.sys_autostart()
check("自启状态可读", before.get("ok") is True, json.dumps(before, ensure_ascii=False))
orig = bool(before.get("enabled"))
if before.get("ok"):
    on = ui.sys_autostart(True)
    check("开启自启", on.get("ok") and on.get("enabled") is True, str(on.get("error", "")))
    reread = ui.sys_autostart()
    check("开机能读回", reread.get("enabled") is True)
    off = ui.sys_autostart(False)
    check("关闭自启", off.get("ok") and off.get("enabled") is False, str(off.get("error", "")))
    reread2 = ui.sys_autostart()
    check("关闭能读回", reread2.get("enabled") is False)
    if orig:
        ui.sys_autostart(True)
        print("      （原本是开启状态，已恢复）")

# ---- 造点数据再统计 ----
(root / "notes.json").write_text(json.dumps([{"id": "n1", "text": "x" * 2000}], ensure_ascii=False), "utf-8")
(root / "todo_data.json").write_text(json.dumps({"items": [{"id": "t1", "title": "y" * 3000}]}, ensure_ascii=False), "utf-8")
exp = root / "exports"
exp.mkdir(parents=True, exist_ok=True)
(exp / "a.png").write_bytes(b"\x89PNG" + b"0" * 5000)

stats = ui.data_stats()
check("占用统计 ok", stats.get("ok") is True)
check("占用总量 > 8KB", stats.get("total", 0) > 8000, f"{stats.get('total')} B / {stats.get('files')} 个")
names = [r["name"] for r in stats.get("rows", [])]
check("统计里有 notes / todo_data", "notes" in names and "todo_data" in names, str(names))
check("导出目录计数", stats.get("exports", {}).get("count") == 1, str(stats.get("exports")))
check("导出体积", stats.get("exports", {}).get("size", 0) > 5000, str(stats.get("exports", {}).get("size")))

# ---- 备份 ----
bak = ui.data_backup()
check("备份成功", bak.get("ok") is True, str(bak.get("error", "")))
if bak.get("ok"):
    target = Path(bak["path"])
    check("备份目录在 data/backup 下", target.parent == root / "backup", str(target))
    files = sorted(p.name for p in target.iterdir())
    check("备份含 json 文件", "notes.json" in files and "todo_data.json" in files, str(files))
    check("计数一致", bak.get("count") == len(files), f"{bak.get('count')} vs {len(files)}")

# ---- 诊断 ----
diag = ui.diag_info()
check("诊断 ok", diag.get("ok") is True)
text = diag.get("text", "")
for token in ("个人工具", "WebView2", "数据目录", "AI 接口"):
    check(f"诊断含「{token}」", token in text)
check("诊断不含明文 key", "sk-" not in text)

# ---- 打开说明（只测错误分支，避免真弹窗）----
guide = ui.open_guide()
print("     open_guide ->", json.dumps(guide, ensure_ascii=False))

print()
print(f"合计 {len(fails)} 项失败" if fails else "全部通过")
sys.exit(1 if fails else 0)
