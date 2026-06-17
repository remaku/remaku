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
        class Capture:
            fps = 60

        class Input:
            jitter_ms = 7

        capture = Capture()
        input = Input()

    config = Config()


class ClosingGrabber:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class FakeWindow:
    _hWnd = 123


def test_is_running_reports_live_thread(monkeypatch) -> None:
    runner = SampleEngine()
    runner.thread = threading.Thread()
    monkeypatch.setattr(runner.thread, "is_alive", lambda: True)

    assert runner.is_running() is True


def test_is_running_reports_stopped_without_live_thread() -> None:
    runner = SampleEngine()

    assert runner.is_running() is False


def test_update_and_get_status_return_copy() -> None:
    runner = SampleEngine()

    runner.update(running=True, state="waiting")
    status = runner.get_status()
    status.state = "mutated"

    assert runner.status.running is True, "status copy mutation should not change the engine running state"
    assert runner.status.state == "waiting", "status copy mutation should not change the engine state"


def test_get_status_updates_elapsed_when_running(monkeypatch) -> None:
    runner = SampleEngine()
    runner.start_time = 2.5
    runner.update(running=True)
    monkeypatch.setattr(engine.time, "monotonic", lambda: 7.0)

    assert runner.get_status().elapsed_s == 4.5


def test_finish_sets_reason_message_and_elapsed(qtbot, monkeypatch) -> None:
    runner = SampleEngine()
    runner.status.running = True
    runner.start_time = 3.0
    monkeypatch.setattr(engine.time, "monotonic", lambda: 8.0)

    with qtbot.waitSignal(engine.event_bus.macro_running_changed, timeout=100) as blocker:
        runner.finish(StopReason.DONE, "done")

    assert runner.status.running is False, "finish should mark the engine as stopped"
    assert runner.status.last_reason == "done"
    assert runner.status.message == "done"
    assert runner.status.elapsed_s == 5.0
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
    monkeypatch.setattr(
        engine.keys,
        "tap",
        lambda key, hold_ms, jitter_ms, hwnd=None: calls.append((key, hold_ms, jitter_ms, hwnd)),
    )

    runner.tap("enter", hold_ms=120)

    assert calls == [("enter", 120, 7, None)]


def test_input_hwnd_returns_target_only_when_background_input_enabled(monkeypatch) -> None:
    runner = SampleEngine()
    runner.found_window = FakeWindow()
    focus_calls = []
    monkeypatch.setattr(engine.window, "fake_focus", lambda found_window: focus_calls.append(found_window))

    assert runner.input_hwnd() == 123
    assert focus_calls == []

    runner.keep_target_focused = True
    assert runner.input_hwnd() == 123
    assert focus_calls == [runner.found_window]

    runner.background_input = False
    assert runner.input_hwnd() is None
    assert focus_calls == [runner.found_window]


def test_foreground_tick_refreshes_named_target_without_waiting_when_background_input_enabled(monkeypatch) -> None:
    runner = SampleEngine()
    runner.target_window = "Game"
    runner.found_window = object()
    refreshes = []
    runner.refresh_found_window = lambda: refreshes.append(True) or True

    runner.foreground_tick()

    assert runner.status.state == "running"
    assert runner.status.message == ""
    assert refreshes == [True]


def test_foreground_tick_waits_when_background_input_is_disabled(monkeypatch) -> None:
    runner = SampleEngine()
    runner.background_input = False
    runner.found_window = object()
    foreground_states = iter([False, False, True])
    monkeypatch.setattr(engine.window, "is_foreground", lambda found_window: next(foreground_states))
    sleeps = []
    runner.sleep = lambda ms, pause_callback=None, resume_callback=None: sleeps.append(ms)

    runner.foreground_tick()

    assert runner.status.state == "running"
    assert sleeps == [250]


def test_refresh_found_window_updates_handle_and_capture_rect(monkeypatch) -> None:
    runner = SampleEngine()
    runner.target_window = "Game"
    found_window = object()
    rect = Rect(1, 2, 3, 4)

    monkeypatch.setattr(engine.window, "find_target_window", lambda title: found_window)
    monkeypatch.setattr(engine.window, "client_rect", lambda handle: rect)

    assert runner.refresh_found_window() is True
    assert runner.found_window is found_window
    assert runner.capture_rect == rect


def test_refresh_found_window_returns_false_without_target_or_match(monkeypatch) -> None:
    runner = SampleEngine()
    find_calls = []
    monkeypatch.setattr(engine.window, "find_target_window", lambda title: find_calls.append(title))

    assert runner.refresh_found_window() is False
    assert find_calls == []

    runner.target_window = "Missing"
    assert runner.refresh_found_window() is False
    assert find_calls == ["Missing"]


def test_refresh_found_window_if_due_throttles_window_lookup(monkeypatch) -> None:
    runner = SampleEngine()
    runner.target_window = "Game"
    runner.last_window_refresh_at = 10.0
    calls = []
    monkeypatch.setattr(engine.time, "monotonic", lambda: 10.5)
    runner.refresh_found_window = lambda: calls.append("refresh") or True

    assert runner.refresh_found_window_if_due() is False
    assert calls == []

    monkeypatch.setattr(engine.time, "monotonic", lambda: 11.1)

    assert runner.refresh_found_window_if_due() is True
    assert calls == ["refresh"]


def test_capture_tick_returns_raw_frame_when_foreground(monkeypatch) -> None:
    runner = SampleEngine()
    frame = np.ones((2, 2, 3), dtype=np.uint8)
    runner.found_window = object()
    runner.capture_rect = Rect(0, 0, 2, 2)
    runner.grabber = cast(Grabber, FakeGrabber(frame))
    monkeypatch.setattr(engine.window, "is_foreground", lambda found_window: True)

    assert runner.capture_tick() is frame
    assert runner.status.state == "running"


def test_capture_tick_grabs_frame_when_window_not_foreground(monkeypatch) -> None:
    runner = SampleEngine()
    frame = np.ones((2, 2, 3), dtype=np.uint8)
    runner.found_window = object()
    runner.capture_rect = Rect(0, 0, 2, 2)
    runner.grabber = cast(Grabber, FakeGrabber(frame))
    monkeypatch.setattr(engine.window, "is_foreground", lambda found_window: False)

    assert runner.capture_tick() is frame
    assert runner.status.state == "running"


def test_capture_tick_waits_when_background_input_is_disabled_and_window_not_foreground(monkeypatch) -> None:
    runner = SampleEngine()
    runner.background_input = False
    runner.found_window = object()
    runner.capture_rect = Rect(0, 0, 2, 2)
    runner.grabber = cast(Grabber, FakeGrabber(np.ones((2, 2, 3), dtype=np.uint8)))
    sleeps = []
    monkeypatch.setattr(engine.window, "is_foreground", lambda found_window: False)
    runner.sleep = lambda ms, pause_callback=None, resume_callback=None: sleeps.append(ms)

    assert runner.capture_tick() is None
    assert runner.status.state == "waiting_foreground"
    assert sleeps == [250]


def test_capture_tick_fakes_focus_when_enabled(monkeypatch) -> None:
    runner = SampleEngine()
    frame = np.ones((2, 2, 3), dtype=np.uint8)
    runner.keep_target_focused = True
    runner.found_window = FakeWindow()
    runner.capture_rect = Rect(0, 0, 2, 2)
    runner.grabber = cast(Grabber, FakeGrabber(frame))
    focus_calls = []
    monkeypatch.setattr(engine.window, "fake_focus", lambda found_window: focus_calls.append(found_window))

    assert runner.capture_tick() is frame
    assert focus_calls == [runner.found_window]


def test_keep_target_focus_alive_throttles_focus_messages(monkeypatch) -> None:
    runner = SampleEngine()
    runner.keep_target_focused = True
    runner.found_window = FakeWindow()
    runner.last_fake_focus_at = 10.0
    focus_calls = []
    monkeypatch.setattr(engine.window, "fake_focus", lambda found_window: focus_calls.append(found_window))
    monkeypatch.setattr(engine.time, "monotonic", lambda: 10.5)

    runner.keep_target_focus_alive()

    assert focus_calls == []

    monkeypatch.setattr(engine.time, "monotonic", lambda: 11.1)
    runner.keep_target_focus_alive()

    assert focus_calls == [runner.found_window]


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

    assert runner.status.running is True, "start should mark the engine as running before launching the thread"
    assert runner.thread is threads[0]
    assert threads[0].target == runner.run_safe
    assert threads[0].daemon is True
    assert threads[0].start_calls == 1


def test_base_loop_raises_not_implemented() -> None:
    runner = Engine()

    with pytest.raises(NotImplementedError):
        runner.loop()


def test_run_safe_finishes_with_exception_message() -> None:
    class FailingEngine(Engine):
        def loop(self) -> None:
            raise RuntimeError("boom")

    runner = FailingEngine()
    runner.status.running = True

    runner.run_safe()

    assert runner.status.running is False, "run_safe should stop the engine after an unexpected error"
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


def test_foreground_tick_does_not_check_foreground(monkeypatch) -> None:
    runner = SampleEngine()
    runner.found_window = None
    foreground_calls = []

    def is_foreground_side_effect(window):
        foreground_calls.append(window)
        return True

    monkeypatch.setattr(engine.window, "is_foreground", is_foreground_side_effect)

    runner.foreground_tick()

    assert foreground_calls == []
    assert runner.status.state == "running"


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


def test_run_finishes_when_no_target_window_found(monkeypatch) -> None:
    runner = SampleEngine()
    finishes = []
    monkeypatch.setattr(engine.window, "find_target_window", lambda *args: None)
    runner.finish = lambda reason, message: finishes.append((reason, message))

    runner.run()

    assert finishes == [(StopReason.NO_WINDOW, "window_not_found")]


def test_run_finishes_on_elevation_mismatch(monkeypatch) -> None:
    runner = SampleEngine()
    found_window = object()
    finishes = []
    monkeypatch.setattr(engine.window, "find_target_window", lambda *args: found_window)
    monkeypatch.setattr(engine.window, "check_elevation_mismatch", lambda window: True)
    runner.finish = lambda reason, message: finishes.append((reason, message))

    runner.run()

    assert finishes == [(StopReason.ERROR, "elevation_mismatch")]


def test_run_finishes_when_template_is_missing(monkeypatch) -> None:
    runner = SampleEngine()
    runner.template_ids = ["one", "two"]
    found_window = object()
    finishes = []
    monkeypatch.setattr(engine.window, "find_target_window", lambda *args: found_window)
    monkeypatch.setattr(engine.window, "check_elevation_mismatch", lambda window: False)
    monkeypatch.setattr(engine.window, "client_rect", lambda window: Rect(0, 0, 100, 100))
    monkeypatch.setattr(engine.vision, "load_templates", lambda template_ids, engine_id: {"one": np.ones((1, 1))})
    runner.finish = lambda reason, message: finishes.append((reason, message))

    runner.run()

    assert finishes == [(StopReason.STALE, "missing_templates: two")]


def test_run_sets_runtime_fields_and_closes_grabber(monkeypatch) -> None:
    runner = SampleEngine()
    found_window = object()
    grabber = ClosingGrabber()
    monkeypatch.setattr(engine.window, "find_target_window", lambda *args: found_window)
    monkeypatch.setattr(engine.window, "check_elevation_mismatch", lambda window: False)
    monkeypatch.setattr(engine.window, "client_rect", lambda window: Rect(1, 2, 3, 4))
    monkeypatch.setattr(engine.capture, "make_grabber", lambda: grabber)
    monkeypatch.setattr(engine.window, "screen_resolution", lambda: (1920, 1080))

    runner.run()

    assert runner.found_window is found_window
    assert runner.capture_rect == Rect(1, 2, 3, 4)
    assert runner.templates == {}
    assert grabber.closed is True


def test_run_waits_for_named_target_without_requiring_foreground_when_background_input_enabled(monkeypatch) -> None:
    runner = SampleEngine()
    runner.target_window = "Game"
    found_window = object()
    windows = iter([None, found_window])
    sleeps = []
    monkeypatch.setattr(engine.window, "find_target_window", lambda *args: next(windows))
    monkeypatch.setattr(
        runner, "sleep", lambda ms, pause_callback=None, resume_callback=None: sleeps.append(ms) or None
    )
    monkeypatch.setattr(engine.window, "check_elevation_mismatch", lambda window: False)
    monkeypatch.setattr(engine.window, "client_rect", lambda window: Rect(1, 2, 3, 4))
    monkeypatch.setattr(engine.capture, "make_grabber", lambda: ClosingGrabber())
    monkeypatch.setattr(engine.window, "screen_resolution", lambda: (1920, 1080))

    runner.run()

    assert sleeps == [1000]
    assert runner.status.state == "waiting_window"


def test_run_waits_for_named_target_foreground_when_background_input_disabled(monkeypatch) -> None:
    runner = SampleEngine()
    runner.background_input = False
    runner.target_window = "Game"
    found_window = object()
    windows = iter([found_window, found_window])
    foreground = iter([False, True])
    sleeps = []
    monkeypatch.setattr(engine.window, "find_target_window", lambda *args: next(windows))
    monkeypatch.setattr(engine.window, "is_foreground", lambda window: next(foreground))
    monkeypatch.setattr(
        runner, "sleep", lambda ms, pause_callback=None, resume_callback=None: sleeps.append(ms) or None
    )
    monkeypatch.setattr(engine.window, "check_elevation_mismatch", lambda window: False)
    monkeypatch.setattr(engine.window, "client_rect", lambda window: Rect(1, 2, 3, 4))
    monkeypatch.setattr(engine.capture, "make_grabber", lambda: ClosingGrabber())
    monkeypatch.setattr(engine.window, "screen_resolution", lambda: (1920, 1080))

    runner.run()

    assert sleeps == [1000]
    assert runner.status.state == "waiting_foreground"


def test_run_stops_while_waiting_for_named_target(monkeypatch) -> None:
    runner = SampleEngine()
    runner.target_window = "Game"
    monkeypatch.setattr(engine.window, "find_target_window", lambda *args: None)
    runner.stop()

    with pytest.raises(Stopped):
        runner.run()


def test_sleep_remaining_raises_when_stop_event_set(monkeypatch) -> None:
    runner = SampleEngine()
    monkeypatch.setattr(engine.time, "monotonic", lambda: 10.0)
    runner.stop()

    with pytest.raises(Stopped):
        runner.sleep_remaining(9.5, 1.0)


def test_scale_template_uses_capture_size(monkeypatch) -> None:
    runner = SampleEngine()
    template = np.ones((2, 2), dtype=np.uint8)
    frame = np.ones((4, 4), dtype=np.uint8)
    scaled = np.ones((3, 3), dtype=np.uint8)
    runner.template_capture_sizes = cast(dict[str, tuple[int, int] | None], {"button": (100, 50)})
    monkeypatch.setattr(engine.vision, "scale_template", lambda source, shape, size: scaled)

    assert runner.scale_template("missing", template, frame) is template
    assert runner.scale_template("button", template, frame) is scaled


def test_wait_for_template_matches_and_updates_status(monkeypatch) -> None:
    runner = SampleEngine()
    frame = np.ones((4, 4), dtype=np.uint8)
    template = np.ones((2, 2), dtype=np.uint8)
    runner.templates = {"button": template}
    runner.template_capture_sizes = {}
    monkeypatch.setattr(engine, "config_model", FakeConfigModel())
    monkeypatch.setattr(runner, "capture_tick", lambda: frame)
    monkeypatch.setattr(runner, "sleep_remaining", lambda tick_start, period: None)
    monkeypatch.setattr(engine.vision, "match_template", lambda image, tpl, mode="grayscale": (0.95, (0, 0)))

    assert runner.wait_for_template("button", timeout_ms=1000, threshold=0.9) is True
    assert runner.status.score == 0.95
    assert runner.status.match_id == "button"


def test_wait_for_template_retries_empty_frame_and_low_score(monkeypatch) -> None:
    runner = SampleEngine()
    frame = np.ones((4, 4), dtype=np.uint8)
    template = np.ones((2, 2), dtype=np.uint8)
    runner.templates = {"button": template}
    runner.template_capture_sizes = {}
    frames = iter([None, frame])
    sleep_calls = []
    monotonic_values = iter([0.0, 0.1, 0.2, 0.3, 0.4, 2.0])
    monkeypatch.setattr(engine, "config_model", FakeConfigModel())
    monkeypatch.setattr(engine.time, "monotonic", lambda: next(monotonic_values))
    monkeypatch.setattr(runner, "capture_tick", lambda: next(frames))
    monkeypatch.setattr(runner, "sleep_remaining", lambda tick_start, period: sleep_calls.append((tick_start, period)))
    monkeypatch.setattr(engine.vision, "match_template", lambda image, tpl, mode="grayscale": (0.2, (0, 0)))

    assert runner.wait_for_template("button", timeout_ms=1000, threshold=0.9) is False
    assert runner.status.score == 0.2
    assert runner.status.match_id == "button"
    assert sleep_calls == [(0.2, 1.0 / 60), (0.4, 1.0 / 60)]


def test_wait_for_template_times_out_or_stops(monkeypatch) -> None:
    runner = SampleEngine()
    runner.templates = {"button": np.ones((2, 2), dtype=np.uint8)}
    monkeypatch.setattr(engine, "config_model", FakeConfigModel())

    assert runner.wait_for_template("button", timeout_ms=0, threshold=0.9) is False

    runner.stop()
    with pytest.raises(Stopped):
        runner.wait_for_template("button", timeout_ms=1000, threshold=0.9)


def test_wait_for_any_returns_best_matching_template(monkeypatch) -> None:
    runner = SampleEngine()
    frame = np.ones((4, 4), dtype=np.uint8)
    runner.templates = {"one": np.ones((1, 1), dtype=np.uint8), "two": np.ones((2, 2), dtype=np.uint8)}
    runner.template_capture_sizes = {}
    scores = {1: 0.2, 2: 0.91}
    monkeypatch.setattr(engine, "config_model", FakeConfigModel())
    monkeypatch.setattr(runner, "capture_tick", lambda: frame)
    monkeypatch.setattr(runner, "sleep_remaining", lambda tick_start, period: None)
    monkeypatch.setattr(
        engine.vision,
        "match_template",
        lambda image, tpl, mode="grayscale": (scores[tpl.shape[0]], (0, 0)),
    )

    assert runner.wait_for_any(["one", "two"], timeout_ms=1000, threshold=0.9) == "two"
    assert runner.status.score == 0.91
    assert runner.status.match_id == "two"


def test_wait_for_any_retries_empty_frame_and_low_score(monkeypatch) -> None:
    runner = SampleEngine()
    frame = np.ones((4, 4), dtype=np.uint8)
    runner.templates = {"one": np.ones((1, 1), dtype=np.uint8), "two": np.ones((2, 2), dtype=np.uint8)}
    runner.template_capture_sizes = {}
    frames = iter([None, frame])
    sleep_calls = []
    monotonic_values = iter([0.0, 0.1, 0.2, 0.3, 0.4, 2.0])
    scores = {1: 0.2, 2: 0.4}
    monkeypatch.setattr(engine, "config_model", FakeConfigModel())
    monkeypatch.setattr(engine.time, "monotonic", lambda: next(monotonic_values))
    monkeypatch.setattr(runner, "capture_tick", lambda: next(frames))
    monkeypatch.setattr(runner, "sleep_remaining", lambda tick_start, period: sleep_calls.append((tick_start, period)))
    monkeypatch.setattr(
        engine.vision,
        "match_template",
        lambda image, tpl, mode="grayscale": (scores[tpl.shape[0]], (0, 0)),
    )

    assert runner.wait_for_any(["one", "two"], timeout_ms=1000, threshold=0.9) is None
    assert runner.status.score == 0.4
    assert runner.status.match_id == "two"
    assert sleep_calls == [(0.2, 1.0 / 60), (0.4, 1.0 / 60)]


def test_wait_for_any_times_out_or_stops(monkeypatch) -> None:
    runner = SampleEngine()
    runner.templates = {"one": np.ones((1, 1), dtype=np.uint8)}
    monkeypatch.setattr(engine, "config_model", FakeConfigModel())

    assert runner.wait_for_any(["one"], timeout_ms=0, threshold=0.9) is None

    runner.stop()
    with pytest.raises(Stopped):
        runner.wait_for_any(["one"], timeout_ms=1000, threshold=0.9)


def test_build_template_capture_sizes_uses_current_screen_resolution(monkeypatch) -> None:
    runner = SampleEngine()
    runner.templates = {"one": np.ones((1, 1)), "two": np.ones((1, 1))}
    monkeypatch.setattr(engine.window, "screen_resolution", lambda: (800, 600))

    assert runner.build_template_capture_sizes() == {"one": (800, 600), "two": (800, 600)}
