import pytest

from remaku.core import keys


def test_sleep_ms_applies_jitter(monkeypatch) -> None:
    sleeps = []
    monkeypatch.setattr(keys.random, "uniform", lambda start, end: 25)
    monkeypatch.setattr(keys.time, "sleep", sleeps.append)

    keys.sleep_ms(100, jitter_ms=50)

    assert sleeps == [0.125]


def test_tap_presses_and_releases_key(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(keys, "sleep_ms", lambda ms, jitter_ms=0: calls.append(("sleep", ms, jitter_ms)))
    monkeypatch.setattr(keys.pdi, "keyDown", lambda key: calls.append(("down", key)))
    monkeypatch.setattr(keys.pdi, "keyUp", lambda key: calls.append(("up", key)))

    keys.tap("enter", hold_ms=120, jitter_ms=10)

    assert calls == [("down", "enter"), ("sleep", 120, 10), ("up", "enter")]


def test_tap_stops_when_key_down_fails(monkeypatch) -> None:
    calls = []

    def raise_key_down(key: str) -> None:
        raise RuntimeError("blocked")

    monkeypatch.setattr(keys.pdi, "keyDown", raise_key_down)
    monkeypatch.setattr(keys.pdi, "keyUp", lambda key: calls.append(("up", key)))

    keys.tap("enter")

    assert calls == []


def test_tap_logs_key_up_failure(monkeypatch) -> None:
    calls = []

    def raise_key_up(key: str) -> None:
        raise RuntimeError("blocked")

    monkeypatch.setattr(keys, "sleep_ms", lambda ms, jitter_ms=0: calls.append(("sleep", ms, jitter_ms)))
    monkeypatch.setattr(keys.pdi, "keyDown", lambda key: calls.append(("down", key)))
    monkeypatch.setattr(keys.pdi, "keyUp", raise_key_up)

    keys.tap("enter", hold_ms=120, jitter_ms=10)

    assert calls == [("down", "enter"), ("sleep", 120, 10)]


def test_type_text_types_unicode_characters_with_interval(monkeypatch) -> None:
    calls = []
    sleeps = []

    monkeypatch.setattr(keys.pdi, "unicode_press", lambda char, _pause=False: calls.append(("unicode", char, _pause)))
    monkeypatch.setattr(keys.pdi, "press", lambda key, _pause=False: calls.append(("press", key, _pause)))
    monkeypatch.setattr(keys.time, "sleep", sleeps.append)

    keys.type_text("哈囉", interval_ms=25)

    assert calls == [("unicode", "哈", False), ("unicode", "囉", False)]
    assert sleeps == [0.025]


def test_type_text_preserves_empty_text(monkeypatch) -> None:
    calls = []

    monkeypatch.setattr(keys.pdi, "unicode_press", lambda char, _pause=False: calls.append(("unicode", char, _pause)))
    monkeypatch.setattr(keys.pdi, "press", lambda key, _pause=False: calls.append(("press", key, _pause)))

    keys.type_text("", interval_ms=0)

    assert calls == []


def test_type_text_converts_newlines_to_enter(monkeypatch) -> None:
    calls = []

    monkeypatch.setattr(keys.pdi, "unicode_press", lambda char, _pause=False: calls.append(("unicode", char, _pause)))
    monkeypatch.setattr(keys.pdi, "press", lambda key, _pause=False: calls.append(("press", key, _pause)))

    keys.type_text("test\n\n\nasd", interval_ms=0)

    assert calls == [
        ("unicode", "t", False),
        ("unicode", "e", False),
        ("unicode", "s", False),
        ("unicode", "t", False),
        ("press", "enter", False),
        ("press", "enter", False),
        ("press", "enter", False),
        ("unicode", "a", False),
        ("unicode", "s", False),
        ("unicode", "d", False),
    ]


def test_type_text_normalizes_windows_newlines(monkeypatch) -> None:
    calls = []

    monkeypatch.setattr(keys.pdi, "unicode_press", lambda char, _pause=False: calls.append(("unicode", char, _pause)))
    monkeypatch.setattr(keys.pdi, "press", lambda key, _pause=False: calls.append(("press", key, _pause)))

    keys.type_text("first\r\nsecond\rold", interval_ms=0)

    assert calls == [
        ("unicode", "f", False),
        ("unicode", "i", False),
        ("unicode", "r", False),
        ("unicode", "s", False),
        ("unicode", "t", False),
        ("press", "enter", False),
        ("unicode", "s", False),
        ("unicode", "e", False),
        ("unicode", "c", False),
        ("unicode", "o", False),
        ("unicode", "n", False),
        ("unicode", "d", False),
        ("press", "enter", False),
        ("unicode", "o", False),
        ("unicode", "l", False),
        ("unicode", "d", False),
    ]


def test_type_text_clamps_negative_interval(monkeypatch) -> None:
    calls = []
    sleeps = []

    monkeypatch.setattr(keys.pdi, "unicode_press", lambda char, _pause=False: calls.append(("unicode", char, _pause)))
    monkeypatch.setattr(keys.pdi, "press", lambda key, _pause=False: calls.append(("press", key, _pause)))
    monkeypatch.setattr(keys.time, "sleep", sleeps.append)

    keys.type_text("hello", interval_ms=-100)

    assert calls == [
        ("unicode", "h", False),
        ("unicode", "e", False),
        ("unicode", "l", False),
        ("unicode", "l", False),
        ("unicode", "o", False),
    ]
    assert sleeps == []


def test_type_text_logs_failure(monkeypatch) -> None:
    def raise_unicode_press(char: str, _pause: bool = False) -> None:
        raise RuntimeError("blocked")

    monkeypatch.setattr(keys.pdi, "unicode_press", raise_unicode_press)

    keys.type_text("hello")


def test_held_releases_key_after_context(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(keys.pdi, "keyDown", lambda key: calls.append(("down", key)))
    monkeypatch.setattr(keys.pdi, "keyUp", lambda key: calls.append(("up", key)))

    with keys.held("space"):
        calls.append(("inside", "space"))

    assert calls == [("down", "space"), ("inside", "space"), ("up", "space")]


def test_held_reraises_key_down_failure(monkeypatch) -> None:
    def raise_key_down(key: str) -> None:
        raise RuntimeError("blocked")

    monkeypatch.setattr(keys.pdi, "keyDown", raise_key_down)

    with pytest.raises(RuntimeError, match="blocked"), keys.held("space"):
        pass


def test_held_suppresses_key_up_failure(monkeypatch) -> None:
    calls = []

    def raise_key_up(key: str) -> None:
        raise RuntimeError("blocked")

    monkeypatch.setattr(keys.pdi, "keyDown", lambda key: calls.append(("down", key)))
    monkeypatch.setattr(keys.pdi, "keyUp", raise_key_up)

    with keys.held("space"):
        calls.append(("inside", "space"))

    assert calls == [("down", "space"), ("inside", "space")]


def test_is_valid_key_delegates_to_pydirectinput(monkeypatch) -> None:
    monkeypatch.setattr(keys.pdi, "isValidKey", lambda key: key == "enter")

    assert keys.is_valid_key("enter") is True
    assert keys.is_valid_key("nope") is False


@pytest.mark.parametrize(
    ("button", "expected_call"),
    [
        ("left", "left"),
        ("right", "right"),
        ("middle", "middle"),
    ],
)
def test_mouse_click_moves_and_clicks_requested_button(monkeypatch, button: str, expected_call: str) -> None:
    calls = []
    monkeypatch.setattr(keys.pdi, "moveTo", lambda x, y: calls.append(("move", x, y)))
    monkeypatch.setattr(keys.pdi, "leftClick", lambda: calls.append(("click", "left")))
    monkeypatch.setattr(keys.pdi, "rightClick", lambda: calls.append(("click", "right")))
    monkeypatch.setattr(keys.pdi, "middleClick", lambda: calls.append(("click", "middle")))

    keys.mouse_click(button, 10, 20)

    assert calls == [("move", 10, 20), ("click", expected_call)]


def test_mouse_click_stops_when_move_fails(monkeypatch) -> None:
    calls = []

    def raise_move(x: int, y: int) -> None:
        raise RuntimeError("blocked")

    monkeypatch.setattr(keys.pdi, "moveTo", raise_move)
    monkeypatch.setattr(keys.pdi, "leftClick", lambda: calls.append("left"))

    keys.mouse_click("left", 10, 20)

    assert calls == []


def test_mouse_click_logs_click_failure(monkeypatch) -> None:
    calls = []

    def raise_click() -> None:
        raise RuntimeError("blocked")

    monkeypatch.setattr(keys.pdi, "moveTo", lambda x, y: calls.append(("move", x, y)))
    monkeypatch.setattr(keys.pdi, "leftClick", raise_click)

    keys.mouse_click("left", 10, 20)

    assert calls == [("move", 10, 20)]


def test_mouse_move_delegates_to_pydirectinput(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(keys.pdi, "moveTo", lambda x, y: calls.append((x, y)))

    keys.mouse_move(10, 20)

    assert calls == [(10, 20)]


def test_mouse_move_logs_failure(monkeypatch) -> None:
    def raise_move(x: int, y: int) -> None:
        raise RuntimeError("blocked")

    monkeypatch.setattr(keys.pdi, "moveTo", raise_move)

    keys.mouse_move(10, 20)


def test_mouse_scroll_sends_one_tick_at_a_time_with_interval(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(keys.pdi, "scroll", lambda clicks: calls.append(("scroll", clicks)))
    monkeypatch.setattr(keys, "sleep_ms", lambda ms: calls.append(("sleep", ms)))

    keys.mouse_scroll(3, interval_ms=25)

    assert calls == [
        ("scroll", 1),
        ("sleep", 25),
        ("scroll", 1),
        ("sleep", 25),
        ("scroll", 1),
        ("sleep", 25),
    ]


def test_mouse_scroll_sends_negative_ticks_and_allows_zero(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(keys.pdi, "scroll", lambda clicks: calls.append(clicks))

    keys.mouse_scroll(-2)
    keys.mouse_scroll(0)

    assert calls == [-1, -1]


def test_mouse_scroll_stops_on_failure(monkeypatch) -> None:
    calls = []

    def fake_scroll(clicks: int) -> None:
        calls.append(clicks)
        raise RuntimeError("blocked")

    monkeypatch.setattr(keys.pdi, "scroll", fake_scroll)
    monkeypatch.setattr(keys, "sleep_ms", lambda ms: calls.append(ms))

    keys.mouse_scroll(2, interval_ms=25)

    assert calls == [1]
