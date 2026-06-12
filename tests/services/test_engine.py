import threading
from typing import cast

import numpy as np
import pytest

from remaku.core.capture import Grabber
from remaku.core.window import Rect
from remaku.services import engine
from remaku.services.engine import Engine, Stopped, StopReason


class SampleEngine(Engine):
    def loop(self) -> None:
        self.finish(StopReason.DONE, "done")

    def capture_once(self):
        if self.capture_rect is None:
            return None
        return self.grabber.grab(self.capture_rect)


class FakeGrabber:
    def __init__(self, frame) -> None:
        self.frame = frame

    def grab(self, rect):
        return self.frame


class FakeConfigModel:
    class Config:
        class Input:
            jitter_ms = 7

        input = Input()

    config = Config()


def test_update_and_get_status_return_copy() -> None:
    runner = SampleEngine()

    runner.update(running=True, state="waiting")
    status = runner.get_status()
    status.state = "mutated"

    assert runner.status.running is True
    assert runner.status.state == "waiting"


def test_finish_sets_reason_and_message(qtbot) -> None:
    runner = SampleEngine()
    runner.status.running = True

    with qtbot.waitSignal(engine.event_bus.macro_running_changed, timeout=100) as blocker:
        runner.finish(StopReason.DONE, "done")

    assert runner.status.running is False
    assert runner.status.last_reason == "done"
    assert runner.status.message == "done"
    assert blocker.args == [False]


def test_sleep_raises_stopped_when_stop_event_set() -> None:
    runner = SampleEngine()
    runner.stop()

    with pytest.raises(Stopped):
        runner.sleep(100)


def test_tap_delegates_to_keys_with_configured_jitter(monkeypatch) -> None:
    runner = SampleEngine()
    calls = []
    monkeypatch.setattr(engine, "config_model", FakeConfigModel())
    monkeypatch.setattr(engine.keys, "tap", lambda key, hold_ms, jitter_ms: calls.append((key, hold_ms, jitter_ms)))

    runner.tap("enter", hold_ms=120)

    assert calls == [("enter", 120, 7)]


def test_foreground_tick_waits_until_window_is_foreground(monkeypatch) -> None:
    runner = SampleEngine()
    runner.found_window = object()
    foreground_states = iter([False, False, True])
    monkeypatch.setattr(engine.window, "is_foreground", lambda found_window: next(foreground_states))
    sleeps = []
    runner.sleep = lambda ms: sleeps.append(ms)

    runner.foreground_tick()

    assert runner.status.state == "running"
    assert runner.status.message == ""
    assert sleeps == [250]


def test_capture_tick_returns_gray_frame_when_foreground(monkeypatch) -> None:
    runner = SampleEngine()
    frame = np.ones((2, 2, 3), dtype=np.uint8)
    gray = np.ones((2, 2), dtype=np.uint8)
    runner.found_window = object()
    runner.capture_rect = Rect(0, 0, 2, 2)
    runner.grabber = cast(Grabber, FakeGrabber(frame))
    monkeypatch.setattr(engine.window, "is_foreground", lambda found_window: True)
    monkeypatch.setattr(engine.vision, "to_gray", lambda image: gray)

    assert runner.capture_tick() is gray
    assert runner.status.state == "running"


def test_capture_tick_returns_none_when_window_not_foreground(monkeypatch) -> None:
    runner = SampleEngine()
    runner.found_window = object()
    runner.capture_rect = Rect(0, 0, 2, 2)
    runner.grabber = cast(Grabber, FakeGrabber(None))
    sleeps = []
    monkeypatch.setattr(engine.window, "is_foreground", lambda found_window: False)
    runner.sleep = lambda ms: sleeps.append(ms)

    assert runner.capture_tick() is None
    assert runner.status.state == "waiting_foreground"
    assert sleeps == [250]


def test_start_does_not_create_second_thread_when_running(monkeypatch) -> None:
    runner = SampleEngine()
    runner.thread = threading.Thread()
    monkeypatch.setattr(runner.thread, "is_alive", lambda: True)
    created = []
    monkeypatch.setattr(engine.threading, "Thread", lambda **kwargs: created.append(kwargs))

    runner.start()

    assert created == []


class FakeThread:
    def __init__(self, target, name: str, daemon: bool) -> None:
        self.target = target
        self.name = name
        self.daemon = daemon
        self.start_calls = 0

    def is_alive(self) -> bool:
        return False

    def start(self) -> None:
        self.start_calls += 1


def test_start_creates_daemon_thread(monkeypatch) -> None:
    runner = SampleEngine()
    threads = []

    def make_thread(target, name: str, daemon: bool) -> FakeThread:
        thread = FakeThread(target, name, daemon)
        threads.append(thread)
        return thread

    monkeypatch.setattr(engine.threading, "Thread", make_thread)

    runner.start()

    assert runner.status.running is True
    assert runner.thread is threads[0]
    assert threads[0].target == runner.run_safe
    assert threads[0].daemon is True
    assert threads[0].start_calls == 1


def test_run_safe_finishes_with_exception_message() -> None:
    class FailingEngine(Engine):
        def loop(self) -> None:
            raise RuntimeError("boom")

    runner = FailingEngine()
    runner.status.running = True

    runner.run_safe()

    assert runner.status.running is False
    assert runner.status.last_reason == StopReason.ERROR.value
    assert runner.status.message == "Error: boom"


def test_run_safe_preserves_stopped_reason() -> None:
    class StoppingEngine(Engine):
        def loop(self) -> None:
            raise Stopped

    runner = StoppingEngine()
    runner.status.running = True

    runner.run_safe()

    assert runner.status.running is False
    assert runner.status.last_reason == StopReason.USER.value
    assert runner.status.message == "user_stopped"


def test_stop_sets_event() -> None:
    runner = SampleEngine()

    runner.stop()

    assert runner.stop_event.is_set()


def test_foreground_tick_does_nothing_without_window(monkeypatch) -> None:
    runner = SampleEngine()
    runner.found_window = None
    foreground_calls = []
    sleep_calls = []

    def is_foreground_side_effect(window):
        foreground_calls.append(window)
        return True

    monkeypatch.setattr(engine.window, "is_foreground", is_foreground_side_effect)
    runner.sleep = lambda ms: sleep_calls.append(ms)

    runner.foreground_tick()

    assert foreground_calls == [None, None]
    assert runner.status.state == "running"
    assert sleep_calls == []


def test_capture_once_grabs_current_rect() -> None:
    frame = np.ones((2, 2, 3), dtype=np.uint8)
    runner = SampleEngine()
    runner.capture_rect = Rect(0, 0, 2, 2)
    runner.grabber = cast(Grabber, FakeGrabber(frame))

    assert runner.capture_once() is frame


def test_capture_tick_returns_none_when_grabber_has_no_frame(monkeypatch) -> None:
    runner = SampleEngine()
    runner.found_window = object()
    runner.capture_rect = Rect(0, 0, 2, 2)
    runner.grabber = cast(Grabber, FakeGrabber(None))
    monkeypatch.setattr(engine.window, "is_foreground", lambda found_window: True)

    assert runner.capture_tick() is None
