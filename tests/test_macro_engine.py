"""Tests for macro_engine module."""

# pyright: reportAttributeAccessIssue=false

import json
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

import config
from macro_engine import MacroRunner, load_macro, validate_steps
from runner import Stopped, StopReason


@pytest.fixture
def conf():
    return config.get_defaults()


class TestLoadMacro:
    def test_loads_json(self, tmp_path):
        data = {"meta": {"name": "test"}, "steps": [{"type": "key", "key": "a"}]}
        path = tmp_path / "m.json"
        path.write_text(json.dumps(data), encoding="utf-8")

        result = load_macro(path)
        assert result == data

    def test_invalid_json_raises(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text("not json", encoding="utf-8")

        with pytest.raises(json.JSONDecodeError):
            load_macro(path)


class TestMacroRunnerInit:
    def test_parses_meta(self, conf):
        macro = {
            "meta": {"name": "buy", "label": "Buy", "target_window": "Game"},
            "templates": {"btn": None, "icon": None},
            "steps": [],
        }
        runner = MacroRunner(conf, macro)
        assert runner.name == "buy"
        assert runner.label == "Buy"
        assert runner.target_window == "Game"
        assert set(runner.template_names) == {"btn", "icon"}

    def test_defaults_without_meta(self, conf):
        runner = MacroRunner(conf, {})
        assert runner.name == "macro"
        assert runner.label == "Macro"
        assert runner.target_window == ""
        assert runner.template_names == []


class TestFindEmptyTemplates:
    def setup_method(self):
        self.runner = MacroRunner(config.get_defaults(), {"steps": []})

    def test_no_issues(self):
        steps = [{"type": "key", "key": "a"}, {"type": "delay", "ms": 100}]
        assert self.runner.find_empty_templates(steps) == []

    def test_wait_image_missing_template(self):
        steps = [{"type": "wait_image"}, {"type": "key", "key": "a"}]
        assert self.runner.find_empty_templates(steps) == [1]

    def test_wait_image_with_template_ok(self):
        steps = [{"type": "wait_image", "template": "btn"}]
        assert self.runner.find_empty_templates(steps) == []

    def test_if_image_missing_template(self):
        steps = [{"type": "if_image", "then": [], "else": []}]
        assert self.runner.find_empty_templates(steps) == [1]

    def test_hold_key_missing_template(self):
        steps = [{"type": "hold_key_until_gone", "key": "space"}]
        assert self.runner.find_empty_templates(steps) == [1]

    def test_nested_missing(self):
        steps = [
            {
                "type": "repeat",
                "steps": [{"type": "wait_image"}],
            }
        ]
        result = self.runner.find_empty_templates(steps)
        assert 2 in result

    def test_nested_then_else(self):
        steps = [
            {
                "type": "if_image",
                "template": "ok",
                "then": [{"type": "wait_image"}],
                "else": [{"type": "hold_key_until_gone", "key": "x"}],
            }
        ]
        result = self.runner.find_empty_templates(steps)
        # then and else share the same parent offset, so both start at 2
        assert result == [2, 2]


class TestExecSteps:
    """Test exec_step for actions that don't require actual keypresses or screenshots."""

    def make_runner(self, steps):
        macro = {"meta": {"name": "t"}, "templates": {}, "steps": steps}
        runner = MacroRunner(config.get_defaults(), macro)
        runner.status.running = True
        runner.templates = {}
        return runner

    def test_key_calls_tap(self, conf):
        runner = self.make_runner([{"type": "key", "key": "enter"}])
        with patch.object(runner, "tap") as mock_tap:
            runner.exec_steps(runner.macro["steps"])
        mock_tap.assert_called_once_with("enter", hold_ms=90)

    def test_key_skip(self, conf):
        runner = self.make_runner([{"type": "key", "key": "enter", "skip": True}])
        with patch.object(runner, "tap") as mock_tap:
            runner.exec_steps(runner.macro["steps"])
        mock_tap.assert_not_called()

    def test_delay_calls_sleep(self, conf):
        runner = self.make_runner([{"type": "delay", "ms": 500}])
        with patch.object(runner, "sleep") as mock_sleep:
            runner.exec_steps(runner.macro["steps"])
        mock_sleep.assert_called_once_with(500)

    def test_repeat_iterates(self, conf):
        runner = self.make_runner([{"type": "repeat", "count": 3, "steps": [{"type": "delay", "ms": 10}]}])
        with patch.object(runner, "sleep") as mock_sleep:
            runner.exec_steps(runner.macro["steps"])
        assert mock_sleep.call_count == 3

    def test_repeat_track_progress(self, conf):
        runner = self.make_runner(
            [{"type": "repeat", "count": 2, "track_progress": True, "steps": [{"type": "delay", "ms": 1}]}]
        )
        with patch.object(runner, "sleep"):
            runner.exec_steps(runner.macro["steps"])
        assert runner.status.progress == 2

    def test_unknown_action_no_crash(self, conf):
        runner = self.make_runner([{"type": "nonsense_action"}])
        runner.exec_steps(runner.macro["steps"])
        # No crash means pass

    def test_stop_event_raises_stopped(self, conf):
        runner = self.make_runner([{"type": "delay", "ms": 1}])
        runner.stop_evt.set()
        with pytest.raises(Stopped):
            runner.exec_steps(runner.macro["steps"])

    def test_wait_image_timeout_finishes(self, conf):
        runner = self.make_runner([{"type": "wait_image", "template": "btn", "timeout_ms": 10}])
        runner.templates = {"btn": np.zeros((10, 10), dtype=np.uint8)}
        with patch.object(runner, "wait_for_template", return_value=False):
            runner.exec_steps(runner.macro["steps"])
        assert runner.status.last_reason == StopReason.STALE.value

    def test_wait_image_timeout_continue(self, conf):
        runner = self.make_runner(
            [
                {"type": "wait_image", "template": "btn", "timeout_ms": 10, "on_timeout": "continue"},
                {"type": "delay", "ms": 1},
            ]
        )
        runner.templates = {"btn": np.zeros((10, 10), dtype=np.uint8)}
        with patch.object(runner, "wait_for_template", return_value=False), patch.object(runner, "sleep") as mock_sleep:
            runner.exec_steps(runner.macro["steps"])
        mock_sleep.assert_called_once_with(1)

    def test_if_image_then_branch(self, conf):
        runner = self.make_runner(
            [
                {
                    "type": "if_image",
                    "template": "btn",
                    "timeout_ms": 10,
                    "then": [{"type": "delay", "ms": 11}],
                    "else": [{"type": "delay", "ms": 22}],
                }
            ]
        )
        runner.templates = {"btn": np.zeros((10, 10), dtype=np.uint8)}
        with patch.object(runner, "wait_for_template", return_value=True), patch.object(runner, "sleep") as mock_sleep:
            runner.exec_steps(runner.macro["steps"])
        mock_sleep.assert_called_once_with(11)

    def test_if_image_else_branch(self, conf):
        runner = self.make_runner(
            [
                {
                    "type": "if_image",
                    "template": "btn",
                    "timeout_ms": 10,
                    "then": [{"type": "delay", "ms": 11}],
                    "else": [{"type": "delay", "ms": 22}],
                }
            ]
        )
        runner.templates = {"btn": np.zeros((10, 10), dtype=np.uint8)}
        with patch.object(runner, "wait_for_template", return_value=False), patch.object(runner, "sleep") as mock_sleep:
            runner.exec_steps(runner.macro["steps"])
        mock_sleep.assert_called_once_with(22)


class TestLoop:
    """Test MacroRunner.loop() main flow."""

    def make_runner(self, steps, templates=None):
        macro = {"meta": {"name": "t"}, "templates": templates or {}, "steps": steps}
        runner = MacroRunner(config.get_defaults(), macro)
        runner.status.running = True
        runner.templates = {}
        return runner

    def test_missing_templates_finishes_stale(self):
        runner = self.make_runner([{"type": "wait_image"}])
        runner.loop()
        assert runner.status.last_reason == StopReason.STALE.value
        assert "template" in runner.status.message

    def test_normal_completion(self):
        runner = self.make_runner([{"type": "delay", "ms": 1}])
        with patch.object(runner, "sleep"):
            runner.loop()
        assert runner.status.last_reason == StopReason.DONE.value

    def test_loop_does_not_double_finish(self):
        """If exec_steps already called finish, loop should not override the reason."""
        runner = self.make_runner([{"type": "wait_image", "template": "x", "timeout_ms": 10}])
        runner.templates = {"x": np.zeros((10, 10), dtype=np.uint8)}
        with patch.object(runner, "wait_for_template", return_value=False):
            runner.loop()
        assert runner.status.last_reason == StopReason.STALE.value


class TestWaitAnyImage:
    def make_runner(self, steps):
        macro = {"meta": {"name": "t"}, "templates": {}, "steps": steps}
        runner = MacroRunner(config.get_defaults(), macro)
        runner.status.running = True
        runner.templates = {}
        return runner

    def test_wait_any_image_timeout_stop(self):
        runner = self.make_runner([{"type": "if_any_image", "templates": ["a", "b"], "timeout_ms": 10}])
        with patch.object(runner, "wait_for_any", return_value=None):
            runner.exec_steps(runner.macro["steps"])
        assert runner.status.last_reason == StopReason.STALE.value

    def test_wait_any_image_timeout_continue(self):
        runner = self.make_runner(
            [
                {"type": "if_any_image", "templates": ["a"], "timeout_ms": 10, "on_timeout": "continue"},
                {"type": "delay", "ms": 7},
            ]
        )
        with patch.object(runner, "wait_for_any", return_value=None), patch.object(runner, "sleep") as mock_sleep:
            runner.exec_steps(runner.macro["steps"])
        mock_sleep.assert_called_once_with(7)

    def test_wait_any_image_found(self):
        runner = self.make_runner(
            [
                {"type": "if_any_image", "templates": ["a", "b"], "timeout_ms": 10},
                {"type": "delay", "ms": 5},
            ]
        )
        with patch.object(runner, "wait_for_any", return_value="a"), patch.object(runner, "sleep") as mock_sleep:
            runner.exec_steps(runner.macro["steps"])
        mock_sleep.assert_called_once_with(5)


class TestIfAnyImage:
    def make_runner(self, steps):
        macro = {"meta": {"name": "t"}, "templates": {}, "steps": steps}
        runner = MacroRunner(config.get_defaults(), macro)
        runner.status.running = True
        runner.templates = {}
        return runner

    def test_if_any_image_matched_branch(self):
        step = {
            "type": "if_any_image",
            "templates": ["a", "b"],
            "timeout_ms": 10,
            "branches": {"a": [{"type": "delay", "ms": 11}], "b": [{"type": "delay", "ms": 22}]},
        }
        runner = self.make_runner([step])
        with patch.object(runner, "wait_for_any", return_value="b"), patch.object(runner, "sleep") as mock_sleep:
            runner.exec_steps(runner.macro["steps"])
        mock_sleep.assert_called_once_with(22)

    def test_if_any_image_timeout_stop(self):
        step = {
            "type": "if_any_image",
            "templates": ["a"],
            "timeout_ms": 10,
            "branches": {"a": [{"type": "delay", "ms": 1}]},
        }
        runner = self.make_runner([step])
        with patch.object(runner, "wait_for_any", return_value=None):
            runner.exec_steps(runner.macro["steps"])
        assert runner.status.last_reason == StopReason.STALE.value

    def test_if_any_image_timeout_continue(self):
        step = {
            "type": "if_any_image",
            "templates": ["a"],
            "timeout_ms": 10,
            "on_timeout": "continue",
            "branches": {"a": [{"type": "delay", "ms": 1}]},
        }
        runner = self.make_runner([step])
        with patch.object(runner, "wait_for_any", return_value=None):
            runner.exec_steps(runner.macro["steps"])
        # Should not finish; still running
        assert runner.status.running is True

    def test_if_any_image_no_matching_branch(self):
        step = {
            "type": "if_any_image",
            "templates": ["a", "b"],
            "timeout_ms": 10,
            "branches": {"a": [{"type": "delay", "ms": 1}]},
        }
        runner = self.make_runner([step])
        with patch.object(runner, "wait_for_any", return_value="b"), patch.object(runner, "sleep") as mock_sleep:
            runner.exec_steps(runner.macro["steps"])
        mock_sleep.assert_not_called()


class TestGridNav:
    def make_runner(self, steps):
        macro = {"meta": {"name": "t"}, "templates": {}, "steps": steps}
        runner = MacroRunner(config.get_defaults(), macro)
        runner.status.running = True
        runner.templates = {}
        return runner

    def test_next_row(self):
        step = {
            "type": "grid_nav",
            "rows": 3,
            "on_next_row": [{"type": "delay", "ms": 1}],
            "on_next_col": [{"type": "delay", "ms": 2}],
        }
        runner = self.make_runner([step])
        runner.grid_counters[id(runner.macro["steps"][0])] = 1
        with patch.object(runner, "sleep") as mock_sleep:
            runner.exec_steps(runner.macro["steps"])
        mock_sleep.assert_called_once_with(1)

    def test_next_col(self):
        step = {
            "type": "grid_nav",
            "rows": 3,
            "on_next_row": [{"type": "delay", "ms": 1}],
            "on_next_col": [{"type": "delay", "ms": 2}],
        }
        runner = self.make_runner([step])
        runner.grid_counters[id(runner.macro["steps"][0])] = 2
        with patch.object(runner, "sleep") as mock_sleep:
            runner.exec_steps(runner.macro["steps"])
        mock_sleep.assert_called_once_with(2)

    def test_first_position_uses_next_row(self):
        step = {
            "type": "grid_nav",
            "rows": 3,
            "on_next_row": [{"type": "delay", "ms": 1}],
            "on_next_col": [{"type": "delay", "ms": 2}],
        }
        runner = self.make_runner([step])
        with patch.object(runner, "sleep") as mock_sleep:
            runner.exec_steps(runner.macro["steps"])
        mock_sleep.assert_called_once_with(1)

    def test_counter_increments(self):
        step = {
            "type": "grid_nav",
            "rows": 3,
            "on_next_row": [{"type": "delay", "ms": 1}],
            "on_next_col": [{"type": "delay", "ms": 2}],
        }
        runner = self.make_runner([step])
        with patch.object(runner, "sleep"):
            runner.exec_steps(runner.macro["steps"])
        assert runner.grid_counters[id(runner.macro["steps"][0])] == 1

    def test_start_offset(self):
        step = {
            "type": "grid_nav",
            "rows": 3,
            "start": 2,
            "on_next_row": [{"type": "delay", "ms": 1}],
            "on_next_col": [{"type": "delay", "ms": 2}],
        }
        runner = self.make_runner([step])
        with patch.object(runner, "sleep") as mock_sleep:
            runner.exec_steps(runner.macro["steps"])
        # pos = 0 + 2 = 2, (2+1) % 3 == 0 → on_next_col
        mock_sleep.assert_called_once_with(2)


class TestWaitImageSkip:
    def test_wait_image_skip(self):
        macro = {
            "meta": {"name": "t"},
            "templates": {},
            "steps": [
                {"type": "wait_image", "template": "btn", "skip": True},
                {"type": "delay", "ms": 5},
            ],
        }
        runner = MacroRunner(config.get_defaults(), macro)
        runner.status.running = True
        runner.templates = {"btn": np.zeros((10, 10), dtype=np.uint8)}
        with patch.object(runner, "wait_for_template") as mock_wait, patch.object(runner, "sleep") as mock_sleep:
            runner.exec_steps(runner.macro["steps"])
        mock_wait.assert_not_called()
        mock_sleep.assert_called_once_with(5)


class TestValidateSteps:
    def test_missing_type(self):
        steps = [{"key": "a"}]
        errors = validate_steps(steps)
        assert len(errors) == 1
        assert "type" in errors[0]

    def test_unknown_type(self):
        steps = [{"type": "nonsense"}]
        errors = validate_steps(steps)
        assert len(errors) == 1
        assert "nonsense" in errors[0]

    def test_missing_field(self):
        steps = [{"type": "key"}]
        errors = validate_steps(steps)
        assert len(errors) == 1
        assert "key" in errors[0]

    def test_bad_format(self):
        steps = [{"type": "delay", "ms": "not_a_number"}]
        errors = validate_steps(steps)
        assert len(errors) == 1
        assert "format" in errors[0]

    def test_bad_key(self):
        steps = [{"type": "key", "key": "not_a_real_key"}]
        with patch("macro_engine.pdi") as mock_pdi:
            mock_pdi.isValidKey.return_value = False
            errors = validate_steps(steps)
        assert len(errors) == 1
        assert "key" in errors[0]

    def test_valid_steps(self):
        steps = [
            {"type": "key", "key": "enter"},
            {"type": "delay", "ms": 100},
            {"type": "repeat", "steps": [{"type": "key", "key": "a"}]},
        ]
        with patch("macro_engine.pdi") as mock_pdi:
            mock_pdi.isValidKey.return_value = True
            errors = validate_steps(steps)
        assert errors == []

    def test_recursive_validation(self):
        steps = [
            {
                "type": "repeat",
                "steps": [{"type": "bad_type"}],
            }
        ]
        errors = validate_steps(steps)
        assert len(errors) == 1
        assert "bad_type" in errors[0]

    def test_recursive_then_else(self):
        steps = [
            {
                "type": "if_image",
                "template": "btn",
                "then": [{"type": "delay"}],
                "else": [{"type": "delay"}],
            }
        ]
        errors = validate_steps(steps)
        assert len(errors) == 2

    def test_offset(self):
        steps = [{"type": "delay", "ms": 100}]
        errors = validate_steps(steps, offset=5)
        assert errors == []


class TestExecStepsNotRunning:
    def test_returns_early_when_not_running(self):
        macro = {"meta": {"name": "t"}, "templates": {}, "steps": [{"type": "delay", "ms": 1}]}
        runner = MacroRunner(config.get_defaults(), macro)
        runner.status.running = False
        with patch.object(runner, "sleep") as mock_sleep:
            runner.exec_steps(runner.macro["steps"])
        mock_sleep.assert_not_called()


class TestRepeatNotRunning:
    def test_repeat_stops_when_not_running(self):
        macro = {
            "meta": {"name": "t"},
            "templates": {},
            "steps": [{"type": "repeat", "count": 5, "steps": [{"type": "delay", "ms": 1}]}],
        }
        runner = MacroRunner(config.get_defaults(), macro)
        runner.status.running = True
        call_count = 0

        def stop_after_two(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                runner.status.running = False

        with patch.object(runner, "sleep", side_effect=stop_after_two):
            runner.exec_steps(runner.macro["steps"])
        assert call_count == 2


class TestLoopMissingTemplates:
    def test_loop_finishes_with_missing_template_message(self):
        macro = {"meta": {"name": "t"}, "templates": {}, "steps": [{"type": "wait_image"}]}
        runner = MacroRunner(config.get_defaults(), macro)
        runner.status.running = True
        runner.templates = {}
        runner.loop()
        assert runner.status.last_reason == StopReason.STALE.value
        assert "template" in runner.status.message


class TestHoldKeyUntilGone:
    def make_runner(self, step):
        macro = {"meta": {"name": "t"}, "templates": {}, "steps": [step]}
        runner = MacroRunner(config.get_defaults(), macro)
        runner.status.running = True
        runner.templates = {"btn": np.zeros((10, 10), dtype=np.uint8)}
        runner.template_capture_sizes = {}
        runner.win = MagicMock()
        runner.grabber = MagicMock()
        runner.rect = (0, 0, 100, 100)
        return runner

    def test_holds_key_and_releases_when_gone(self):
        step = {
            "type": "hold_key_until_gone",
            "key": "w",
            "template": "btn",
            "load_delay_ms": 0,
            "find_timeout_ms": 1000,
            "gone_grace_ms": 50,
            "hard_timeout_ms": 5000,
        }
        runner = self.make_runner(step)
        frame = np.zeros((100, 100), dtype=np.uint8)
        runner.grabber.grab.return_value = frame

        t = 0.0

        def tick():
            nonlocal t
            t += 0.02
            return t

        with (
            patch("macro_engine.vision") as mock_vision,
            patch("macro_engine.window") as mock_window,
            patch("macro_engine.keys") as mock_keys,
            patch("macro_engine.time") as mock_time,
            patch.object(runner, "sleep"),
        ):
            mock_vision.to_gray.return_value = frame
            mock_vision.match_one.side_effect = [(0.9, (5, 5)), (0.1, (5, 5)), (0.1, (5, 5))]
            mock_window.is_foreground.return_value = True
            mock_time.monotonic.side_effect = tick

            runner.do_hold_key_until_gone(step)

        mock_keys.held.assert_called_once_with("w")

    def test_releases_on_hard_timeout(self):
        step = {
            "type": "hold_key_until_gone",
            "key": "w",
            "template": "btn",
            "load_delay_ms": 0,
            "find_timeout_ms": 10000,
            "gone_grace_ms": 1500,
            "hard_timeout_ms": 100,
        }
        runner = self.make_runner(step)
        frame = np.zeros((100, 100), dtype=np.uint8)
        runner.grabber.grab.return_value = frame

        t = 0.0

        def tick():
            nonlocal t
            t += 0.05
            return t

        with (
            patch("macro_engine.vision") as mock_vision,
            patch("macro_engine.window") as mock_window,
            patch("macro_engine.keys") as mock_keys,
            patch("macro_engine.time") as mock_time,
            patch.object(runner, "sleep"),
        ):
            mock_vision.to_gray.return_value = frame
            mock_vision.match_one.return_value = (0.9, (5, 5))
            mock_window.is_foreground.return_value = True
            mock_time.monotonic.side_effect = tick

            runner.do_hold_key_until_gone(step)

        mock_keys.held.assert_called_once()

    def test_releases_when_window_lost_foreground(self):
        step = {
            "type": "hold_key_until_gone",
            "key": "w",
            "template": "btn",
            "load_delay_ms": 0,
            "find_timeout_ms": 1000,
            "gone_grace_ms": 50,
            "hard_timeout_ms": 5000,
        }
        runner = self.make_runner(step)
        frame = np.zeros((100, 100), dtype=np.uint8)
        runner.grabber.grab.return_value = frame

        with (
            patch("macro_engine.vision") as mock_vision,
            patch("macro_engine.window") as mock_window,
            patch("macro_engine.keys") as mock_keys,
            patch("macro_engine.time") as mock_time,
            patch.object(runner, "sleep"),
        ):
            mock_vision.to_gray.return_value = frame
            mock_vision.match_one.return_value = (0.9, (5, 5))
            mock_window.is_foreground.return_value = False
            mock_time.monotonic.side_effect = lambda: 0.01

            runner.do_hold_key_until_gone(step)

        mock_keys.held.assert_called_once()

    def test_releases_on_find_timeout(self):
        step = {
            "type": "hold_key_until_gone",
            "key": "w",
            "template": "btn",
            "load_delay_ms": 0,
            "find_timeout_ms": 50,
            "gone_grace_ms": 1500,
            "hard_timeout_ms": 60000,
        }
        runner = self.make_runner(step)
        frame = np.zeros((100, 100), dtype=np.uint8)
        runner.grabber.grab.return_value = frame

        t = 0.0

        def tick():
            nonlocal t
            t += 0.03
            return t

        with (
            patch("macro_engine.vision") as mock_vision,
            patch("macro_engine.window") as mock_window,
            patch("macro_engine.keys") as mock_keys,
            patch("macro_engine.time") as mock_time,
            patch.object(runner, "sleep"),
        ):
            mock_vision.to_gray.return_value = frame
            mock_vision.match_one.return_value = (0.1, (5, 5))
            mock_window.is_foreground.return_value = True
            mock_time.monotonic.side_effect = tick

            runner.do_hold_key_until_gone(step)

        mock_keys.held.assert_called_once()

    def test_skips_none_frame(self):
        step = {
            "type": "hold_key_until_gone",
            "key": "w",
            "template": "btn",
            "load_delay_ms": 0,
            "find_timeout_ms": 1000,
            "gone_grace_ms": 50,
            "hard_timeout_ms": 5000,
        }
        runner = self.make_runner(step)
        frame = np.zeros((100, 100), dtype=np.uint8)

        call_count = 0

        def grab_side_effect(rect):
            nonlocal call_count
            call_count += 1
            if call_count <= 1:
                return None
            return frame

        runner.grabber.grab = MagicMock(side_effect=grab_side_effect)

        t = 0.0

        def tick():
            nonlocal t
            t += 0.02
            return t

        with (
            patch("macro_engine.vision") as mock_vision,
            patch("macro_engine.window") as mock_window,
            patch("macro_engine.keys") as mock_keys,
            patch("macro_engine.time") as mock_time,
            patch.object(runner, "sleep"),
        ):
            mock_vision.to_gray.return_value = frame
            mock_vision.match_one.side_effect = lambda *a: (0.1, (5, 5))
            mock_window.is_foreground.return_value = True
            mock_time.monotonic.side_effect = tick

            runner.do_hold_key_until_gone(step)

        mock_keys.held.assert_called_once()

    def test_uses_scaled_template_with_capture_size(self):
        step = {
            "type": "hold_key_until_gone",
            "key": "w",
            "template": "btn",
            "load_delay_ms": 0,
            "find_timeout_ms": 1000,
            "gone_grace_ms": 50,
            "hard_timeout_ms": 5000,
        }
        runner = self.make_runner(step)
        runner.template_capture_sizes = {"btn": (1920, 1080)}
        frame = np.zeros((100, 100), dtype=np.uint8)
        runner.grabber.grab.return_value = frame

        t = 0.0

        def tick():
            nonlocal t
            t += 0.02
            return t

        with (
            patch("macro_engine.vision") as mock_vision,
            patch("macro_engine.window") as mock_window,
            patch("macro_engine.keys"),
            patch("macro_engine.time") as mock_time,
            patch.object(runner, "sleep"),
        ):
            mock_vision.to_gray.return_value = frame
            mock_vision.match_one.side_effect = lambda *a: (0.1, (5, 5))
            mock_window.is_foreground.return_value = True
            mock_time.monotonic.side_effect = tick

            runner.do_hold_key_until_gone(step)

        mock_vision.scale_template.assert_called_once()

    def test_dispatch_through_exec_step(self):
        step = {
            "type": "hold_key_until_gone",
            "key": "w",
            "template": "btn",
            "load_delay_ms": 0,
            "find_timeout_ms": 1000,
            "gone_grace_ms": 50,
            "hard_timeout_ms": 5000,
        }
        runner = self.make_runner(step)
        frame = np.zeros((100, 100), dtype=np.uint8)
        runner.grabber.grab.return_value = frame

        t = 0.0

        def tick():
            nonlocal t
            t += 0.02
            return t

        with (
            patch("macro_engine.vision") as mock_vision,
            patch("macro_engine.window") as mock_window,
            patch("macro_engine.keys"),
            patch("macro_engine.time") as mock_time,
            patch.object(runner, "sleep"),
        ):
            mock_vision.to_gray.return_value = frame
            mock_vision.match_one.side_effect = lambda *a: (0.1, (5, 5))
            mock_window.is_foreground.return_value = False
            mock_time.monotonic.side_effect = tick

            runner.exec_steps(runner.macro["steps"])

    def test_stops_on_stop_event(self):
        step = {
            "type": "hold_key_until_gone",
            "key": "w",
            "template": "btn",
            "load_delay_ms": 0,
            "find_timeout_ms": 1000,
            "gone_grace_ms": 50,
            "hard_timeout_ms": 5000,
        }
        runner = self.make_runner(step)
        frame = np.zeros((100, 100), dtype=np.uint8)
        runner.grabber.grab.return_value = frame

        with (
            patch("macro_engine.vision") as mock_vision,
            patch("macro_engine.window") as mock_window,
            patch("macro_engine.keys"),
            patch("macro_engine.time") as mock_time,
            patch.object(runner, "sleep"),
        ):
            mock_vision.to_gray.return_value = frame
            mock_vision.match_one.return_value = (0.9, (5, 5))
            mock_window.is_foreground.return_value = True
            mock_time.monotonic.side_effect = lambda: 0.01
            runner.stop_evt.set()

            with pytest.raises(Stopped):
                runner.do_hold_key_until_gone(step)


# ---------------------------------------------------------------------------
# Repeat depth tracking
# ---------------------------------------------------------------------------


class TestRepeatDepthTracking:
    def make_runner(self, steps):
        macro = {"meta": {"name": "t"}, "templates": {}, "steps": steps}
        runner = MacroRunner(config.get_defaults(), macro)
        runner.status.running = True
        runner.templates = {}
        return runner

    def test_nested_repeat_increments_depth(self):
        steps = [
            {
                "type": "repeat",
                "count": 1,
                "steps": [
                    {"type": "delay", "ms": 1},
                    {
                        "type": "repeat",
                        "count": 1,
                        "steps": [{"type": "delay", "ms": 1}],
                    },
                ],
            }
        ]
        runner = self.make_runner(steps)
        depths = []

        def record_depth(*args, **kwargs):
            depths.append(runner.repeat_depth)

        with patch.object(runner, "sleep", side_effect=record_depth):
            runner.exec_steps(runner.macro["steps"])
        assert depths == [1, 2]
        assert runner.repeat_depth == 0

    def test_repeat_depth_resets_after_loop(self):
        steps = [
            {"type": "repeat", "count": 2, "steps": [{"type": "delay", "ms": 1}]},
            {"type": "delay", "ms": 1},
        ]
        runner = self.make_runner(steps)
        depths = []

        def record_depth(*args, **kwargs):
            depths.append(runner.repeat_depth)

        with patch.object(runner, "sleep", side_effect=record_depth):
            runner.exec_steps(runner.macro["steps"])
        assert depths == [1, 1, 0]

    def test_repeat_depth_zero_for_sibling(self):
        steps = [
            {"type": "repeat", "count": 1, "steps": [{"type": "delay", "ms": 1}]},
            {"type": "repeat", "count": 1, "steps": [{"type": "delay", "ms": 1}]},
        ]
        runner = self.make_runner(steps)
        depths = []

        def record_depth(*args, **kwargs):
            depths.append(runner.repeat_depth)

        with patch.object(runner, "sleep", side_effect=record_depth):
            runner.exec_steps(runner.macro["steps"])
        assert depths == [1, 1]


# ---------------------------------------------------------------------------
# Grid nav multiple rounds
# ---------------------------------------------------------------------------


class TestGridNavMultipleRounds:
    def make_runner(self, steps):
        macro = {"meta": {"name": "t"}, "templates": {}, "steps": steps}
        runner = MacroRunner(config.get_defaults(), macro)
        runner.status.running = True
        runner.templates = {}
        return runner

    def test_wraparound_second_round(self):
        step = {
            "type": "grid_nav",
            "rows": 2,
            "on_next_row": [{"type": "delay", "ms": 1}],
            "on_next_col": [{"type": "delay", "ms": 2}],
        }
        runner = self.make_runner([step])
        # Counter starts at 0. First call: pos=0, (0+1)%2=1 -> on_next_row
        # Second call: counter=1, pos=1, (1+1)%2=0 -> on_next_col
        with patch.object(runner, "sleep") as mock_sleep:
            runner.exec_steps(runner.macro["steps"])
            runner.exec_steps(runner.macro["steps"])
        assert mock_sleep.call_count == 2
        calls = [c.args[0] for c in mock_sleep.call_args_list]
        assert calls == [1, 2]

    def test_start_offset_with_multiple_calls(self):
        step = {
            "type": "grid_nav",
            "rows": 3,
            "start": 1,
            "on_next_row": [{"type": "delay", "ms": 1}],
            "on_next_col": [{"type": "delay", "ms": 2}],
        }
        runner = self.make_runner([step])
        # Call 1: pos = 0 + 1 = 1, (1+1)%3=2 -> on_next_row
        # Call 2: counter=1, pos=1+1=2, (2+1)%3=0 -> on_next_col
        # Call 3: counter=2, pos=2+1=3, (3+1)%3=1 -> on_next_row
        with patch.object(runner, "sleep") as mock_sleep:
            for _ in range(3):
                runner.exec_steps(runner.macro["steps"])
        calls = [c.args[0] for c in mock_sleep.call_args_list]
        assert calls == [1, 2, 1]


# ---------------------------------------------------------------------------
# Skip + current_step
# ---------------------------------------------------------------------------


class TestSkipCurrentStep:
    def make_runner(self, steps):
        macro = {"meta": {"name": "t"}, "templates": {}, "steps": steps}
        runner = MacroRunner(config.get_defaults(), macro)
        runner.status.running = True
        runner.templates = {}
        return runner

    def test_skip_does_not_set_current_step(self):
        steps = [
            {"type": "key", "key": "a", "skip": True},
            {"type": "delay", "ms": 1},
        ]
        runner = self.make_runner(steps)
        runner.current_step = None
        with patch.object(runner, "sleep"):
            runner.exec_steps(runner.macro["steps"])
        assert runner.current_step is not None
        assert runner.current_step["type"] == "delay"

    def test_non_skip_sets_current_step(self):
        steps = [
            {"type": "key", "key": "a"},
            {"type": "delay", "ms": 1},
        ]
        runner = self.make_runner(steps)
        with patch.object(runner, "tap"), patch.object(runner, "sleep"):
            runner.exec_steps(runner.macro["steps"])
        assert runner.current_step is not None
        assert runner.current_step["type"] == "delay"

    def test_container_does_not_set_current_step(self):
        steps = [
            {"type": "repeat", "count": 1, "steps": [{"type": "delay", "ms": 1}]},
            {"type": "delay", "ms": 1},
        ]
        runner = self.make_runner(steps)
        with patch.object(runner, "sleep"):
            runner.exec_steps(runner.macro["steps"])
        assert runner.current_step is not None
        assert runner.current_step["type"] == "delay"


# ---------------------------------------------------------------------------
# Hold key until gone — gone grace edge case
# ---------------------------------------------------------------------------


class TestHoldKeyUntilGoneGoneGrace:
    def make_runner(self, step):
        macro = {"meta": {"name": "t"}, "templates": {}, "steps": [step]}
        runner = MacroRunner(config.get_defaults(), macro)
        runner.status.running = True
        runner.templates = {"btn": np.zeros((10, 10), dtype=np.uint8)}
        runner.template_capture_sizes = {}
        runner.win = MagicMock()
        runner.grabber = MagicMock()
        runner.rect = (0, 0, 100, 100)
        return runner

    def test_gone_grace_requires_continuous_absence(self):
        """Template disappears briefly then reappears; should not release."""
        step = {
            "type": "hold_key_until_gone",
            "key": "w",
            "template": "btn",
            "load_delay_ms": 0,
            "find_timeout_ms": 1000,
            "gone_grace_ms": 200,
            "hard_timeout_ms": 5000,
        }
        runner = self.make_runner(step)
        frame = np.zeros((100, 100), dtype=np.uint8)
        runner.grabber.grab.return_value = frame

        t = 0.0

        def tick():
            nonlocal t
            t += 0.12
            return t

        with (
            patch("macro_engine.vision") as mock_vision,
            patch("macro_engine.window") as mock_window,
            patch("macro_engine.keys") as mock_keys,
            patch("macro_engine.time") as mock_time,
            patch.object(runner, "sleep"),
        ):
            mock_vision.to_gray.return_value = frame
            # Appears -> gone (too short) -> appears -> gone (long enough)
            mock_vision.match_one.side_effect = [
                (0.95, (5, 5)),
                (0.1, (5, 5)),
                (0.95, (5, 5)),
                (0.1, (5, 5)),
                (0.1, (5, 5)),
            ]
            mock_window.is_foreground.return_value = True
            mock_time.monotonic.side_effect = tick

            runner.do_hold_key_until_gone(step)

        mock_keys.held.assert_called_once_with("w")
