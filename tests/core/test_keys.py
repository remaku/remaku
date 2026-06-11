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


def test_is_valid_key_delegates_to_pydirectinput(monkeypatch) -> None:
    monkeypatch.setattr(keys.pdi, "isValidKey", lambda key: key == "enter")

    assert keys.is_valid_key("enter") is True
    assert keys.is_valid_key("nope") is False
