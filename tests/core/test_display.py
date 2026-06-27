from typing import Any, cast

from PySide6.QtCore import QPoint, QRect

from remaku.core import display
from remaku.core.window import Rect


def test_normalize_monitor_name_strips_dot_prefix() -> None:
    assert display.normalize_monitor_name("\\\\.\\DISPLAY1") == "DISPLAY1"


def test_normalize_monitor_name_uppercases_input() -> None:
    assert display.normalize_monitor_name("\\\\.\\display2") == "DISPLAY2"


def test_normalize_monitor_name_keeps_plain_name() -> None:
    assert display.normalize_monitor_name("DISPLAY1") == "DISPLAY1"


def test_normalize_monitor_name_strips_qt6_monitor_suffix() -> None:
    assert display.normalize_monitor_name("\\\\.\\DISPLAY2\\Monitor0") == "DISPLAY2"


class FakeScreen:
    def __init__(self, name: str = "DISPLAY1", geometry: QRect | None = None) -> None:
        self.screen_name = name
        self.screen_geometry = geometry or QRect(0, 0, 100, 100)

    def name(self) -> str:
        return self.screen_name

    def geometry(self) -> QRect:
        return self.screen_geometry


def test_qt_screen_for_monitor_matches_monitor_device_name(monkeypatch) -> None:
    primary = FakeScreen("DISPLAY1")
    secondary = FakeScreen("DISPLAY2")

    monkeypatch.setattr(display.win32api, "GetMonitorInfo", lambda monitor: {"Device": "\\\\.\\DISPLAY2"})
    monkeypatch.setattr(display.QApplication, "screens", lambda: [primary, secondary])

    assert display.qt_screen_for_monitor(object()) is secondary


def test_physical_rect_for_screen_uses_matching_monitor_device_name(monkeypatch) -> None:
    screen = FakeScreen("DISPLAY2", QRect(200, 10, 100, 80))
    monitor_one = object()
    monitor_two = object()

    monkeypatch.setattr(
        display.win32api,
        "EnumDisplayMonitors",
        lambda: [(monitor_one, object(), object()), (monitor_two, object(), object())],
    )
    monkeypatch.setattr(
        display.win32api,
        "GetMonitorInfo",
        lambda monitor: {
            monitor_one: {"Device": "\\\\.\\DISPLAY1", "Monitor": (0, 0, 1920, 1080)},
            monitor_two: {"Device": "\\\\.\\DISPLAY2", "Monitor": (1920, 0, 3200, 720)},
        }[monitor],
    )

    rect = display.physical_rect_for_screen(cast(Any, screen))

    assert rect.left == 1920
    assert rect.top == 0
    assert rect.width == 1280
    assert rect.height == 720


def test_physical_rect_for_screen_falls_back_to_qt_geometry(monkeypatch) -> None:
    screen = FakeScreen("DISPLAY2", QRect(200, 10, 100, 80))

    monkeypatch.setattr(display.win32api, "EnumDisplayMonitors", lambda: [])

    rect = display.physical_rect_for_screen(cast(Any, screen))

    assert rect.left == 200
    assert rect.top == 10
    assert rect.width == 100
    assert rect.height == 80


def test_screen_at_point_uses_primary_when_screen_at_misses(monkeypatch) -> None:
    primary = FakeScreen()

    monkeypatch.setattr(display.QApplication, "screenAt", lambda point: None)
    monkeypatch.setattr(display.QApplication, "primaryScreen", lambda: primary)

    assert display.screen_at_point(QPoint(10, 10)) is primary


def test_screen_at_cursor_uses_cursor_position(monkeypatch) -> None:
    screen = FakeScreen()

    monkeypatch.setattr(display.QCursor, "pos", lambda: QPoint(20, 30))
    monkeypatch.setattr(display, "screen_at_point", lambda point: screen if point == QPoint(20, 30) else None)

    assert display.screen_at_cursor() is screen


def test_physical_rect_for_screen_handles_monitor_enumeration_error(monkeypatch) -> None:
    screen = FakeScreen("DISPLAY2", QRect(200, 10, 100, 80))

    def raise_error():
        raise RuntimeError("display unavailable")

    monkeypatch.setattr(display.win32api, "EnumDisplayMonitors", raise_error)

    rect = display.physical_rect_for_screen(cast(Any, screen))

    assert rect == Rect(200, 10, 100, 80)


def test_physical_rect_for_screen_skips_monitor_info_errors(monkeypatch) -> None:
    screen = FakeScreen("DISPLAY2", QRect(200, 10, 100, 80))

    def get_monitor_info(monitor):
        raise RuntimeError("bad monitor")

    monkeypatch.setattr(display.win32api, "EnumDisplayMonitors", lambda: [(object(), object(), object())])
    monkeypatch.setattr(display.win32api, "GetMonitorInfo", get_monitor_info)

    rect = display.physical_rect_for_screen(cast(Any, screen))

    assert rect == Rect(200, 10, 100, 80)


def test_physical_rect_for_monitor_returns_none_when_info_fails(monkeypatch) -> None:
    def raise_error(monitor):
        raise RuntimeError("bad monitor")

    monkeypatch.setattr(display.win32api, "GetMonitorInfo", raise_error)

    assert display.physical_rect_for_monitor(object()) is None


def test_physical_rect_for_monitor_rejects_missing_or_invalid_rect(monkeypatch) -> None:
    monkeypatch.setattr(display.win32api, "GetMonitorInfo", lambda monitor: {})

    assert display.physical_rect_for_monitor(object()) is None

    monkeypatch.setattr(display.win32api, "GetMonitorInfo", lambda monitor: {"Monitor": (1, 2, 3)})

    assert display.physical_rect_for_monitor(object()) is None


def test_physical_rect_for_monitor_converts_monitor_rect(monkeypatch) -> None:
    monkeypatch.setattr(display.win32api, "GetMonitorInfo", lambda monitor: {"Monitor": (10, 20, 110, 220)})

    assert display.physical_rect_for_monitor(object()) == Rect(10, 20, 100, 200)


def test_display_target_for_monitor_keeps_win32_physical_rect(monkeypatch) -> None:
    screen = FakeScreen("DISPLAY2", QRect(0, 720, 1280, 720))
    monitor = object()

    monkeypatch.setattr(display, "qt_screen_for_monitor", lambda target_monitor: screen)
    monkeypatch.setattr(
        display.win32api,
        "GetMonitorInfo",
        lambda target_monitor: {"Device": "\\\\.\\DISPLAY2", "Monitor": (0, 1080, 1920, 2160)},
    )

    target = display.display_target_for_monitor(monitor)

    assert target is not None
    assert target.screen is screen
    assert target.physical_rect.left == 0
    assert target.physical_rect.top == 1080
    assert target.physical_rect.width == 1920
    assert target.physical_rect.height == 1080


def test_qt_screen_for_monitor_falls_back_to_geometry_center(monkeypatch) -> None:
    primary = FakeScreen("DISPLAY1", QRect(0, 0, 100, 100))
    secondary = FakeScreen("DISPLAY2", QRect(100, 0, 100, 100))

    monkeypatch.setattr(
        display.win32api,
        "GetMonitorInfo",
        lambda monitor: {"Device": "\\\\.\\DISPLAY3", "Monitor": (100, 0, 200, 100)},
    )
    monkeypatch.setattr(display.QApplication, "screens", lambda: [primary, secondary])
    monkeypatch.setattr(display.QApplication, "screenAt", lambda point: secondary if point == QPoint(150, 50) else None)
    monkeypatch.setattr(display.QApplication, "primaryScreen", lambda: primary)

    assert display.qt_screen_for_monitor(object()) is secondary


def test_qt_screen_for_monitor_returns_none_when_info_fails(monkeypatch) -> None:
    def raise_error(monitor):
        raise RuntimeError("bad monitor")

    monkeypatch.setattr(display.win32api, "GetMonitorInfo", raise_error)

    assert display.qt_screen_for_monitor(object()) is None


def test_qt_screen_for_monitor_rejects_invalid_monitor_rect(monkeypatch) -> None:
    monkeypatch.setattr(display.win32api, "GetMonitorInfo", lambda monitor: {"Device": "DISPLAY3", "Monitor": (1, 2)})
    monkeypatch.setattr(display.QApplication, "screens", lambda: [])

    assert display.qt_screen_for_monitor(object()) is None


def test_qt_screen_for_monitor_uses_geometry_contains_then_primary(monkeypatch) -> None:
    primary = FakeScreen("DISPLAY1", QRect(0, 0, 100, 100))
    secondary = FakeScreen("DISPLAY2", QRect(100, 0, 100, 100))

    monkeypatch.setattr(
        display.win32api,
        "GetMonitorInfo",
        lambda monitor: {"Device": "\\\\.\\DISPLAY3", "Monitor": (100, 0, 200, 100)},
    )
    monkeypatch.setattr(display.QApplication, "screens", lambda: [primary, secondary])
    monkeypatch.setattr(display.QApplication, "screenAt", lambda point: None)
    monkeypatch.setattr(display.QApplication, "primaryScreen", lambda: primary)

    assert display.qt_screen_for_monitor(object()) is secondary

    monkeypatch.setattr(display.QApplication, "screens", lambda: [])

    assert display.qt_screen_for_monitor(object()) is primary


def test_display_target_for_monitor_returns_none_without_qt_screen(monkeypatch) -> None:
    monkeypatch.setattr(display, "qt_screen_for_monitor", lambda monitor: None)

    assert display.display_target_for_monitor(object()) is None


def test_display_target_for_monitor_falls_back_to_screen_rect(monkeypatch) -> None:
    screen = FakeScreen("DISPLAY2", QRect(20, 30, 400, 500))

    monkeypatch.setattr(display, "qt_screen_for_monitor", lambda monitor: screen)
    monkeypatch.setattr(display, "physical_rect_for_monitor", lambda monitor: None)

    target = display.display_target_for_monitor(object())

    assert target == display.DisplayTarget(screen=cast(Any, screen), physical_rect=Rect(20, 30, 400, 500))


def test_screen_for_window_returns_none_when_monitor_lookup_fails(monkeypatch) -> None:
    def raise_error(hwnd, default):
        raise RuntimeError("window missing")

    monkeypatch.setattr(display.win32api, "MonitorFromWindow", raise_error)

    assert display.screen_for_window(10) is None


def test_screen_for_window_uses_qt_screen_for_monitor(monkeypatch) -> None:
    screen = FakeScreen()
    monitor = object()

    monkeypatch.setattr(display.win32api, "MonitorFromWindow", lambda hwnd, default: monitor)
    monkeypatch.setattr(
        display, "qt_screen_for_monitor", lambda target_monitor: screen if target_monitor is monitor else None
    )

    assert display.screen_for_window(10) is screen


def test_display_target_for_window_returns_none_when_monitor_lookup_fails(monkeypatch) -> None:
    def raise_error(hwnd, default):
        raise RuntimeError("window missing")

    monkeypatch.setattr(display.win32api, "MonitorFromWindow", raise_error)

    assert display.display_target_for_window(10) is None


def test_display_target_for_window_uses_display_target_for_monitor(monkeypatch) -> None:
    screen = FakeScreen()
    monitor = object()
    target = display.DisplayTarget(screen=cast(Any, screen), physical_rect=Rect(0, 0, 100, 100))

    monkeypatch.setattr(display.win32api, "MonitorFromWindow", lambda hwnd, default: monitor)
    monkeypatch.setattr(
        display, "display_target_for_monitor", lambda target_monitor: target if target_monitor is monitor else None
    )

    assert display.display_target_for_window(10) is target


def test_screen_for_rect_returns_none_when_monitor_lookup_fails(monkeypatch) -> None:
    def raise_error(rect, default):
        raise RuntimeError("bad rect")

    monkeypatch.setattr(display.win32api, "MonitorFromRect", raise_error)

    assert display.screen_for_rect(Rect(1, 2, 3, 4)) is None


def test_screen_for_rect_uses_qt_screen_for_monitor(monkeypatch) -> None:
    screen = FakeScreen()
    monitor = object()

    monkeypatch.setattr(display.win32api, "MonitorFromRect", lambda rect, default: monitor)
    monkeypatch.setattr(
        display, "qt_screen_for_monitor", lambda target_monitor: screen if target_monitor is monitor else None
    )

    assert display.screen_for_rect(Rect(1, 2, 3, 4)) is screen


def test_display_target_for_rect_returns_none_when_monitor_lookup_fails(monkeypatch) -> None:
    def raise_error(rect, default):
        raise RuntimeError("bad rect")

    monkeypatch.setattr(display.win32api, "MonitorFromRect", raise_error)

    assert display.display_target_for_rect(Rect(1, 2, 3, 4)) is None


def test_display_target_for_rect_uses_display_target_for_monitor(monkeypatch) -> None:
    screen = FakeScreen()
    monitor = object()
    target = display.DisplayTarget(screen=cast(Any, screen), physical_rect=Rect(0, 0, 100, 100))

    monkeypatch.setattr(display.win32api, "MonitorFromRect", lambda rect, default: monitor)
    monkeypatch.setattr(
        display, "display_target_for_monitor", lambda target_monitor: target if target_monitor is monitor else None
    )

    assert display.display_target_for_rect(Rect(1, 2, 3, 4)) is target


class FakeWindow:
    _hWnd: int
    left: int
    top: int
    width: int
    height: int


def test_screen_for_pygetwindow_uses_hwnd(monkeypatch) -> None:
    screen = FakeScreen()
    target_window = FakeWindow()
    target_window._hWnd = 123

    monkeypatch.setattr(display, "screen_for_window", lambda hwnd: screen if hwnd == 123 else None)

    assert display.screen_for_pygetwindow(target_window) is screen


def test_screen_for_pygetwindow_uses_rect_when_hwnd_missing(monkeypatch) -> None:
    screen = FakeScreen()
    target_window = FakeWindow()
    target_window.left = 1
    target_window.top = 2
    target_window.width = 3
    target_window.height = 4

    monkeypatch.setattr(display, "screen_for_rect", lambda rect: screen if rect == Rect(1, 2, 3, 4) else None)

    assert display.screen_for_pygetwindow(target_window) is screen


def test_screen_for_pygetwindow_returns_none_without_window_geometry() -> None:
    assert display.screen_for_pygetwindow(FakeWindow()) is None


def test_display_target_for_pygetwindow_uses_hwnd(monkeypatch) -> None:
    screen = FakeScreen()
    target = display.DisplayTarget(screen=cast(Any, screen), physical_rect=Rect(0, 0, 100, 100))
    target_window = FakeWindow()
    target_window._hWnd = 123

    monkeypatch.setattr(display, "display_target_for_window", lambda hwnd: target if hwnd == 123 else None)

    assert display.display_target_for_pygetwindow(target_window) is target


def test_display_target_for_pygetwindow_uses_rect_when_hwnd_missing(monkeypatch) -> None:
    screen = FakeScreen()
    target = display.DisplayTarget(screen=cast(Any, screen), physical_rect=Rect(0, 0, 100, 100))
    target_window = FakeWindow()
    target_window.left = 1
    target_window.top = 2
    target_window.width = 3
    target_window.height = 4

    monkeypatch.setattr(display, "display_target_for_rect", lambda rect: target if rect == Rect(1, 2, 3, 4) else None)

    assert display.display_target_for_pygetwindow(target_window) is target


def test_display_target_for_pygetwindow_returns_none_without_window_geometry() -> None:
    assert display.display_target_for_pygetwindow(FakeWindow()) is None


def test_display_target_at_cursor_falls_back_when_win32_cursor_lookup_fails(monkeypatch) -> None:
    screen = FakeScreen("DISPLAY1", QRect(5, 6, 70, 80))

    def raise_error():
        raise RuntimeError("cursor unavailable")

    monkeypatch.setattr(display.win32api, "GetCursorPos", raise_error)
    monkeypatch.setattr(display, "screen_at_cursor", lambda: screen)
    monkeypatch.setattr(display, "physical_rect_for_screen", lambda target_screen: Rect(5, 6, 70, 80))

    target = display.display_target_at_cursor()

    assert target == display.DisplayTarget(screen=cast(Any, screen), physical_rect=Rect(5, 6, 70, 80))


def test_display_target_at_cursor_returns_none_when_fallback_screen_missing(monkeypatch) -> None:
    def raise_error():
        raise RuntimeError("cursor unavailable")

    monkeypatch.setattr(display.win32api, "GetCursorPos", raise_error)
    monkeypatch.setattr(display, "screen_at_cursor", lambda: None)

    assert display.display_target_at_cursor() is None


def test_display_target_at_cursor_uses_monitor_target(monkeypatch) -> None:
    screen = FakeScreen()
    monitor = object()
    target = display.DisplayTarget(screen=cast(Any, screen), physical_rect=Rect(0, 0, 100, 100))

    monkeypatch.setattr(display.win32api, "GetCursorPos", lambda: (10, 20))
    monkeypatch.setattr(display.win32api, "MonitorFromPoint", lambda point, default: monitor)
    monkeypatch.setattr(
        display, "display_target_for_monitor", lambda target_monitor: target if target_monitor is monitor else None
    )

    assert display.display_target_at_cursor() is target


def test_display_target_at_cursor_falls_back_when_monitor_target_missing(monkeypatch) -> None:
    screen = FakeScreen("DISPLAY1", QRect(5, 6, 70, 80))

    monkeypatch.setattr(display.win32api, "GetCursorPos", lambda: (10, 20))
    monkeypatch.setattr(display.win32api, "MonitorFromPoint", lambda point, default: object())
    monkeypatch.setattr(display, "display_target_for_monitor", lambda monitor: None)
    monkeypatch.setattr(display, "screen_at_cursor", lambda: screen)
    monkeypatch.setattr(display, "physical_rect_for_screen", lambda target_screen: Rect(5, 6, 70, 80))

    target = display.display_target_at_cursor()

    assert target == display.DisplayTarget(screen=cast(Any, screen), physical_rect=Rect(5, 6, 70, 80))


def test_display_target_at_cursor_returns_none_when_monitor_and_screen_missing(monkeypatch) -> None:
    monkeypatch.setattr(display.win32api, "GetCursorPos", lambda: (10, 20))
    monkeypatch.setattr(display.win32api, "MonitorFromPoint", lambda point, default: object())
    monkeypatch.setattr(display, "display_target_for_monitor", lambda monitor: None)
    monkeypatch.setattr(display, "screen_at_cursor", lambda: None)

    assert display.display_target_at_cursor() is None


def test_target_screen_for_macro_falls_back_to_cursor_when_no_target_window(monkeypatch) -> None:
    cursor_screen = FakeScreen()
    cursor_target = display.DisplayTarget(
        screen=cast(Any, cursor_screen),
        physical_rect=display.window.Rect(0, 0, 100, 100),
    )

    monkeypatch.setattr(display.window, "find_target_window", lambda title="": None)
    monkeypatch.setattr(display, "display_target_at_cursor", lambda: cursor_target)

    assert display.target_screen_for_macro("Missing") is cursor_screen


def test_target_display_for_macro_uses_cursor_without_target_window(monkeypatch) -> None:
    cursor_screen = FakeScreen()
    cursor_target = display.DisplayTarget(
        screen=cast(Any, cursor_screen),
        physical_rect=display.window.Rect(0, 2160, 100, 100),
    )

    def fail_find_target_window(title: str = ""):
        raise AssertionError("foreground window should not be queried without a target title")

    monkeypatch.setattr(display.window, "find_target_window", fail_find_target_window)
    monkeypatch.setattr(display, "display_target_at_cursor", lambda: cursor_target)

    assert display.target_display_for_macro("") is cursor_target


def test_target_screen_for_macro_returns_none_without_target(monkeypatch) -> None:
    monkeypatch.setattr(display, "target_display_for_macro", lambda title: None)

    assert display.target_screen_for_macro("Missing") is None


def test_target_display_for_macro_uses_named_target_window(monkeypatch) -> None:
    target_window = object()
    screen = FakeScreen()
    target = display.DisplayTarget(screen=cast(Any, screen), physical_rect=Rect(0, 0, 100, 100))

    monkeypatch.setattr(
        display.window, "find_target_window", lambda title="": target_window if title == "Game" else None
    )
    monkeypatch.setattr(
        display, "display_target_for_pygetwindow", lambda window: target if window is target_window else None
    )

    assert display.target_display_for_macro("Game") is target


def test_target_display_for_macro_falls_back_to_cursor_when_windows_have_no_target(monkeypatch) -> None:
    named_window = object()
    foreground_window = object()
    cursor_target = display.DisplayTarget(screen=cast(Any, FakeScreen()), physical_rect=Rect(0, 0, 100, 100))
    calls = []

    def find_target_window(title: str = ""):
        calls.append(title)
        return named_window if title == "Game" else foreground_window

    monkeypatch.setattr(display.window, "find_target_window", find_target_window)
    monkeypatch.setattr(display, "display_target_for_pygetwindow", lambda target_window: None)
    monkeypatch.setattr(display, "display_target_at_cursor", lambda: cursor_target)

    assert display.target_display_for_macro("Game") is cursor_target
    assert calls == ["Game", ""]


def test_target_screen_for_macro_uses_foreground_when_named_target_is_missing(monkeypatch) -> None:
    foreground_window = object()
    foreground_screen = FakeScreen()
    calls = []

    def fake_find_target_window(title: str = ""):
        calls.append(title)
        return foreground_window if title == "" else None

    monkeypatch.setattr(display.window, "find_target_window", fake_find_target_window)
    monkeypatch.setattr(
        display,
        "display_target_for_pygetwindow",
        lambda target_window: display.DisplayTarget(
            screen=cast(Any, foreground_screen),
            physical_rect=display.window.Rect(0, 0, 100, 100),
        ),
    )

    assert display.target_screen_for_macro("Missing") is foreground_screen
    assert calls == ["Missing", ""]
