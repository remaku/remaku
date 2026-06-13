from dataclasses import dataclass
from typing import Any, cast

from remaku.core import window
from remaku.core.window import Rect


@dataclass
class FakeWindow:
    title: str
    visible: bool = True
    width: int = 100
    height: int = 100


def test_rect_computes_right_and_bottom() -> None:
    rect = Rect(left=10, top=20, width=300, height=200)

    assert rect.right == 310
    assert rect.bottom == 220


def test_list_visible_windows_returns_sorted_visible_titles(monkeypatch) -> None:
    monkeypatch.setattr(
        window.gw,
        "getAllWindows",
        lambda: [FakeWindow("Beta"), FakeWindow(""), FakeWindow("Alpha"), FakeWindow("Hidden", visible=False)],
    )

    assert window.list_visible_windows() == ["Alpha", "Beta"]


def test_find_target_window_returns_active_window_when_title_missing(monkeypatch) -> None:
    active = FakeWindow("Active")
    monkeypatch.setattr(window.gw, "getActiveWindow", lambda: active)

    assert window.find_target_window() is active


def test_find_target_window_returns_none_when_no_active_window(monkeypatch) -> None:
    monkeypatch.setattr(window.gw, "getActiveWindow", lambda: None)

    assert window.find_target_window() is None


def test_find_target_window_picks_largest_visible_match(monkeypatch) -> None:
    small = FakeWindow("Game", width=100, height=100)
    large = FakeWindow("Game", width=200, height=200)
    hidden = FakeWindow("Game", visible=False, width=1000, height=1000)
    monkeypatch.setattr(window.gw, "getWindowsWithTitle", lambda title: [small, hidden, large])

    assert window.find_target_window("Game") is large


def test_find_target_window_returns_none_when_no_visible_match(monkeypatch) -> None:
    monkeypatch.setattr(window.gw, "getWindowsWithTitle", lambda title: [FakeWindow("Game", visible=False)])

    assert window.find_target_window("Game") is None


def test_client_rect_converts_client_area_to_screen(monkeypatch) -> None:
    fake_window = FakeWindow("Game")
    cast(Any, fake_window)._hWnd = 123
    monkeypatch.setattr(window.win32gui, "GetClientRect", lambda hwnd: (0, 0, 640, 480))
    monkeypatch.setattr(window.win32gui, "ClientToScreen", lambda hwnd, point: (10, 20))

    rect = window.client_rect(fake_window)

    assert rect == Rect(left=10, top=20, width=640, height=480)


def test_is_foreground_compares_window_handle(monkeypatch) -> None:
    fake_window = FakeWindow("Game")
    cast(Any, fake_window)._hWnd = 123
    monkeypatch.setattr(window.win32gui, "GetForegroundWindow", lambda: 123)

    assert window.is_foreground(fake_window) is True


def test_is_foreground_returns_false_on_errors(monkeypatch) -> None:
    class BadWindow:
        @property
        def _hWnd(self):
            raise RuntimeError("no handle")

    assert window.is_foreground(BadWindow()) is False


def test_is_self_elevated_returns_admin_state(monkeypatch) -> None:
    class FakeShell32:
        def IsUserAnAdmin(self) -> int:
            return 1

    class FakeWindll:
        shell32 = FakeShell32()

    monkeypatch.setattr(window.ctypes, "windll", FakeWindll())

    assert window.is_self_elevated() is True


def test_is_self_elevated_returns_false_on_error(monkeypatch) -> None:
    class BadShell32:
        def IsUserAnAdmin(self) -> int:
            raise RuntimeError("blocked")

    class FakeWindll:
        shell32 = BadShell32()

    monkeypatch.setattr(window.ctypes, "windll", FakeWindll())

    assert window.is_self_elevated() is False


def test_check_elevation_mismatch_returns_false_when_self_elevated(monkeypatch) -> None:
    monkeypatch.setattr(window, "is_self_elevated", lambda: True)

    assert window.check_elevation_mismatch(FakeWindow("Game")) is False


def test_check_elevation_mismatch_detects_elevated_target(monkeypatch) -> None:
    fake_window = FakeWindow("Game")
    cast(Any, fake_window)._hWnd = 123
    closed = []
    monkeypatch.setattr(window, "is_self_elevated", lambda: False)
    monkeypatch.setattr(window.win32process, "GetWindowThreadProcessId", lambda hwnd: (1, 456))
    monkeypatch.setattr(window.win32api, "OpenProcess", lambda access, inherit, pid: "process")
    monkeypatch.setattr(window.win32security, "OpenProcessToken", lambda process, access: "token")
    monkeypatch.setattr(window.win32security, "GetTokenInformation", lambda token, token_type: True)
    monkeypatch.setattr(window.win32api, "CloseHandle", closed.append)

    assert window.check_elevation_mismatch(fake_window) is True
    assert closed == ["token", "process"]


def test_check_elevation_mismatch_returns_false_for_same_elevation(monkeypatch) -> None:
    fake_window = FakeWindow("Game")
    cast(Any, fake_window)._hWnd = 123
    monkeypatch.setattr(window, "is_self_elevated", lambda: False)
    monkeypatch.setattr(window.win32process, "GetWindowThreadProcessId", lambda hwnd: (1, 456))
    monkeypatch.setattr(window.win32api, "OpenProcess", lambda access, inherit, pid: "process")
    monkeypatch.setattr(window.win32security, "OpenProcessToken", lambda process, access: "token")
    monkeypatch.setattr(window.win32security, "GetTokenInformation", lambda token, token_type: False)
    monkeypatch.setattr(window.win32api, "CloseHandle", lambda handle: None)

    assert window.check_elevation_mismatch(fake_window) is False


def test_check_elevation_mismatch_returns_true_on_error(monkeypatch) -> None:
    fake_window = FakeWindow("Game")
    cast(Any, fake_window)._hWnd = 123
    monkeypatch.setattr(window, "is_self_elevated", lambda: False)
    monkeypatch.setattr(
        window.win32process,
        "GetWindowThreadProcessId",
        lambda hwnd: (_ for _ in ()).throw(RuntimeError("blocked")),
    )

    assert window.check_elevation_mismatch(fake_window) is True


def test_screen_resolution_returns_system_metrics(monkeypatch) -> None:
    monkeypatch.setattr(window.win32api, "GetSystemMetrics", lambda index: 1920 if index == 0 else 1080)

    assert window.screen_resolution() == (1920, 1080)
