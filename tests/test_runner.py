import threading
import time
from unittest.mock import MagicMock, patch

import pytest

import config
from runner import Status, StepRunner, Stopped, StopReason


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
