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
