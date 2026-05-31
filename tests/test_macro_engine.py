"""Tests for macro_engine module."""

import json
from unittest.mock import patch

import numpy as np
import pytest

import config
from macro_engine import MacroRunner, load_macro
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

    def test_foreground_calls_foreground_tick(self, conf):
        runner = self.make_runner([{"type": "foreground"}])
        with patch.object(runner, "foreground_tick") as mock_fg:
            runner.exec_steps(runner.macro["steps"])
        mock_fg.assert_called_once()

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
