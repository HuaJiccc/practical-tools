"""卸载流程自测：走一遍卸载向导，确认数据默认保留。

前提：已经用 dev_installer_shots.py 或安装包装过一次。
用法：python dev/dev_uninstall_test.py "D:\\测试安装目录"
"""

import ctypes
import ctypes.wintypes as wt
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from shot_util import find, shot  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SHOTS = ROOT / "dev" / "_shots" / "v30"
user32 = ctypes.windll.user32

VK_RETURN = 0x0D
VK_MENU = 0x12
VK_Y = 0x59


def key(vk=VK_RETURN):
    user32.keybd_event(vk, 0, 0, 0)
    time.sleep(0.06)
    user32.keybd_event(vk, 0, 2, 0)
    time.sleep(1.2)


def alt_key(vk):
    """Alt + 字母，命中「是(Y)」这类加速键。确认框默认停在「否」，回车等于取消。"""
    user32.keybd_event(VK_MENU, 0, 0, 0)
    time.sleep(0.05)
    user32.keybd_event(vk, 0, 0, 0)
    time.sleep(0.05)
    user32.keybd_event(vk, 0, 2, 0)
    user32.keybd_event(VK_MENU, 0, 2, 0)
    time.sleep(1.2)


def foreground(hwnd):
    tid = user32.GetWindowThreadProcessId(hwnd, None)
    fg = user32.GetForegroundWindow()
    ftid = user32.GetWindowThreadProcessId(fg, None)
    if tid != ftid:
        user32.AttachThreadInput(ftid, tid, True)
        user32.SetForegroundWindow(hwnd)
        user32.AttachThreadInput(ftid, tid, False)
    else:
        user32.SetForegroundWindow(hwnd)
    time.sleep(0.3)


def wait_window(title_part, timeout=20):
    deadline = time.time() + timeout
    while time.time() < deadline:
        hwnd = find(title_part)
        if hwnd:
            return hwnd
        time.sleep(0.4)
    return None


def all_windows(title_part):
    found = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def cb(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        n = user32.GetWindowTextLengthW(hwnd)
        if n:
            buf = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, buf, n + 1)
            if title_part in buf.value:
                found.append(hwnd)
        return True

    user32.EnumWindows(cb, 0)
    return found


def child_text(hwnd):
    """把窗口里所有子控件的文字拼起来，用来判断当前是哪种对话框。"""
    parts = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def cb(child, _):
        n = user32.GetWindowTextLengthW(child)
        if n:
            buf = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(child, buf, n + 1)
            if buf.value.strip():
                parts.append(buf.value.strip())
        return True

    user32.EnumChildWindows(hwnd, cb, 0)
    return " | ".join(parts)


def wait_confirm(timeout=15):
    """等「是否一并删除个人数据」这个确认框。卸载进度页标题相同，靠正文区分。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        for hwnd in all_windows("实用工具 卸载"):
            if "个人数据" in child_text(hwnd):
                return hwnd
        time.sleep(0.4)
    return None


def main():
    target = Path(sys.argv[1] if len(sys.argv) > 1 else r"D:\_pt_install_test")
    unins = target / "unins000.exe"
    if not unins.exists():
        print("没有卸载程序:", unins)
        return 1
    data_dir = Path.home() / "AppData" / "Local" / "实用工具" / "data"
    before = data_dir.exists()

    proc = subprocess.Popen([str(unins)])
    hwnd = wait_window("实用工具 卸载")
    if not hwnd:
        print("卸载窗口没有出现")
        proc.kill()
        return 1
    print("卸载向导已弹出")
    foreground(hwnd)
    time.sleep(0.6)
    SHOTS.mkdir(parents=True, exist_ok=True)
    shot(hwnd, SHOTS / "uninstall_1.png")

    alt_key(VK_Y)  # 「是」→ 真正开始卸载
    time.sleep(1.0)
    box = wait_confirm(timeout=15)
    if box:
        shot(box, SHOTS / "uninstall_2_data.png")
        print("已截到「是否一并删除个人数据」确认框")
        key()  # 默认按钮是「否」= 保留数据
    else:
        print("没等到数据确认框")

    for _ in range(45):
        time.sleep(1)
        if not (target / "实用工具.exe").exists():
            break
    still_exe = (target / "实用工具.exe").exists()
    print("主程序已移除:", not still_exe)
    leftovers = sorted(p.name for p in target.iterdir()) if target.exists() else []
    print("安装目录残留:", leftovers or "无（目录已删除）")
    after = data_dir.exists()
    print("数据目录仍在:", after, "| 路径:", data_dir)
    if after:
        print("数据内容:", sorted(p.name for p in data_dir.iterdir())[:8])
    print("结论: 卸载默认保留数据 =", bool(after or not before))
    return 0 if not still_exe else 1


if __name__ == "__main__":
    sys.exit(main())
