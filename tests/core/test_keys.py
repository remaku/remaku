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


def test_tap_presses_combo_and_releases_in_reverse_order(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(keys, "sleep_ms", lambda ms, jitter_ms=0: calls.append(("sleep", ms, jitter_ms)))
    monkeypatch.setattr(keys.pdi, "keyDown", lambda key: calls.append(("down", key)))
    monkeypatch.setattr(keys.pdi, "keyUp", lambda key: calls.append(("up", key)))

    keys.tap("ctrl+shift+s", hold_ms=120, jitter_ms=10)

    assert calls == [
        ("down", "ctrl"),
        ("down", "shift"),
        ("down", "s"),
        ("sleep", 120, 10),
        ("up", "s"),
        ("up", "shift"),
        ("up", "ctrl"),
    ]


def test_tap_posts_background_key_messages(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(keys, "sleep_ms", lambda ms, jitter_ms=0: calls.append(("sleep", ms, jitter_ms)))
    monkeypatch.setattr(keys.win32api, "MapVirtualKey", lambda vk_code, map_type: 30)
    monkeypatch.setattr(
        keys.win32gui,
        "PostMessage",
        lambda hwnd, message, wparam, lparam: calls.append((hwnd, message, wparam, lparam)),
    )

    keys.tap("a", hold_ms=120, jitter_ms=10, hwnd=123)

    assert calls == [
        (123, keys.win32con.WM_KEYDOWN, 65, 1 | (30 << 16)),
        ("sleep", 120, 10),
        (123, keys.win32con.WM_KEYUP, 65, 1 | (30 << 16) | (1 << 30) | (1 << 31)),
    ]


def test_post_key_handles_digit_and_unknown_background_keys(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(keys.win32api, "MapVirtualKey", lambda vk_code, map_type: 11)
    monkeypatch.setattr(
        keys.win32gui,
        "PostMessage",
        lambda hwnd, message, wparam, lparam: calls.append((message, wparam, lparam)),
    )

    assert keys.post_key(123, "5", True) is True
    assert keys.post_key(123, "not-a-key", True) is False
    assert calls == [(keys.win32con.WM_KEYDOWN, ord("5"), 1 | (11 << 16))]


def test_tap_background_rejects_empty_combo_and_failed_key(monkeypatch) -> None:
    releases = []
    monkeypatch.setattr(keys, "parse_key_combo", lambda key: [] if key == "empty" else ["ctrl", "bad"])
    monkeypatch.setattr(keys, "post_key", lambda hwnd, key, is_down: key != "bad")
    monkeypatch.setattr(keys, "release_background_keys", lambda hwnd, pressed: releases.append(list(pressed)))

    assert keys.tap_background(123, "empty", 1, 0) is False
    assert keys.tap_background(123, "ctrl+bad", 1, 0) is False
    assert releases == [["ctrl"]]


def test_tap_background_releases_pressed_keys_on_post_exception(monkeypatch) -> None:
    releases = []

    def post_key(hwnd: int, key: str, is_down: bool) -> bool:
        if key == "bad":
            raise RuntimeError("blocked")

        return True

    monkeypatch.setattr(keys, "parse_key_combo", lambda key: ["ctrl", "bad"])
    monkeypatch.setattr(keys, "post_key", post_key)
    monkeypatch.setattr(keys, "release_background_keys", lambda hwnd, pressed: releases.append(list(pressed)))

    assert keys.tap_background(123, "ctrl+bad", 1, 0) is False
    assert releases == [["ctrl"]]


def test_tap_delegates_to_background_tap(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(
        keys, "tap_background", lambda hwnd, key, hold_ms, jitter_ms: calls.append((hwnd, key, hold_ms, jitter_ms))
    )

    keys.tap("a", hold_ms=10, jitter_ms=2, hwnd=123)

    assert calls == [(123, "a", 10, 2)]


def test_release_background_keys_suppresses_key_up_errors(monkeypatch) -> None:
    calls = []

    def post_key(hwnd: int, key: str, is_down: bool) -> bool:
        calls.append((key, is_down))
        if key == "ctrl":
            raise RuntimeError("blocked")

        return True

    monkeypatch.setattr(keys, "post_key", post_key)

    keys.release_background_keys(123, ["ctrl", "s"])

    assert calls == [("s", False), ("ctrl", False)]


def test_tap_stops_when_key_down_fails(monkeypatch) -> None:
    calls = []

    def raise_key_down(key: str) -> None:
        raise RuntimeError("blocked")

    monkeypatch.setattr(keys.pdi, "keyDown", raise_key_down)
    monkeypatch.setattr(keys.pdi, "keyUp", lambda key: calls.append(("up", key)))

    keys.tap("enter")

    assert calls == []


def test_tap_releases_pressed_combo_keys_when_later_key_down_fails(monkeypatch) -> None:
    calls = []

    def key_down(key: str) -> None:
        calls.append(("down", key))

        if key == "s":
            raise RuntimeError("blocked")

    monkeypatch.setattr(keys.pdi, "keyDown", key_down)
    monkeypatch.setattr(keys.pdi, "keyUp", lambda key: calls.append(("up", key)))

    keys.tap("ctrl+s")

    assert calls == [("down", "ctrl"), ("down", "s"), ("up", "ctrl")]


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


def test_type_text_posts_background_characters(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(keys.win32api, "MapVirtualKey", lambda vk_code, map_type: 28)
    monkeypatch.setattr(
        keys.win32gui,
        "PostMessage",
        lambda hwnd, message, wparam, lparam: calls.append((hwnd, message, wparam, lparam)),
    )

    keys.type_text("A\n好", hwnd=123)

    assert calls == [
        (123, keys.win32con.WM_CHAR, ord("A"), 1),
        (123, keys.win32con.WM_KEYDOWN, 13, 1 | (28 << 16)),
        (123, keys.win32con.WM_KEYUP, 13, 1 | (28 << 16) | (1 << 30) | (1 << 31)),
        (123, keys.win32con.WM_CHAR, ord("好"), 1),
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


def test_held_keeps_combo_pressed_until_context_exits(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(keys.pdi, "keyDown", lambda key: calls.append(("down", key)))
    monkeypatch.setattr(keys.pdi, "keyUp", lambda key: calls.append(("up", key)))

    with keys.held("ctrl+space"):
        calls.append(("inside", "combo"))

    assert calls == [("down", "ctrl"), ("down", "space"), ("inside", "combo"), ("up", "space"), ("up", "ctrl")]


def test_held_posts_background_key_messages(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(keys.win32api, "MapVirtualKey", lambda vk_code, map_type: 57)
    monkeypatch.setattr(
        keys.win32gui,
        "PostMessage",
        lambda hwnd, message, wparam, lparam: calls.append((hwnd, message, wparam, lparam)),
    )

    with keys.held("space", hwnd=123):
        calls.append(("inside", "space"))

    assert calls == [
        (123, keys.win32con.WM_KEYDOWN, 32, 1 | (57 << 16)),
        ("inside", "space"),
        (123, keys.win32con.WM_KEYUP, 32, 1 | (57 << 16) | (1 << 30) | (1 << 31)),
    ]


def test_held_background_releases_and_reraises_unsupported_key(monkeypatch) -> None:
    releases = []
    monkeypatch.setattr(keys, "parse_key_combo", lambda key: ["ctrl", "bad"])
    monkeypatch.setattr(keys, "post_key", lambda hwnd, key, is_down: key != "bad")
    monkeypatch.setattr(keys, "release_background_keys", lambda hwnd, pressed: releases.append(list(pressed)))

    with pytest.raises(RuntimeError, match="unsupported background key"), keys.held("ctrl+bad", hwnd=123):
        pass

    assert releases == [["ctrl"], ["ctrl"]]


def test_held_background_releases_on_post_exception(monkeypatch) -> None:
    releases = []

    def post_key(hwnd: int, key: str, is_down: bool) -> bool:
        if key == "bad":
            raise RuntimeError("blocked")

        return True

    monkeypatch.setattr(keys, "parse_key_combo", lambda key: ["ctrl", "bad"])
    monkeypatch.setattr(keys, "post_key", post_key)
    monkeypatch.setattr(keys, "release_background_keys", lambda hwnd, pressed: releases.append(list(pressed)))

    with pytest.raises(RuntimeError, match="blocked"), keys.held("ctrl+bad", hwnd=123):
        pass

    assert releases == [["ctrl"]]


def test_held_reraises_key_down_failure(monkeypatch) -> None:
    def raise_key_down(key: str) -> None:
        raise RuntimeError("blocked")

    monkeypatch.setattr(keys.pdi, "keyDown", raise_key_down)

    with pytest.raises(RuntimeError, match="blocked"), keys.held("space"):
        pass


def test_held_releases_pressed_combo_keys_when_later_key_down_fails(monkeypatch) -> None:
    calls = []

    def key_down(key: str) -> None:
        calls.append(("down", key))

        if key == "s":
            raise RuntimeError("blocked")

    monkeypatch.setattr(keys.pdi, "keyDown", key_down)
    monkeypatch.setattr(keys.pdi, "keyUp", lambda key: calls.append(("up", key)))

    with pytest.raises(RuntimeError, match="blocked"), keys.held("ctrl+s"):
        pass

    assert calls == [("down", "ctrl"), ("down", "s"), ("up", "ctrl")]


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


def test_is_valid_key_accepts_combo_when_all_parts_are_supported(monkeypatch) -> None:
    monkeypatch.setattr(keys.pdi, "isValidKey", lambda key: key in {"ctrl", "shift", "s"})

    assert keys.is_valid_key("control+shift+s") is True
    assert keys.is_valid_key("ctrl+bad") is False
    assert keys.is_valid_key("") is False


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
    monkeypatch.setattr(keys.pdi, "mouseDown", lambda button: calls.append(("down", button)))
    monkeypatch.setattr(keys.pdi, "mouseUp", lambda button: calls.append(("up", button)))

    keys.mouse_click(button, 10, 20)

    assert calls == [("move", 10, 20), ("down", expected_call), ("up", expected_call)]


def test_mouse_click_stops_when_move_fails(monkeypatch) -> None:
    calls = []

    def raise_move(x: int, y: int) -> None:
        raise RuntimeError("blocked")

    monkeypatch.setattr(keys.pdi, "moveTo", raise_move)
    monkeypatch.setattr(keys.pdi, "mouseDown", lambda button="left": calls.append("down"))
    monkeypatch.setattr(keys.pdi, "mouseUp", lambda button="left": calls.append("up"))

    keys.mouse_click("left", 10, 20)

    assert calls == []


def test_mouse_click_posts_background_mouse_messages(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(keys.win32gui, "ScreenToClient", lambda hwnd, point: (5, 7))
    monkeypatch.setattr(keys.win32api, "MAKELONG", lambda low, high: low | (high << 16))
    monkeypatch.setattr(
        keys.win32gui,
        "PostMessage",
        lambda hwnd, message, wparam, lparam: calls.append((hwnd, message, wparam, lparam)),
    )

    keys.mouse_click("left", 100, 200, hwnd=123)

    assert calls == [
        (123, keys.win32con.WM_MOUSEMOVE, 0, 5 | (7 << 16)),
        (123, keys.win32con.WM_LBUTTONDOWN, keys.win32con.MK_LBUTTON, 5 | (7 << 16)),
        (123, keys.win32con.WM_LBUTTONUP, 0, 5 | (7 << 16)),
    ]


def test_post_mouse_click_rejects_unknown_button() -> None:
    assert keys.post_mouse_click(123, "side", 10, 20) is False


def test_mouse_click_background_suppresses_post_errors(monkeypatch) -> None:
    def raise_click(hwnd: int, button: str, x: int, y: int) -> bool:
        raise RuntimeError("blocked")

    monkeypatch.setattr(keys, "post_mouse_click", raise_click)

    keys.mouse_click("left", 10, 20, hwnd=123)


def test_mouse_click_logs_click_failure(monkeypatch) -> None:
    calls = []

    monkeypatch.setattr(keys.pdi, "moveTo", lambda x, y: calls.append(("move", x, y)))

    def raise_down(button="left") -> None:
        raise RuntimeError("blocked")

    monkeypatch.setattr(keys.pdi, "mouseDown", raise_down)
    monkeypatch.setattr(keys.pdi, "mouseUp", lambda button="left": calls.append("up"))

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


def test_mouse_move_posts_background_mouse_move(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(keys.win32gui, "ScreenToClient", lambda hwnd, point: (6, 8))
    monkeypatch.setattr(keys.win32api, "MAKELONG", lambda low, high: low | (high << 16))
    monkeypatch.setattr(
        keys.win32gui,
        "PostMessage",
        lambda hwnd, message, wparam, lparam: calls.append((hwnd, message, wparam, lparam)),
    )

    keys.mouse_move(100, 200, hwnd=123)

    assert calls == [(123, keys.win32con.WM_MOUSEMOVE, 0, 6 | (8 << 16))]


def test_mouse_move_background_suppresses_post_errors(monkeypatch) -> None:
    def raise_post(hwnd, message, wparam, lparam) -> None:
        raise RuntimeError("blocked")

    monkeypatch.setattr(keys.win32gui, "ScreenToClient", lambda hwnd, point: (6, 8))
    monkeypatch.setattr(keys.win32api, "MAKELONG", lambda low, high: low | (high << 16))
    monkeypatch.setattr(keys.win32gui, "PostMessage", raise_post)

    keys.mouse_move(100, 200, hwnd=123)


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


def test_mouse_scroll_posts_background_wheel_messages(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(
        keys.win32gui, "PostMessage", lambda hwnd, message, wparam, lparam: calls.append((wparam, lparam))
    )
    monkeypatch.setattr(keys, "sleep_ms", lambda ms: calls.append(("sleep", ms)))

    keys.mouse_scroll(-2, interval_ms=25, hwnd=123)

    assert calls == [(-120 << 16, 0), ("sleep", 25), (-120 << 16, 0), ("sleep", 25)]


def test_mouse_scroll_stops_on_failure(monkeypatch) -> None:
    calls = []

    def fake_scroll(clicks: int) -> None:
        calls.append(clicks)
        raise RuntimeError("blocked")

    monkeypatch.setattr(keys.pdi, "scroll", fake_scroll)
    monkeypatch.setattr(keys, "sleep_ms", lambda ms: calls.append(ms))

    keys.mouse_scroll(2, interval_ms=25)

    assert calls == [1]
