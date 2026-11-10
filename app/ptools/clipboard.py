"""Win32 剪贴板读写。

WebView2 从 file:// 源写剪贴板需要用户手势，界面上没有手势的场合
（比如点一下按钮就复制）会被拒。所以退回到这两个函数。
"""

import ctypes
import ctypes.wintypes as wt

CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

user32.OpenClipboard.argtypes = [wt.HWND]
user32.OpenClipboard.restype = wt.BOOL
user32.CloseClipboard.restype = wt.BOOL
user32.EmptyClipboard.restype = wt.BOOL
user32.GetClipboardData.argtypes = [wt.UINT]
user32.GetClipboardData.restype = wt.HANDLE
user32.SetClipboardData.argtypes = [wt.UINT, wt.HANDLE]
user32.SetClipboardData.restype = wt.HANDLE

kernel32.GlobalAlloc.argtypes = [wt.UINT, ctypes.c_size_t]
kernel32.GlobalAlloc.restype = wt.HGLOBAL
kernel32.GlobalLock.argtypes = [wt.HGLOBAL]
kernel32.GlobalLock.restype = ctypes.c_void_p
kernel32.GlobalUnlock.argtypes = [wt.HGLOBAL]
kernel32.GlobalFree.argtypes = [wt.HGLOBAL]
kernel32.RtlMoveMemory.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t]


def write_text(text):
    """把文本放进剪贴板。失败返回 False，不抛异常。"""
    data = str(text or "")
    payload = data.encode("utf-16-le") + b"\x00\x00"
    handle = None
    try:
        if not user32.OpenClipboard(None):
            return False
        try:
            user32.EmptyClipboard()
            handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(payload))
            if not handle:
                return False
            ptr = kernel32.GlobalLock(handle)
            if not ptr:
                return False
            try:
                kernel32.RtlMoveMemory(ptr, payload, len(payload))
            finally:
                kernel32.GlobalUnlock(handle)
            if not user32.SetClipboardData(CF_UNICODETEXT, handle):
                return False
            handle = None  # 交给系统了，不能自己释放
            return True
        finally:
            user32.CloseClipboard()
    except Exception:  # noqa: BLE001
        return False
    finally:
        if handle:
            try:
                kernel32.GlobalFree(handle)
            except Exception:  # noqa: BLE001
                pass


def read_text():
    """从剪贴板取文本，取不到返回空串。"""
    try:
        if not user32.OpenClipboard(None):
            return ""
        try:
            handle = user32.GetClipboardData(CF_UNICODETEXT)
            if not handle:
                return ""
            ptr = kernel32.GlobalLock(handle)
            if not ptr:
                return ""
            try:
                return ctypes.wstring_at(ptr)
            finally:
                kernel32.GlobalUnlock(handle)
        finally:
            user32.CloseClipboard()
    except Exception:  # noqa: BLE001
        return ""
