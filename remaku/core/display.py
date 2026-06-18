from dataclasses import dataclass
from typing import Any, cast

import win32api
import win32con
from PySide6.QtCore import QPoint
from PySide6.QtGui import QCursor, QScreen
from PySide6.QtWidgets import QApplication

from remaku.core import window


@dataclass(slots=True)
class DisplayTarget:
    screen: QScreen
    physical_rect: window.Rect


def normalize_monitor_name(name: str) -> str:
    base = name.upper().removeprefix("\\\\.\\")
    return base.split("\\", 1)[0]


def screen_at_point(point: QPoint) -> QScreen | None:
    return QApplication.screenAt(point) or QApplication.primaryScreen()


def screen_at_cursor() -> QScreen | None:
    return screen_at_point(QCursor.pos())


def physical_rect_for_screen(screen: QScreen) -> window.Rect:
    device = normalize_monitor_name(screen.name())

    try:
        monitors = win32api.EnumDisplayMonitors()
    except Exception:
        monitors = []

    for monitor, device_context, monitor_rect in monitors:
        del device_context, monitor_rect

        try:
            info = win32api.GetMonitorInfo(cast(int, monitor))
        except Exception:
            continue

        if normalize_monitor_name(str(info.get("Device", ""))) != device:
            continue

        left, top, right, bottom = info["Monitor"]
        return window.Rect(left, top, right - left, bottom - top)

    geometry = screen.geometry()
    return window.Rect(geometry.x(), geometry.y(), geometry.width(), geometry.height())


def physical_rect_for_monitor(monitor: Any) -> window.Rect | None:
    try:
        info = win32api.GetMonitorInfo(cast(int, monitor))
    except Exception:
        return None

    monitor_rect = info.get("Monitor")

    if monitor_rect is None or len(monitor_rect) != 4:
        return None

    left, top, right, bottom = monitor_rect
    return window.Rect(left, top, right - left, bottom - top)


def qt_screen_for_monitor(monitor: Any) -> QScreen | None:
    try:
        info = win32api.GetMonitorInfo(monitor)
    except Exception:
        return None

    device = normalize_monitor_name(str(info.get("Device", "")))

    for screen in QApplication.screens():
        if normalize_monitor_name(screen.name()) == device:
            return screen

    monitor_rect = info.get("Monitor")

    if monitor_rect is None or len(monitor_rect) != 4:
        return None

    left, top, right, bottom = monitor_rect
    center = QPoint((left + right) // 2, (top + bottom) // 2)
    screen = QApplication.screenAt(center)

    if screen is not None:
        return screen

    for candidate in QApplication.screens():
        geometry = candidate.geometry()

        if geometry.contains(center):
            return candidate

    return QApplication.primaryScreen()


def display_target_for_monitor(monitor: Any) -> DisplayTarget | None:
    screen = qt_screen_for_monitor(monitor)

    if screen is None:
        return None

    physical_rect = physical_rect_for_monitor(monitor)

    if physical_rect is None:
        physical_rect = physical_rect_for_screen(screen)

    return DisplayTarget(screen=screen, physical_rect=physical_rect)


def screen_for_window(hwnd: int) -> QScreen | None:
    try:
        monitor = win32api.MonitorFromWindow(hwnd, win32con.MONITOR_DEFAULTTONEAREST)
    except Exception:
        return None

    return qt_screen_for_monitor(monitor)


def display_target_for_window(hwnd: int) -> DisplayTarget | None:
    try:
        monitor = win32api.MonitorFromWindow(hwnd, win32con.MONITOR_DEFAULTTONEAREST)
    except Exception:
        return None

    return display_target_for_monitor(monitor)


def screen_for_rect(rect: window.Rect) -> QScreen | None:
    try:
        monitor = win32api.MonitorFromRect(
            (rect.left, rect.top, rect.right, rect.bottom),
            win32con.MONITOR_DEFAULTTONEAREST,
        )
    except Exception:
        return None

    return qt_screen_for_monitor(monitor)


def display_target_for_rect(rect: window.Rect) -> DisplayTarget | None:
    try:
        monitor = win32api.MonitorFromRect(
            (rect.left, rect.top, rect.right, rect.bottom),
            win32con.MONITOR_DEFAULTTONEAREST,
        )
    except Exception:
        return None

    return display_target_for_monitor(monitor)


def screen_for_pygetwindow(target_window: Any) -> QScreen | None:
    hwnd = getattr(target_window, "_hWnd", None)

    if isinstance(hwnd, int):
        return screen_for_window(hwnd)

    left = getattr(target_window, "left", None)
    top = getattr(target_window, "top", None)
    width = getattr(target_window, "width", None)
    height = getattr(target_window, "height", None)

    if isinstance(left, int) and isinstance(top, int) and isinstance(width, int) and isinstance(height, int):
        return screen_for_rect(window.Rect(left, top, width, height))

    return None


def display_target_for_pygetwindow(target_window: Any) -> DisplayTarget | None:
    hwnd = getattr(target_window, "_hWnd", None)

    if isinstance(hwnd, int):
        return display_target_for_window(hwnd)

    left = getattr(target_window, "left", None)
    top = getattr(target_window, "top", None)
    width = getattr(target_window, "width", None)
    height = getattr(target_window, "height", None)

    if isinstance(left, int) and isinstance(top, int) and isinstance(width, int) and isinstance(height, int):
        return display_target_for_rect(window.Rect(left, top, width, height))

    return None


def display_target_at_cursor() -> DisplayTarget | None:
    try:
        cursor_pos = win32api.GetCursorPos()
        monitor = win32api.MonitorFromPoint(cursor_pos, win32con.MONITOR_DEFAULTTONEAREST)
    except Exception:
        screen = screen_at_cursor()

        if screen is None:
            return None

        return DisplayTarget(screen=screen, physical_rect=physical_rect_for_screen(screen))

    target = display_target_for_monitor(monitor)

    if target is not None:
        return target

    screen = screen_at_cursor()

    if screen is None:
        return None

    return DisplayTarget(screen=screen, physical_rect=physical_rect_for_screen(screen))


def target_screen_for_macro(target_window_title: str = "") -> QScreen | None:
    target = target_display_for_macro(target_window_title)

    if target is not None:
        return target.screen

    return None


def target_display_for_macro(target_window_title: str = "") -> DisplayTarget | None:
    if not target_window_title:
        return display_target_at_cursor()

    target_window = window.find_target_window(target_window_title)

    if target_window is not None:
        target = display_target_for_pygetwindow(target_window)

        if target is not None:
            return target

    foreground_window = window.find_target_window()

    if foreground_window is not None:
        target = display_target_for_pygetwindow(foreground_window)

        if target is not None:
            return target

    return display_target_at_cursor()
