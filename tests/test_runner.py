import threading
import time
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

import config
from runner import Status, StepRunner, Stopped, StopReason
from window import Rect


class TestStatus:
    def test_defaults(self):
        s = Status()
        assert s.running is False
        assert s.state == "-"
        assert s.score == 0.0
        assert s.progress == 0


class TestStepRunner:
    def make_runner(self):
        conf = config.get_defaults()
        runner = StepRunner(conf)
        runner.name = "test"
        runner.template_names = ["dummy"]
        return runner

    def test_initial_status(self):
        runner = self.make_runner()
        s = runner.get_status()
        assert s.running is False
        assert s.last_reason == ""

    def test_update_fields(self):
        runner = self.make_runner()
        runner.update(state="loading", score=0.95)
        s = runner.get_status()
        assert s.state == "loading"
        assert s.score == 0.95

    def test_finish_sets_reason(self):
        runner = self.make_runner()
        runner.start_time = time.monotonic() - 1.0
        runner.finish(StopReason.DONE, "done")
        s = runner.get_status()
        assert s.running is False
        assert s.last_reason == "done"
        assert s.message == "done"
        assert s.elapsed_s >= 1.0

    def test_finish_user_stopped(self):
        runner = self.make_runner()
        runner.start_time = time.monotonic()
        runner.finish_user_stopped()
        s = runner.get_status()
        assert s.last_reason == StopReason.USER.value

    def test_stop_sets_event(self):
        runner = self.make_runner()
        assert not runner.stop_evt.is_set()
        runner.stop()
        assert runner.stop_evt.is_set()

    def test_start_sets_status(self):
        runner = self.make_runner()
        # Override run_safe to do nothing (avoid actual window/capture)
        runner.run_safe = lambda: None
        runner.start()
        assert runner.thread is not None
        runner.thread.join(timeout=1)
        s = runner.get_status()
        assert s.progress == 0

    def test_start_ignores_if_running(self):
        runner = self.make_runner()
        evt = threading.Event()
        runner.thread = threading.Thread(target=evt.wait, daemon=True)
        runner.thread.start()
        try:
            # start should return immediately without resetting
            runner.start()
            assert runner.thread.is_alive()
        finally:
            evt.set()
            runner.thread.join(timeout=1)

    def test_is_running_false_initially(self):
        runner = self.make_runner()
        assert runner.is_running() is False

    def test_is_running_true_when_thread_alive(self):
        runner = self.make_runner()
        evt = threading.Event()
        runner.thread = threading.Thread(target=evt.wait, daemon=True)
        runner.thread.start()
        try:
            assert runner.is_running() is True
        finally:
            evt.set()
            runner.thread.join(timeout=1)

    def test_sleep_raises_stopped_when_event_set(self):
        runner = self.make_runner()
        runner.stop_evt.set()
        with pytest.raises(Stopped):
            runner.sleep(1000)

    def test_sleep_completes_when_not_stopped(self):
        runner = self.make_runner()
        t0 = time.monotonic()
        runner.sleep(10)
        assert time.monotonic() - t0 < 0.5

    def test_sleep_remaining_raises_stopped(self):
        runner = self.make_runner()
        runner.stop_evt.set()
        with pytest.raises(Stopped):
            runner.sleep_remaining(time.monotonic(), 1.0)

    def test_sleep_remaining_no_wait_if_elapsed(self):
        runner = self.make_runner()
        # tick_start far in the past => elapsed > period => no wait
        runner.sleep_remaining(time.monotonic() - 10, 0.1)


class TestRunMethod:
    """Test StepRunner.run() branches (mocking external dependencies)."""

    def make_runner(self):
        conf = config.get_defaults()
        runner = StepRunner(conf)
        runner.name = "test"
        runner.template_names = []
        return runner

    def test_no_window_finishes(self):
        runner = self.make_runner()
        runner.start_time = time.monotonic()
        with patch("runner.window.find_target_window", return_value=None):
            runner.run()
        s = runner.get_status()
        assert s.last_reason == StopReason.NO_WINDOW.value

    def test_elevation_mismatch_finishes(self):
        runner = self.make_runner()
        runner.start_time = time.monotonic()
        mock_win = MagicMock()
        with (
            patch("runner.window.find_target_window", return_value=mock_win),
            patch("runner.window.check_elevation_mismatch", return_value=True),
        ):
            runner.run()
        s = runner.get_status()
        assert s.last_reason == StopReason.ERROR.value
        assert "permission" in s.message.lower()

    def test_missing_templates_finishes(self):
        runner = self.make_runner()
        runner.template_names = ["a", "b"]
        runner.start_time = time.monotonic()
        mock_win = MagicMock()
        with (
            patch("runner.window.find_target_window", return_value=mock_win),
            patch("runner.window.check_elevation_mismatch", return_value=False),
            patch("runner.window.client_rect", return_value=MagicMock(width=100, height=100)),
            patch("runner.vision.load_templates", return_value={"a": None}),
        ):
            runner.run()
        s = runner.get_status()
        assert s.last_reason == StopReason.STALE.value
        assert "b" in s.message

    def test_run_safe_catches_exception(self):
        runner = self.make_runner()
        runner.start_time = time.monotonic()
        runner.status.running = True
        with patch.object(runner, "run", side_effect=RuntimeError("boom")):
            runner.run_safe()
        s = runner.get_status()
        assert s.last_reason == StopReason.ERROR.value
        assert "boom" in s.message

    def test_run_safe_catches_stopped(self):
        runner = self.make_runner()
        runner.start_time = time.monotonic()
        runner.status.running = True
        with patch.object(runner, "run", side_effect=Stopped):
            runner.run_safe()
        s = runner.get_status()
        assert s.last_reason == StopReason.USER.value

    def test_window_found_no_title(self):
        """When target_title is empty, run() finds the foreground window."""
        runner = self.make_runner()
        runner.start_time = time.monotonic()
        mock_win = MagicMock()
        with (
            patch("runner.window.find_target_window", return_value=mock_win) as mock_find,
            patch("runner.window.check_elevation_mismatch", return_value=False),
            patch("runner.window.client_rect", return_value=MagicMock(width=100, height=100)),
            patch("runner.capture.make_grabber") as mock_make_grabber,
        ):
            mock_grabber = MagicMock()
            mock_make_grabber.return_value = mock_grabber
            runner.loop = lambda: None
            runner.run()
        mock_find.assert_called_once_with()
        assert runner.win is mock_win

    def test_window_found_with_title_not_foreground(self):
        """When target window exists but is not foreground, run() waits."""
        runner = self.make_runner()
        runner.target_window = "Game"
        runner.start_time = time.monotonic()
        mock_win = MagicMock()
        call_count = 0

        def find_side_effect(title=""):
            nonlocal call_count
            call_count += 1
            return mock_win

        def foreground_side_effect(win):
            return call_count >= 2

        with (
            patch("runner.window.find_target_window", side_effect=find_side_effect),
            patch("runner.window.is_foreground", side_effect=foreground_side_effect),
            patch("runner.window.check_elevation_mismatch", return_value=False),
            patch("runner.window.client_rect", return_value=MagicMock(width=100, height=100)),
            patch("runner.capture.make_grabber") as mock_make_grabber,
            patch.object(runner.stop_evt, "wait", return_value=False),
        ):
            mock_grabber = MagicMock()
            mock_make_grabber.return_value = mock_grabber
            runner.loop = lambda: None
            runner.run()
        assert call_count == 2
        assert runner.win is mock_win

    def test_window_found_with_title_foreground(self):
        """When target window is already foreground, run() proceeds immediately."""
        runner = self.make_runner()
        runner.target_window = "Game"
        runner.start_time = time.monotonic()
        mock_win = MagicMock()
        with (
            patch("runner.window.find_target_window", return_value=mock_win),
            patch("runner.window.is_foreground", return_value=True),
            patch("runner.window.check_elevation_mismatch", return_value=False),
            patch("runner.window.client_rect", return_value=MagicMock(width=100, height=100)),
            patch("runner.capture.make_grabber") as mock_make_grabber,
        ):
            mock_grabber = MagicMock()
            mock_make_grabber.return_value = mock_grabber
            runner.loop = lambda: None
            runner.run()
        assert runner.win is mock_win

    def test_grabber_init_failure(self):
        runner = self.make_runner()
        runner.start_time = time.monotonic()
        mock_win = MagicMock()
        with (
            patch("runner.window.find_target_window", return_value=mock_win),
            patch("runner.window.check_elevation_mismatch", return_value=False),
            patch("runner.window.client_rect", return_value=MagicMock(width=100, height=100)),
            patch("runner.capture.make_grabber", side_effect=RuntimeError("grabber fail")),
        ):
            runner.loop = lambda: None
            with pytest.raises(RuntimeError, match="grabber fail"):
                runner.run()

    def test_stopped_while_waiting_foreground(self):
        runner = self.make_runner()
        runner.target_window = "Game"
        runner.start_time = time.monotonic()
        mock_win = MagicMock()
        with (
            patch("runner.window.find_target_window", return_value=mock_win),
            patch("runner.window.is_foreground", return_value=False),
            patch.object(runner.stop_evt, "wait", return_value=True),
            pytest.raises(Stopped),
        ):
            runner.run()

    def test_template_capture_sizes_populated(self):
        runner = self.make_runner()
        runner.start_time = time.monotonic()
        runner.template_names = ["btn"]
        object.__setattr__(
            runner,
            "macro",
            {
                "templates": {
                    "btn": {"capture_width": 1920, "capture_height": 1080},
                }
            },
        )
        mock_win = MagicMock()
        with (
            patch("runner.window.find_target_window", return_value=mock_win),
            patch("runner.window.check_elevation_mismatch", return_value=False),
            patch("runner.window.client_rect", return_value=MagicMock(width=100, height=100)),
            patch("runner.vision.load_templates", return_value={"btn": np.zeros((10, 10), dtype=np.uint8)}),
            patch("runner.capture.make_grabber") as mock_make_grabber,
        ):
            mock_grabber = MagicMock()
            mock_make_grabber.return_value = mock_grabber
            runner.loop = lambda: None
            runner.run()
        assert runner.template_capture_sizes["btn"] == (1920, 1080)

    def test_template_capture_sizes_none_when_missing(self):
        runner = self.make_runner()
        runner.start_time = time.monotonic()
        runner.template_names = ["btn"]
        object.__setattr__(runner, "macro", {"templates": {}})
        mock_win = MagicMock()
        with (
            patch("runner.window.find_target_window", return_value=mock_win),
            patch("runner.window.check_elevation_mismatch", return_value=False),
            patch("runner.window.client_rect", return_value=MagicMock(width=100, height=100)),
            patch("runner.vision.load_templates", return_value={"btn": np.zeros((10, 10), dtype=np.uint8)}),
            patch("runner.capture.make_grabber") as mock_make_grabber,
        ):
            mock_grabber = MagicMock()
            mock_make_grabber.return_value = mock_grabber
            runner.loop = lambda: None
            runner.run()
        assert runner.template_capture_sizes["btn"] is None

    def test_loop_not_implemented(self):
        runner = self.make_runner()
        with pytest.raises(NotImplementedError):
            runner.loop()


# ---------------------------------------------------------------------------
# wait_for_template
# ---------------------------------------------------------------------------


class TestWaitForTemplate:
    def make_runner(self):
        conf = config.get_defaults()
        runner = StepRunner(conf)
        runner.name = "test"
        runner.template_names = ["btn"]
        runner.templates = {"btn": np.zeros((10, 10), dtype=np.uint8)}
        runner.template_capture_sizes = {}
        runner.grabber = MagicMock()
        runner.win = MagicMock()
        runner.rect = Rect(left=0, top=0, width=100, height=100)
        runner.status.running = True
        return runner

    def test_found(self):
        runner = self.make_runner()
        frame = np.zeros((100, 100), dtype=np.uint8)
        with (
            patch.object(runner, "capture_tick", return_value=frame),
            patch("runner.vision") as mock_vision,
            patch.object(runner, "sleep_remaining"),
        ):
            mock_vision.match_one.return_value = (0.99, (5, 5))
            result = runner.wait_for_template("btn", 5000)
        assert result is True

    def test_timeout(self):
        runner = self.make_runner()
        frame = np.zeros((100, 100), dtype=np.uint8)
        start = time.monotonic()
        t = start

        def mono():
            nonlocal t
            t += 0.05
            return t

        with (
            patch.object(runner, "capture_tick", return_value=frame),
            patch("runner.vision") as mock_vision,
            patch("runner.time") as mock_time,
            patch.object(runner, "sleep_remaining"),
        ):
            mock_vision.match_one.return_value = (0.1, (5, 5))
            mock_time.monotonic.side_effect = mono
            result = runner.wait_for_template("btn", 100)
        assert result is False

    def test_stopped_midway(self):
        runner = self.make_runner()
        frame = np.zeros((100, 100), dtype=np.uint8)
        runner.stop_evt.set()
        with (
            patch.object(runner, "capture_tick", return_value=frame),
            patch("runner.vision") as mock_vision,
            patch.object(runner, "sleep_remaining"),
        ):
            mock_vision.match_one.return_value = (0.1, (5, 5))
            with pytest.raises(Stopped):
                runner.wait_for_template("btn", 5000)

    def test_none_frame_then_match(self):
        runner = self.make_runner()
        frame = np.zeros((100, 100), dtype=np.uint8)
        call_count = 0

        def capture_side_effect():
            nonlocal call_count
            call_count += 1
            return None if call_count == 1 else frame

        with (
            patch.object(runner, "capture_tick", side_effect=capture_side_effect),
            patch("runner.vision") as mock_vision,
            patch.object(runner, "sleep_remaining"),
        ):
            mock_vision.match_one.return_value = (0.99, (5, 5))
            result = runner.wait_for_template("btn", 5000)
        assert result is True
        assert call_count == 2


# ---------------------------------------------------------------------------
# wait_for_any
# ---------------------------------------------------------------------------


class TestWaitForAny:
    def make_runner(self):
        conf = config.get_defaults()
        runner = StepRunner(conf)
        runner.name = "test"
        runner.template_names = ["a", "b"]
        runner.templates = {
            "a": np.zeros((10, 10), dtype=np.uint8),
            "b": np.zeros((10, 10), dtype=np.uint8),
        }
        runner.template_capture_sizes = {}
        runner.grabber = MagicMock()
        runner.win = MagicMock()
        runner.rect = Rect(left=0, top=0, width=100, height=100)
        runner.status.running = True
        return runner

    def test_returns_best_match(self):
        runner = self.make_runner()
        frame = np.zeros((100, 100), dtype=np.uint8)
        with (
            patch.object(runner, "capture_tick", return_value=frame),
            patch("runner.vision") as mock_vision,
            patch.object(runner, "sleep_remaining"),
        ):
            mock_vision.match_one.side_effect = [(0.5, (1, 1)), (0.99, (2, 2))]
            result = runner.wait_for_any(["a", "b"], 5000)
        assert result == "b"

    def test_none_found(self):
        runner = self.make_runner()
        frame = np.zeros((100, 100), dtype=np.uint8)
        start = time.monotonic()
        t = start

        def mono():
            nonlocal t
            t += 0.05
            return t

        with (
            patch.object(runner, "capture_tick", return_value=frame),
            patch("runner.vision") as mock_vision,
            patch("runner.time") as mock_time,
            patch.object(runner, "sleep_remaining"),
        ):
            mock_vision.match_one.return_value = (0.1, (5, 5))
            mock_time.monotonic.side_effect = mono
            result = runner.wait_for_any(["a", "b"], 100)
        assert result is None

    def test_stopped_midway(self):
        runner = self.make_runner()
        frame = np.zeros((100, 100), dtype=np.uint8)
        runner.stop_evt.set()
        with (
            patch.object(runner, "capture_tick", return_value=frame),
            patch("runner.vision") as mock_vision,
            patch.object(runner, "sleep_remaining"),
        ):
            mock_vision.match_one.return_value = (0.1, (5, 5))
            with pytest.raises(Stopped):
                runner.wait_for_any(["a", "b"], 5000)

    def test_none_frame_then_match(self):
        runner = self.make_runner()
        frame = np.zeros((100, 100), dtype=np.uint8)
        call_count = 0

        def capture_side_effect():
            nonlocal call_count
            call_count += 1
            return None if call_count == 1 else frame

        with (
            patch.object(runner, "capture_tick", side_effect=capture_side_effect),
            patch("runner.vision") as mock_vision,
            patch.object(runner, "sleep_remaining"),
        ):
            mock_vision.match_one.side_effect = [(0.1, (1, 1)), (0.99, (2, 2))]
            result = runner.wait_for_any(["a", "b"], 5000)
        assert result == "b"
        assert call_count == 2


# ---------------------------------------------------------------------------
# capture_tick
# ---------------------------------------------------------------------------


class TestCaptureTick:
    def make_runner(self):
        conf = config.get_defaults()
        runner = StepRunner(conf)
        runner.name = "test"
        runner.win = MagicMock()
        runner.grabber = MagicMock()
        runner.rect = Rect(left=0, top=0, width=100, height=100)
        runner.status = Status(running=True)
        return runner

    def test_returns_none_when_not_foreground(self):
        runner = self.make_runner()
        with (
            patch("runner.window.is_foreground", return_value=False),
            patch.object(runner, "sleep") as mock_sleep,
        ):
            result = runner.capture_tick()
        assert result is None
        mock_sleep.assert_called_once_with(250)

    def test_returns_none_when_grab_fails(self):
        runner = self.make_runner()
        with (
            patch("runner.window.is_foreground", return_value=True),
            patch.object(runner.grabber, "grab", return_value=None),
        ):
            result = runner.capture_tick()
        assert result is None

    def test_returns_gray_frame(self):
        runner = self.make_runner()
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        gray = np.zeros((100, 100), dtype=np.uint8)
        with (
            patch("runner.window.is_foreground", return_value=True),
            patch("runner.vision.to_gray", return_value=gray),
            patch.object(runner.grabber, "grab", return_value=frame),
        ):
            result = runner.capture_tick()
        assert result is gray


# ---------------------------------------------------------------------------
# scale_template
# ---------------------------------------------------------------------------


class TestScaleTemplate:
    def make_runner(self):
        conf = config.get_defaults()
        runner = StepRunner(conf)
        runner.name = "test"
        runner.template_capture_sizes = {}
        return runner

    def test_no_capture_size_returns_original(self):
        runner = self.make_runner()
        template = np.zeros((10, 10), dtype=np.uint8)
        frame = np.zeros((100, 100), dtype=np.uint8)
        result = runner.scale_template("btn", template, frame)
        assert result is template

    def test_with_capture_size_scales(self):
        runner = self.make_runner()
        runner.template_capture_sizes = {"btn": (1920, 1080)}
        template = np.zeros((10, 10), dtype=np.uint8)
        frame = np.zeros((100, 100), dtype=np.uint8)
        with patch("runner.vision.scale_template", return_value=np.zeros((5, 5), dtype=np.uint8)) as mock_scale:
            result = runner.scale_template("btn", template, frame)
        mock_scale.assert_called_once_with(template, frame.shape, (1920, 1080))
        assert result.shape == (5, 5)


# ---------------------------------------------------------------------------
# tap
# ---------------------------------------------------------------------------


class TestTap:
    def make_runner(self):
        conf = config.get_defaults()
        runner = StepRunner(conf)
        runner.name = "test"
        return runner

    def test_calls_keys_tap(self):
        runner = self.make_runner()
        with patch("runner.keys.tap") as mock_tap:
            runner.tap("enter", hold_ms=120)
        mock_tap.assert_called_once_with("enter", hold_ms=120, jitter_ms=runner.conf.input.jitter_ms)


# ---------------------------------------------------------------------------
# foreground_tick
# ---------------------------------------------------------------------------


class TestForegroundTick:
    def make_runner(self):
        conf = config.get_defaults()
        runner = StepRunner(conf)
        runner.name = "test"
        runner.win = MagicMock()
        runner.status = Status(running=True, state="running")
        return runner

    def test_returns_immediately_when_foreground(self):
        runner = self.make_runner()
        with (
            patch("runner.window.is_foreground", return_value=True),
            patch.object(runner, "sleep") as mock_sleep,
        ):
            runner.foreground_tick()
        mock_sleep.assert_not_called()
        assert runner.status.state == "running"

    def test_waits_until_foreground(self):
        runner = self.make_runner()
        call_count = 0

        def foreground_side_effect(win):
            nonlocal call_count
            call_count += 1
            return call_count >= 3

        with (
            patch("runner.window.is_foreground", side_effect=foreground_side_effect),
            patch.object(runner, "sleep") as mock_sleep,
        ):
            runner.foreground_tick()
        assert mock_sleep.call_count == 1
        assert runner.status.state == "running"


# ---------------------------------------------------------------------------
# sleep_remaining
# ---------------------------------------------------------------------------


class TestSleepRemaining:
    def make_runner(self):
        conf = config.get_defaults()
        runner = StepRunner(conf)
        runner.name = "test"
        return runner

    def test_waits_remaining_time(self):
        runner = self.make_runner()
        with patch.object(runner.stop_evt, "wait", return_value=False) as mock_wait:
            runner.sleep_remaining(time.monotonic() - 0.05, 0.2)
        mock_wait.assert_called_once()
        args = mock_wait.call_args[0]
        assert 0 < args[0] <= 0.2

    def test_no_wait_if_already_past(self):
        runner = self.make_runner()
        with patch.object(runner.stop_evt, "wait") as mock_wait:
            runner.sleep_remaining(time.monotonic() - 10, 0.01)
        mock_wait.assert_not_called()
