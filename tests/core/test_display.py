from typing import Any, cast

from PySide6.QtCore import QPoint, QRect

from remaku.core import display


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
