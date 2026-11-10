"""网络状态检测。

先问 Windows 自己有没有连上网（瞬间返回），再偶尔用一次短超时的 TCP 探测
确认真的能出去 —— 有些网络会谎报"已连接"（连上了 WiFi 但网关不通）。
结果缓存 ``CHECK_TTL`` 秒，避免每次调用都去探测。

纯本地功能不依赖这里；只有翻译、汇率这些需要联网的地方才会问。
"""

import ctypes
import socket
import threading
import time

CHECK_TTL = 20.0
PROBE_TIMEOUT = 1.6
PROBE_HOSTS = (("223.5.5.5", 443), ("119.29.29.29", 443), ("223.6.6.6", 443))
OFFLINE_HINT = "当前没有网络连接，这个功能需要联网；其他本地功能不受影响"

_lock = threading.Lock()
_cached = {"online": True, "at": 0.0, "checked": False}
_forced = None


def _windows_says_online():
    """Windows 的"已连接"标志：快，但可能不准。"""
    try:
        wininet = ctypes.windll.wininet
        flags = ctypes.c_uint32(0)
        # INTERNET_CONNECTED = 0x01 之外的标志位不关心，只要问通不通
        return bool(wininet.InternetGetConnectedState(ctypes.byref(flags), 0))
    except Exception:  # noqa: BLE001 - 非 Windows 或调用失败就当没连
        return True


def _probe():
    """真的去连一下 DNS 服务器的 443 端口。能连上就算在线。"""
    for host, port in PROBE_HOSTS:
        try:
            with socket.create_connection((host, port), timeout=PROBE_TIMEOUT):
                return True
        except OSError:
            continue
    return False


def online(force=False):
    """当前是否能访问外网。结果缓存 CHECK_TTL 秒。"""
    global _cached
    if _forced is not None:
        return bool(_forced)

    now = time.time()
    with _lock:
        if not force and _cached["checked"] and now - _cached["at"] < CHECK_TTL:
            return bool(_cached["online"])
        reachable = _windows_says_online() and _probe()
        _cached = {"online": reachable, "at": now, "checked": True}
        return reachable


def snapshot():
    """给界面用的完整状态：是否在线、什么时候查的、是不是被强制指定过。"""
    value = online()
    with _lock:
        return {
            "online": bool(value),
            "checked_at": _cached["at"],
            "ttl": CHECK_TTL,
            "forced": _forced,
            "hint": "" if value else OFFLINE_HINT,
        }


def set_forced(value):
    """测试用：强制在线/离线，传 None 恢复真实探测。"""
    global _forced, _cached
    _forced = None if value is None else bool(value)
    with _lock:
        _cached = {"online": bool(_forced) if _forced is not None else True,
                   "at": 0.0, "checked": False}
    return _forced
