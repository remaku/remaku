from dataclasses import dataclass
from typing import Any

import pygetwindow as gw
import win32api
import win32con
import win32gui
import win32process
import win32security
from loguru import logger


@dataclass(slots=True)
class Rect:
    left: int
    top: int
    width: int
    height: int

    @property
    def right(self) -> int:
        return self.left + self.width

    @property
    def bottom(self) -> int:
        return self.top + self.height


def list_visible_windows() -> list[str]:
    return sorted({window.title for window in gw.getAllWindows() if window.title.strip() and window.visible})


def find_target_window(title: str = "") -> Any | None:
    if not title:
        window = gw.getActiveWindow()

        if window:
            return window

        logger.debug("window: no foreground window found")
        return None

    windows = [window for window in gw.getWindowsWithTitle(title) if window.title and window.visible]

    if windows:
        windows.sort(key=lambda item: item.width * item.height, reverse=True)
        logger.trace("window: found '{}' ({}x{})", windows[0].title, windows[0].width, windows[0].height)
        return windows[0]

    logger.debug("window: no matching window (title='{}')", title)
    return None


def client_rect(window: Any) -> Rect:
    hwnd = window._hWnd
    left, top, right, bottom = win32gui.GetClientRect(hwnd)
    screen_x, screen_y = win32gui.ClientToScreen(hwnd, (left, top))

    return Rect(left=screen_x, top=screen_y, width=right - left, height=bottom - top)


def is_foreground(window: Any) -> bool:
    try:
        return win32gui.GetForegroundWindow() == window._hWnd
    except Exception:
        return False


def fake_focus(window: Any) -> None:
    hwnd = window._hWnd

    win32gui.PostMessage(hwnd, win32con.WM_ACTIVATEAPP, True, 0)
    win32gui.PostMessage(hwnd, win32con.WM_NCACTIVATE, True, 0)
    win32gui.PostMessage(hwnd, win32con.WM_ACTIVATE, win32con.WA_ACTIVE, 0)
    win32gui.PostMessage(hwnd, win32con.WM_SETFOCUS, 0, 0)


def is_self_elevated() -> bool:
    try:
        token = win32security.OpenProcessToken(
            win32api.GetCurrentProcess(),
            win32con.TOKEN_QUERY,
        )
        try:
            elevation = win32security.GetTokenInformation(token, win32security.TokenElevation)
            return bool(elevation)
        finally:
            win32api.CloseHandle(token)
    except Exception:
        return False


def check_elevation_mismatch(window: Any) -> bool:
    if is_self_elevated():
        return False

    try:
        _, pid = win32process.GetWindowThreadProcessId(window._hWnd)
        process_handle = win32api.OpenProcess(win32con.PROCESS_QUERY_LIMITED_INFORMATION, False, pid)

        try:
            token_handle = win32security.OpenProcessToken(process_handle, win32con.TOKEN_QUERY)
            elevation = win32security.GetTokenInformation(token_handle, win32security.TokenElevation)
            win32api.CloseHandle(token_handle)

            if elevation:
                logger.warning("window: elevation mismatch detected, SendInput cannot reach target window")
                return True
        finally:
            win32api.CloseHandle(process_handle)
    except Exception as error:
        logger.warning("window: unable to check target process elevation: {}", error)
        return True

    return False


def screen_resolution() -> tuple[int, int]:
    return win32api.GetSystemMetrics(0), win32api.GetSystemMetrics(1)
