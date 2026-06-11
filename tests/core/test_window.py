from dataclasses import dataclass

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


def test_find_target_window_picks_largest_visible_match(monkeypatch) -> None:
    small = FakeWindow("Game", width=100, height=100)
    large = FakeWindow("Game", width=200, height=200)
    hidden = FakeWindow("Game", visible=False, width=1000, height=1000)
    monkeypatch.setattr(window.gw, "getWindowsWithTitle", lambda title: [small, hidden, large])

    assert window.find_target_window("Game") is large


def test_is_foreground_returns_false_on_errors(monkeypatch) -> None:
    class BadWindow:
        @property
        def _hWnd(self):
            raise RuntimeError("no handle")

    assert window.is_foreground(BadWindow()) is False
