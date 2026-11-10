"""系统托盘（纯 ctypes，不依赖 pystray / PIL）。

pywebview 本身没有托盘能力，这里用 Shell_NotifyIcon 自己建一个：
隐藏窗口 + 独立消息循环线程，左键单击/双击恢复窗口，右键弹菜单。

只支持 Windows，其它平台 start() 直接返回 False。
"""

import ctypes
import threading
import traceback
from ctypes import wintypes

WM_APP = 0x8000
WM_TRAY = WM_APP + 20
WM_COMMAND = 0x0111
WM_DESTROY = 0x0002
WM_LBUTTONUP = 0x0202
WM_LBUTTONDBLCLK = 0x0203
WM_RBUTTONUP = 0x0205
WM_CONTEXTMENU = 0x007B

NIM_ADD = 0x00000000
NIM_MODIFY = 0x00000001
NIM_DELETE = 0x00000002
NIF_MESSAGE = 0x00000001
NIF_ICON = 0x00000002
NIF_TIP = 0x00000004
NIF_INFO = 0x00000010
NIIF_INFO = 0x00000001

IMAGE_ICON = 1
LR_LOADFROMFILE = 0x00000010
LR_DEFAULTSIZE = 0x00000040

MF_STRING = 0x00000000
MF_SEPARATOR = 0x00000800
MF_GRAYED = 0x00000001
MF_DEFAULT = 0x00001000

TPM_RIGHTBUTTON = 0x0002
TPM_RETURNCMD = 0x0100
TPM_NONOTIFY = 0x0080

LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

_APIS_READY = False


def _declare():
    """显式声明签名。不声明的话 ctypes 默认按 32 位 int 传参，
    64 位下句柄/指针会被截断（DefWindowProcW 的 lparam 就会抛 OverflowError）。"""
    global _APIS_READY
    if _APIS_READY:
        return
    u = ctypes.windll.user32
    u.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    u.DefWindowProcW.restype = LRESULT
    u.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASS)]
    u.RegisterClassW.restype = wintypes.ATOM if hasattr(wintypes, "ATOM") else wintypes.WORD
    u.CreateWindowExW.argtypes = [
        wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID,
    ]
    u.CreateWindowExW.restype = wintypes.HWND
    u.DestroyWindow.argtypes = [wintypes.HWND]
    u.DestroyWindow.restype = wintypes.BOOL
    u.LoadImageW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT, ctypes.c_int, ctypes.c_int, wintypes.UINT]
    u.LoadImageW.restype = wintypes.HANDLE
    u.LoadIconW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR]
    u.LoadIconW.restype = wintypes.HICON
    u.CreatePopupMenu.restype = wintypes.HMENU
    u.AppendMenuW.argtypes = [wintypes.HMENU, wintypes.UINT, ctypes.c_size_t, wintypes.LPCWSTR]
    u.AppendMenuW.restype = wintypes.BOOL
    u.TrackPopupMenu.argtypes = [wintypes.HMENU, wintypes.UINT, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.HWND, wintypes.LPVOID]
    u.TrackPopupMenu.restype = ctypes.c_int  # TPM_RETURNCMD 时返回菜单 ID
    u.DestroyMenu.argtypes = [wintypes.HMENU]
    u.SetForegroundWindow.argtypes = [wintypes.HWND]
    u.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
    u.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    u.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    u.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
    u.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
    u.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
    u.DispatchMessageW.restype = LRESULT
    s = ctypes.windll.shell32
    s.Shell_NotifyIconW.argtypes = [wintypes.DWORD, ctypes.POINTER(NOTIFYICONDATA)]
    s.Shell_NotifyIconW.restype = wintypes.BOOL
    k = ctypes.windll.kernel32
    k.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
    k.GetModuleHandleW.restype = wintypes.HINSTANCE
    k.GetCurrentThreadId.restype = wintypes.DWORD
    _APIS_READY = True


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_byte * 8),
    ]


class NOTIFYICONDATA(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("hWnd", wintypes.HWND),
        ("uID", wintypes.UINT),
        ("uFlags", wintypes.UINT),
        ("uCallbackMessage", wintypes.UINT),
        ("hIcon", wintypes.HICON),
        ("szTip", wintypes.WCHAR * 128),
        ("dwState", wintypes.DWORD),
        ("dwStateMask", wintypes.DWORD),
        ("szInfo", wintypes.WCHAR * 256),
        ("uVersion", wintypes.UINT),
        ("szInfoTitle", wintypes.WCHAR * 64),
        ("dwInfoFlags", wintypes.DWORD),
        ("guidItem", GUID),
        ("hBalloonIcon", wintypes.HICON),
    ]


class WNDCLASS(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", ctypes.c_void_p),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
    ]


class Tray:
    """托盘图标。

    menu 是 [(cmd, 文案), ...]，cmd 为 None 时是分隔线。
    on_command(cmd) 在托盘线程里被调用，调用方自己负责切回 UI 线程。
    """

    CLASS_NAME = "PracticalToolsTrayWnd"

    def __init__(self, title, icon_file, menu, on_command, on_show):
        self.title = title
        self.icon_file = icon_file
        self.menu = menu
        self.on_command = on_command
        self.on_show = on_show
        self.hwnd = None
        self.hicon = None
        self._ready = threading.Event()
        self._thread = None
        self._thread_id = None
        self._running = False
        self._icon_added = False
        self._wndproc = WNDPROC(self._on_message)

    # ---------- 对外 ----------

    def start(self, timeout=3.0):
        if not hasattr(ctypes, "windll"):
            return False
        _declare()
        self._thread = threading.Thread(target=self._run, name="pt-tray", daemon=True)
        self._thread.start()
        return self._ready.wait(timeout) and self._icon_added

    def stop(self):
        """移除图标并结束循环。可重复调用。"""
        self._running = False
        try:
            if self._icon_added and self.hwnd:
                data = self._data()
                ctypes.windll.shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(data))
                self._icon_added = False
        except Exception:
            pass
        try:
            if self._thread_id:
                ctypes.windll.user32.PostThreadMessageW(self._thread_id, 0x0012, 0, 0)  # WM_QUIT
        except Exception:
            pass

    def set_tooltip(self, text):
        self.title = text or self.title
        if not self._icon_added:
            return False
        try:
            data = self._data()
            data.uFlags = NIF_TIP
            return bool(ctypes.windll.shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(data)))
        except Exception:
            return False

    def balloon(self, title, text):
        if not self._icon_added:
            return False
        try:
            data = self._data()
            data.uFlags = NIF_INFO
            data.szInfo = (text or "")[:250]
            data.szInfoTitle = (title or "")[:60]
            data.dwInfoFlags = NIIF_INFO
            return bool(ctypes.windll.shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(data)))
        except Exception:
            return False

    # ---------- 内部 ----------

    def _data(self):
        data = NOTIFYICONDATA()
        data.cbSize = ctypes.sizeof(NOTIFYICONDATA)
        data.hWnd = self.hwnd
        data.uID = 1
        data.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        data.uCallbackMessage = WM_TRAY
        data.hIcon = self.hicon or 0
        data.szTip = (self.title or "")[:120]
        return data

    def _load_icon(self):
        user32 = ctypes.windll.user32
        if self.icon_file:
            for size in (0, 16):
                handle = user32.LoadImageW(
                    None, self.icon_file, IMAGE_ICON, size, size,
                    LR_LOADFROMFILE | (LR_DEFAULTSIZE if size == 0 else 0),
                )
                if handle:
                    return handle
        # 退路：exe 自身图标
        return user32.LoadIconW(None, ctypes.cast(32512, wintypes.LPCWSTR))

    def _menu_command(self):
        """弹出右键菜单，返回被点中的命令 id。"""
        user32 = ctypes.windll.user32
        menu = user32.CreatePopupMenu()
        if not menu:
            return 0
        ids = {}
        for index, (cmd, label) in enumerate(self.menu):
            if cmd is None:
                user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
                continue
            item_id = 1000 + index
            ids[item_id] = cmd
            user32.AppendMenuW(menu, MF_STRING, item_id, label)
        # 不带 TPM_RETURNCMD 的话拿不到选择结果
        user32.SetForegroundWindow(self.hwnd)
        point = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(point))
        chosen = user32.TrackPopupMenu(
            menu, TPM_RIGHTBUTTON | TPM_RETURNCMD | TPM_NONOTIFY,
            point.x, point.y, 0, self.hwnd, None,
        )
        user32.PostMessageW(self.hwnd, 0x0000, 0, 0)  # WM_NULL，收掉残留菜单
        user32.DestroyMenu(menu)
        return ids.get(chosen, 0)

    def _on_message(self, hwnd, msg, wparam, lparam):
        try:
            if msg == WM_TRAY:
                event = lparam & 0xFFFF
                if event in (WM_LBUTTONUP, WM_LBUTTONDBLCLK):
                    self.on_show()
                elif event in (WM_RBUTTONUP, WM_CONTEXTMENU):
                    cmd = self._menu_command()
                    if cmd:
                        self.on_command(cmd)
                return 0
            if msg == WM_DESTROY:
                ctypes.windll.user32.PostQuitMessage(0)
                return 0
        except Exception:
            traceback.print_exc()
        return ctypes.windll.user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _run(self):
        try:
            _declare()
            kernel32 = ctypes.windll.kernel32
            user32 = ctypes.windll.user32
            self._thread_id = kernel32.GetCurrentThreadId()

            hinst = kernel32.GetModuleHandleW(None)
            wc = WNDCLASS()
            wc.lpfnWndProc = self._wndproc
            wc.hInstance = hinst
            wc.lpszClassName = self.CLASS_NAME
            user32.RegisterClassW(ctypes.byref(wc))

            self.hwnd = user32.CreateWindowExW(
                0, self.CLASS_NAME, self.title, 0, 0, 0, 0, 0, None, None, hinst, None
            )
            if not self.hwnd:
                self._ready.set()
                return

            self.hicon = self._load_icon()
            self._running = True

            data = self._data()
            self._icon_added = bool(ctypes.windll.shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(data)))
            self._ready.set()

            msg = wintypes.MSG()
            while self._running and user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
        except Exception:
            traceback.print_exc()
            self._ready.set()
        finally:
            if self.hwnd:
                try:
                    ctypes.windll.user32.DestroyWindow(self.hwnd)
                except Exception:
                    pass
            self.hwnd = None
