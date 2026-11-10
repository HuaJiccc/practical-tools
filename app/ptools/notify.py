"""Windows 通知。

WebView2 不实现网页版 Notification，所以通知由 Python 侧弹出：
生成一个临时 PowerShell 脚本调用系统的 Toast API。首次使用会注册一个
应用标识，让通知里显示产品名，而不是「Windows PowerShell」。

注：PowerShell 启动要一两百毫秒，所以只用在"到点了"这类低频场合。
"""

import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

APP_ID = "PersonalTools.DesktopApp"
DISPLAY_NAME = "个人工具"

_REG_KEY = r"Software\Classes\AppUserModelId"
_lock = threading.Lock()
_registered = None  # (app_id, icon) 记住上次注册过的组合

# 通知正文里要转义 XML 特殊字符，否则 PowerShell 的 XML 会解析失败
_XML_ESCAPES = (("&", "&amp;"), ("<", "&lt;"), (">", "&gt;"), ('"', "&quot;"), ("'", "&apos;"))


def _xml(text):
    out = str(text or "")
    for raw, safe in _XML_ESCAPES:
        out = out.replace(raw, safe)
    return out


def _ps_quote(text):
    """PowerShell 单引号字符串：内部单引号要写两遍。"""
    return "'" + str(text).replace("'", "''") + "'"


def register_app_id(icon_path=None):
    """把产品名与图标写进注册表，通知里就显示自己的名字。重复调用无害。"""
    global _registered
    if not sys.platform.startswith("win"):
        return False
    icon = str(icon_path or "")
    with _lock:
        if _registered == (APP_ID, icon):
            return True
    try:
        import winreg

        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _REG_KEY + "\\" + APP_ID) as key:
            winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, DISPLAY_NAME)
            if icon and Path(icon).exists():
                winreg.SetValueEx(key, "IconUri", 0, winreg.REG_SZ, icon)
        with _lock:
            _registered = (APP_ID, icon)
        return True
    except Exception:  # noqa: BLE001
        return False


def available():
    """这台机器能不能弹通知。"""
    if not sys.platform.startswith("win"):
        return False
    return bool(os.environ.get("SystemRoot"))


def _script(title, body, icon):
    icon_xml = ""
    if icon and Path(icon).exists():
        icon_xml = (
            '<image placement="appLogoOverride" hint-crop="circle" '
            'src="' + _xml(Path(icon).resolve().as_uri()) + '"/>'
        )
    return (
        "$ErrorActionPreference = 'Stop'\n"
        "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null\n"
        "[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom, ContentType = WindowsRuntime] | Out-Null\n"
        "$xml = @'\n"
        '<toast><visual><binding template="ToastGeneric">'
        + icon_xml
        + "<text>"
        + _xml(title)
        + "</text><text>"
        + _xml(body)
        + "</text></binding></visual></toast>\n"
        "'@\n"
        "$doc = New-Object Windows.Data.Xml.Dom.XmlDocument\n"
        "$doc.LoadXml($xml)\n"
        "try {\n"
        "  $toast = New-Object Windows.UI.Notifications.ToastNotification $doc\n"
        "  [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("
        + _ps_quote(APP_ID)
        + ").Show($toast)\n"
        "} catch {\n"
        "  # 应用标识还没注册时退回到 PowerShell 自己的名字\n"
        "  $toast = New-Object Windows.UI.Notifications.ToastNotification $doc\n"
        "  [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("
        + _ps_quote(DISPLAY_NAME)
        + ").Show($toast)\n"
        "}\n"
    )


def toast(title, body="", icon_path=None):
    """弹一个系统通知。交给系统就算成功，返回 True。"""
    if not available():
        return False
    register_app_id(icon_path)

    text = str(title or "").strip() or DISPLAY_NAME
    detail = str(body or "").strip()
    script = _script(text, detail, icon_path)

    path = None
    try:
        fd, path = tempfile.mkstemp(prefix="pt-toast-", suffix=".ps1")
        with os.fdopen(fd, "w", encoding="utf-8-sig") as handle:
            handle.write(script)
        subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy", "Bypass",
                "-WindowStyle", "Hidden",
                "-File", path,
            ],
            timeout=15,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except Exception:  # noqa: BLE001
        return False
    finally:
        if path:
            # PowerShell 进程刚退出时文件可能还被占着，删不掉就算了
            for _ in range(3):
                try:
                    os.unlink(path)
                    break
                except OSError:
                    time.sleep(0.1)
