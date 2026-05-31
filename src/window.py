"""Window management module.

Provides OS window interaction such as finding windows and getting window positions.
"""

import ctypes
from dataclasses import dataclass

import pygetwindow as gw
import win32api
import win32con
import win32gui
import win32process
import win32security
from loguru import logger


@dataclass
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
    """Return all visible window titles (deduplicated, sorted, excluding blank titles)."""
    return sorted({w.title for w in gw.getAllWindows() if w.title.strip() and w.visible})


def find_target_window(title: str = "") -> gw.Window | None:
    """Find a target window by title. Returns the foreground window if title is empty."""
    if not title:
        win = gw.getActiveWindow()

        if win:
            return win
        logger.debug("window: no foreground window found")
        return None

    wins = [w for w in gw.getWindowsWithTitle(title) if w.title and w.visible]

    if wins:
        wins.sort(key=lambda w: w.width * w.height, reverse=True)
        logger.debug("window: found '{}' ({}x{})", wins[0].title, wins[0].width, wins[0].height)
        return wins[0]

    logger.debug("window: no matching window (title='{}')", title)

    return None


def client_rect(win: gw.Window) -> Rect:
    hwnd = win._hWnd
    left, top, right, bottom = win32gui.GetClientRect(hwnd)
    screen_x, screen_y = win32gui.ClientToScreen(hwnd, (left, top))

    return Rect(left=screen_x, top=screen_y, width=right - left, height=bottom - top)


def is_foreground(win: gw.Window) -> bool:
    try:
        return win32gui.GetForegroundWindow() == win._hWnd
    except Exception:
        return False


def is_self_elevated() -> bool:
    """Check if this program is running as administrator."""
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def check_elevation_mismatch(win: gw.Window) -> bool:
    """Check if the target window's process is running with higher privileges.

    Returns True if we are not elevated but the target process is, meaning SendInput will be blocked by UIPI.
    """
    if is_self_elevated():
        return False

    try:
        _, pid = win32process.GetWindowThreadProcessId(win._hWnd)
        hProcess = win32api.OpenProcess(win32con.PROCESS_QUERY_LIMITED_INFORMATION, False, pid)

        try:
            hToken = win32security.OpenProcessToken(hProcess, win32con.TOKEN_QUERY)
            elevation = win32security.GetTokenInformation(hToken, win32security.TokenElevation)
            win32api.CloseHandle(hToken)

            if elevation:
                logger.warning("window: elevation mismatch detected, SendInput cannot reach target window")
                return True
        finally:
            win32api.CloseHandle(hProcess)
    except Exception as e:
        logger.warning("window: unable to check target process elevation: {}", e)
        return True

    return False
