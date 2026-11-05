"""
Win32 API utilities for BreakTimer Ultra.
Provides robust window layering, force-foreground acquisition, and virtual screen geometry
to ensure break windows NEVER get hidden behind fullscreen applications (games, videos, F11, etc.).
"""

import ctypes
from ctypes import wintypes
from typing import Tuple

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# Constants
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
HWND_TOP = 0

SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOREDRAW = 0x0008
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020
SWP_SHOWWINDOW = 0x0040

GWL_EXSTYLE = -20
WS_EX_TOPMOST = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_LAYERED = 0x00080000
WS_EX_NOACTIVATE = 0x08000000

GA_ROOT = 2

SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79

# Set function signatures
user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
user32.GetAncestor.restype = wintypes.HWND

user32.GetForegroundWindow.argtypes = []
user32.GetForegroundWindow.restype = wintypes.HWND

user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD

kernel32.GetCurrentThreadId.argtypes = []
kernel32.GetCurrentThreadId.restype = wintypes.DWORD

user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
user32.AttachThreadInput.restype = wintypes.BOOL

user32.BringWindowToTop.argtypes = [wintypes.HWND]
user32.BringWindowToTop.restype = wintypes.BOOL

user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.SetForegroundWindow.restype = wintypes.BOOL

user32.SetWindowPos.argtypes = [
    wintypes.HWND,
    wintypes.HWND,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.UINT,
]
user32.SetWindowPos.restype = wintypes.BOOL

user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetWindowLongW.restype = wintypes.LONG

user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.LONG]
user32.SetWindowLongW.restype = wintypes.LONG

user32.GetSystemMetrics.argtypes = [ctypes.c_int]
user32.GetSystemMetrics.restype = ctypes.c_int

user32.IsWindow.argtypes = [wintypes.HWND]
user32.IsWindow.restype = wintypes.BOOL


def get_root_hwnd(hwnd: int) -> int:
    """Get the true top-level root HWND for a given window handle."""
    if not hwnd:
        return 0
    root = user32.GetAncestor(hwnd, GA_ROOT)
    return root if root else hwnd


def get_virtual_screen_geometry() -> Tuple[int, int, int, int]:
    """
    Returns (x, y, width, height) covering all connected monitors combined.
    Handles multi-monitor configurations with negative coordinate offsets.
    """
    x = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
    y = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
    w = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
    h = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
    # Fallback to primary screen if virtual screen metrics are invalid
    if w <= 0 or h <= 0:
        w = user32.GetSystemMetrics(0)  # SM_CXSCREEN
        h = user32.GetSystemMetrics(1)  # SM_CYSCREEN
        x = 0
        y = 0
    return x, y, w, h


def apply_overlay_styles(hwnd: int) -> None:
    """
    Applies extended window styles so the window behaves as a system overlay:
    - WS_EX_TOPMOST: Keep in top-most Z-order band
    - WS_EX_TOOLWINDOW: Don't show in Alt+Tab or taskbar clutter
    """
    root_hwnd = get_root_hwnd(hwnd)
    if not root_hwnd or not user32.IsWindow(root_hwnd):
        return

    cur_style = user32.GetWindowLongW(root_hwnd, GWL_EXSTYLE)
    new_style = cur_style | WS_EX_TOPMOST | WS_EX_TOOLWINDOW
    user32.SetWindowLongW(root_hwnd, GWL_EXSTYLE, new_style)


def force_window_to_top(hwnd: int, take_focus: bool = True) -> None:
    """
    Forcefully raises the window to the very top of the Z-order,
    even bypassing Windows' foreground lock and overriding fullscreen games/videos.
    """
    root_hwnd = get_root_hwnd(hwnd)
    if not root_hwnd or not user32.IsWindow(root_hwnd):
        return

    # 1. Ensure TopMost style
    apply_overlay_styles(root_hwnd)

    # 2. Place in TopMost Z-order
    user32.SetWindowPos(
        root_hwnd,
        HWND_TOPMOST,
        0, 0, 0, 0,
        SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW
    )

    if take_focus:
        # 3. Bypass Windows foreground-lock by attaching thread input
        fore_hwnd = user32.GetForegroundWindow()
        cur_thread = kernel32.GetCurrentThreadId()
        fore_thread = user32.GetWindowThreadProcessId(fore_hwnd, None) if fore_hwnd else 0

        attached = False
        if fore_thread and fore_thread != cur_thread:
            attached = user32.AttachThreadInput(fore_thread, cur_thread, True)

        try:
            user32.BringWindowToTop(root_hwnd)
            user32.SetForegroundWindow(root_hwnd)
        finally:
            if attached:
                user32.AttachThreadInput(fore_thread, cur_thread, False)

    # 4. Final top-most assertion
    user32.SetWindowPos(
        root_hwnd,
        HWND_TOPMOST,
        0, 0, 0, 0,
        SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW
    )


def maintain_topmost(hwnd: int) -> None:
    """
    Fast, lightweight call to re-assert HWND_TOPMOST position without stealing focus or flashing.
    Intended to be called repeatedly (e.g. every 100-200ms) while break is active.
    """
    root_hwnd = get_root_hwnd(hwnd)
    if not root_hwnd or not user32.IsWindow(root_hwnd):
        return

    user32.SetWindowPos(
        root_hwnd,
        HWND_TOPMOST,
        0, 0, 0, 0,
        SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW
    )


# Mutex and instance management
ERROR_ALREADY_EXISTS = 183
SW_RESTORE = 9

kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
kernel32.CreateMutexW.restype = wintypes.HANDLE

kernel32.GetLastError.argtypes = []
kernel32.GetLastError.restype = wintypes.DWORD

kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL

kernel32.ReleaseMutex.argtypes = [wintypes.HANDLE]
kernel32.ReleaseMutex.restype = wintypes.BOOL

user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
user32.FindWindowW.restype = wintypes.HWND

user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.ShowWindow.restype = wintypes.BOOL

_app_mutex_handle = None


def acquire_single_instance(mutex_name: str = "BreakTimerUltra_SingleInstance_Mutex") -> bool:
    """
    Ensures only a single instance of BreakTimer Ultra runs at a time.
    Returns True if this is the only instance, or False if another instance is already running.
    """
    global _app_mutex_handle
    _app_mutex_handle = kernel32.CreateMutexW(None, True, mutex_name)
    last_error = kernel32.GetLastError()
    if last_error == ERROR_ALREADY_EXISTS:
        return False
    return True


def release_single_instance() -> None:
    """
    Releases and closes the singleton mutex handle so another instance can acquire it.
    Must be called before retrying acquire_single_instance.
    """
    global _app_mutex_handle
    if _app_mutex_handle:
        try:
            kernel32.ReleaseMutex(_app_mutex_handle)
        except Exception:
            pass
        try:
            kernel32.CloseHandle(_app_mutex_handle)
        except Exception:
            pass
        _app_mutex_handle = None


def activate_existing_instance(window_title: str = "BreakTimer Ultra — 20-20-20 ルール休憩タイマー") -> bool:
    """Finds and brings the existing instance's window to the foreground."""
    hwnd = user32.FindWindowW(None, window_title)
    if hwnd:
        user32.ShowWindow(hwnd, SW_RESTORE)
        user32.SetForegroundWindow(hwnd)
        return True
    return False


# Media key simulation
VK_MEDIA_PLAY_PAUSE = 0xB3
KEYEVENTF_KEYUP = 0x0002

user32.keybd_event.argtypes = [wintypes.BYTE, wintypes.BYTE, wintypes.DWORD, ctypes.c_void_p]
user32.keybd_event.restype = None


def send_media_play_pause() -> None:
    """
    Simulates pressing the Windows Media Play/Pause key.
    Pauses or resumes playing video in Netflix, YouTube, browser, or media player.
    """
    user32.keybd_event(VK_MEDIA_PLAY_PAUSE, 0, 0, 0)
    user32.keybd_event(VK_MEDIA_PLAY_PAUSE, 0, KEYEVENTF_KEYUP, 0)


# System Idle / Activity tracking
class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.UINT),
        ("dwTime", wintypes.DWORD),
    ]


user32.GetLastInputInfo.argtypes = [ctypes.POINTER(LASTINPUTINFO)]
user32.GetLastInputInfo.restype = wintypes.BOOL

kernel32.GetTickCount.argtypes = []
kernel32.GetTickCount.restype = wintypes.DWORD


def get_system_idle_seconds() -> float:
    """
    Returns the time in seconds since the last keyboard or mouse input.
    Useful for detecting user idle / away from keyboard state.
    """
    lii = LASTINPUTINFO()
    lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
    if user32.GetLastInputInfo(ctypes.byref(lii)):
        # Handle 32-bit unsigned overflow wrapping of GetTickCount (after ~49.7 days)
        current_tick = kernel32.GetTickCount()
        elapsed_ms = (current_tick - lii.dwTime) & 0xFFFFFFFF
        return max(0.0, float(elapsed_ms) / 1000.0)
    return 0.0



