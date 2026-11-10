"""v2.6 存储位置自测：数据目录切换 / 图片保存目录 / 默认值可用性。

要点：data_dir() 在 import 时就定死了，所以「切换是否真的生效」必须开子进程验，
同进程内怎么改都看不出来。
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "_data_dirs26"
if DATA.exists():
    shutil.rmtree(DATA, ignore_errors=True)
DATA.mkdir(parents=True, exist_ok=True)
os.environ["PERSONALTOOLS_DATA"] = str(DATA)
sys.path.insert(0, str(ROOT.parent / "app"))

from ptools.api import Api  # noqa: E402
from ptools.config import Settings, app_dir, data_dir  # noqa: E402
from ptools.store import History  # noqa: E402
from uistore import PrefsStore  # noqa: E402
import app as appmod  # noqa: E402

fails = []


def check(name, cond, detail=""):
    print(("PASS  " if cond else "FAIL  ") + name + (f"   {detail}" if detail else ""))
    if not cond:
        fails.append(name)


root = data_dir()
api = Api(settings=Settings(root / "settings.json"), history=History(root / "history.json", 300))
prefs = PrefsStore(DATA / "ui_prefs.json")
ui = appmod.UiApi(api, prefs=prefs)
config_file = appmod.data_dir_file()
temp_dirs = []

try:
    # ---- 1. 默认值 ----
    info = ui.dirs_info()
    check("dirs_info 可用", info.get("ok") is True, json.dumps(info, ensure_ascii=False)[:120])
    check("默认数据目录 = 当前数据目录", Path(info["data_dir"]).resolve() == root.resolve(), info["data_dir"])
    check("默认图片目录在数据目录下", Path(info["export_default"]).parent.resolve() == root.resolve())
    check("初始不显示为自定义", info["data_custom"] is False and info["export_custom"] is False)
    check("程序目录可写（能记住选择）", info["can_move_data"] is True)

    # ---- 2. 图片保存目录 ----
    pic = Path(tempfile.mkdtemp(prefix="pt_pics_"))
    temp_dirs.append(pic)
    res = ui.export_set_dir(str(pic))
    check("设置图片目录", res.get("ok") is True and Path(res["path"]) == pic, str(res.get("error", "")))
    saved = ui.image_save("t.png", "aGVsbG8=")
    check("图片写进新目录", saved.get("ok") is True and Path(saved["path"]).parent == pic, json.dumps(saved, ensure_ascii=False))
    check("新目录里确实有文件", (pic / "t.png").is_file())
    info = ui.dirs_info()
    check("界面能读到自定义状态", info["export_custom"] is True and Path(info["export_dir"]) == pic)
    res = ui.export_reset_dir()
    check("恢复默认图片目录", res.get("ok") is True and Path(res["path"]).parent.resolve() == root.resolve())
    check("恢复后状态回到默认", ui.dirs_info()["export_custom"] is False)

    # ---- 3. 非法目录要拒绝 ----
    fake = Path(tempfile.gettempdir()) / "pt_not_a_dir_$$" / "x"
    fake.parent.mkdir(parents=True, exist_ok=True)
    (fake.parent / "x").write_text("i am a file", encoding="utf-8")
    bad = ui.export_set_dir(str(fake))
    check("文件占位路径被拒绝", bad.get("ok") is False, str(bad.get("error", "")))
    check("拒绝后目录没被改", ui.dirs_info()["export_custom"] is False)

    # ---- 4. 数据目录切换 ----
    moved = Path(tempfile.mkdtemp(prefix="pt_data_"))
    temp_dirs.append(moved)
    res = ui.data_set_dir(str(moved))
    check("切换数据目录", res.get("ok") is True and res.get("restart") is True, str(res.get("error", "")))
    check("写了 data-dir.txt", config_file.is_file(), str(config_file))
    check("配置里是目标路径", appmod.read_data_override() == str(moved), appmod.read_data_override())
    check("搬了现有数据", res.get("copied", 0) >= 1, f"copied={res.get('copied')}")
    check("目标目录里有 json 记录", bool(list(moved.glob("*.json"))), str([p.name for p in moved.glob("*.json")]))
    check("webview 缓存没搬", not (moved / "webview").exists())

    same = ui.data_set_dir(str(data_dir()))
    check("选当前目录不要求重启", same.get("ok") is True and same.get("restart") is False)

    # ---- 5. 子进程验证真的生效 ----
    probe = (
        "import sys; sys.path.insert(0, r'%s');"
        "from ptools.config import data_dir; print(data_dir())" % (ROOT.parent / "app")
    )
    out = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True,
                         env={k: v for k, v in os.environ.items() if k != "PERSONALTOOLS_DATA"})
    got = Path(out.stdout.strip()) if out.stdout.strip() else None
    check("新进程用的是新目录", got is not None and got.resolve() == moved.resolve(),
          out.stdout.strip() or out.stderr.strip()[:120])

    # ---- 6. 恢复默认 ----
    res = ui.data_reset_dir()
    check("删除配置", res.get("ok") is True and res.get("restart") is True, str(res.get("error", "")))
    check("data-dir.txt 已删除", not config_file.exists())
    out2 = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True,
                          env={k: v for k, v in os.environ.items() if k != "PERSONALTOOLS_DATA"})
    got2 = Path(out2.stdout.strip()) if out2.stdout.strip() else None
    default_dir = app_dir() / "data"
    check("恢复后新进程回到默认", got2 is not None and got2.resolve() == default_dir.resolve(),
          out2.stdout.strip() or out2.stderr.strip()[:120])

    # ---- 7. 注释与坏文件 ----
    config_file.write_text("# 注释行\n\n   " + str(moved) + "  \n", encoding="utf-8")
    check("跳过注释和空行", appmod.read_data_override() == str(moved), appmod.read_data_override())
    config_file.write_text("", encoding="utf-8")
    check("空文件当没设置", appmod.read_data_override() == "")
finally:
    if config_file.exists():
        config_file.unlink()
    for d in temp_dirs:
        shutil.rmtree(d, ignore_errors=True)
    shutil.rmtree(DATA, ignore_errors=True)

print()
print(f"{'全部通过' if not fails else '失败 ' + str(len(fails)) + ' 项：' + ', '.join(fails)}")
sys.exit(0 if not fails else 1)
