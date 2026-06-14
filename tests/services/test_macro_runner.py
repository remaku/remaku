from pathlib import Path
from typing import cast

import numpy as np
import pytest

from remaku.core.capture import Grabber
from remaku.core.window import Rect
from remaku.models.macro_model import Macro
from remaku.services import engine
from remaku.services.engine import Stopped, StopReason
from remaku.services.macro_runner import MacroRunner, validate_steps


class FakeHeldContext:
    def __init__(self, key: str = "") -> None:
        self.key = key

    def __enter__(self) -> "FakeHeldContext":
        return self

    def __exit__(self, *args) -> None:
        pass


class FakeGrabber(Grabber):
    def __init__(self) -> None:
        pass

    def grab(self, rect: Rect) -> np.ndarray:
        return np.ones((10, 10, 3), dtype=np.uint8)


def make_hold_key_runner() -> MacroRunner:
    runner = make_runner([], templates={"start": {"label": "Start"}})
    runner.templates = {"start": np.zeros((10, 10), dtype=np.uint8)}
    runner.found_window = object()
    runner.capture_rect = Rect(0, 0, 10, 10)
    runner.grabber = FakeGrabber()
    runner.template_capture_sizes = {}

    return runner


def make_runner(steps: list[dict], templates: dict | None = None) -> MacroRunner:
    macro = Macro.from_dict(
        {
            "meta": {"name": "runner", "label": "Runner"},
            "templates": templates or {},
            "steps": steps,
        }
    )
    runner = MacroRunner(macro)
    runner.status.running = True
    return runner


def test_validate_steps_reports_missing_and_unknown_types() -> None:
    errors = validate_steps([{}, {"type": "unknown"}])

    assert errors == ["Step 1: missing type", "Step 2: unknown type 'unknown'"]


def test_validate_steps_checks_key_and_template_fields(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("remaku.services.macro_runner.keys.is_valid_key", lambda key: key == "enter")

    errors = validate_steps(
        [
            {"type": "key", "key": "bad"},
            {"type": "wait_image", "template": "missing"},
            {"type": "if_any_image", "templates": []},
        ],
        template_root=tmp_path,
    )

    assert errors == [
        "Step 1 (key): invalid key 'bad'",
        "Step 2 (wait_image): template 'missing' not found on disk",
        "Step 3 (if_any_image): empty templates",
    ]


def test_validate_steps_accepts_modifier_key_combo(monkeypatch) -> None:
    monkeypatch.setattr("remaku.services.macro_runner.keys.is_valid_key", lambda key: key == "ctrl+shift+s")

    assert validate_steps([{"type": "key", "key": "ctrl+shift+s"}]) == []


def test_validate_steps_accepts_existing_templates(tmp_path: Path) -> None:
    (tmp_path / "start.png").write_bytes(b"png")

    assert validate_steps([{"type": "wait_image", "template": "start"}], template_root=tmp_path) == []


def test_pause_resume_are_idempotent() -> None:
    runner = make_runner([])

    runner.pause()
    runner.pause()

    assert runner.is_paused()
    assert not runner.resume_event.is_set()

    runner.resume()
    runner.resume()

    assert not runner.is_paused()
    assert runner.resume_event.is_set()


def test_stop_clears_paused_state(qtbot) -> None:
    runner = make_runner([])
    runner.pause()

    with qtbot.waitSignal(engine.event_bus.macro_paused_changed, timeout=100) as blocker:
        runner.stop()

    assert runner.stop_event.is_set()
    assert not runner.is_paused()
    assert runner.resume_event.is_set()
    assert blocker.args == [False]


def test_stop_does_not_run_resume_callback_after_paused() -> None:
    runner = make_runner([])
    calls = []
    runner.pause()

    runner.stop()

    with pytest.raises(Stopped):
        runner.checkpoint(resume_callback=lambda: calls.append("resume"))

    assert calls == []


def test_elapsed_time_freezes_while_paused(monkeypatch) -> None:
    times = iter([105.0, 106.0, 108.0, 113.0])
    runner = make_runner([])
    runner.start_time = 100.0
    monkeypatch.setattr(engine.time, "monotonic", lambda: next(times))

    runner.pause()
    paused_status = runner.get_status()
    runner.resume()
    resumed_status = runner.get_status()

    assert paused_status.elapsed_s == 5.0
    assert resumed_status.elapsed_s == 10.0


def test_validate_steps_accepts_text_input_and_checks_interval() -> None:
    errors = validate_steps(
        [
            {"type": "text_input", "text": "哈囉", "interval_ms": 25},
            {"type": "text_input"},
            {"type": "text_input", "text": "hello", "interval_ms": "bad"},
        ]
    )

    assert errors == [
        "Step 2 (text_input): missing field 'text'",
        "Step 3 (text_input): bad format for 'interval_ms'",
    ]


def test_exec_step_skips_marked_step() -> None:
    runner = make_runner([])
    calls = []
    runner.tap = lambda key, hold_ms=90: calls.append(key)

    runner.exec_step({"type": "key", "key": "enter", "skip": True}, (("steps", 0),))

    assert calls == []


def test_exec_step_taps_key_with_hold_duration() -> None:
    runner = make_runner([])
    calls = []
    runner.tap = lambda key, hold_ms=90: calls.append((key, hold_ms))

    runner.exec_step({"type": "key", "key": "enter", "hold_ms": 120}, (("steps", 0),))

    assert calls == [("enter", 120)]


def test_exec_step_taps_modifier_key_combo() -> None:
    runner = make_runner([])
    calls = []
    runner.tap = lambda key, hold_ms=90: calls.append((key, hold_ms))

    runner.exec_step({"type": "key", "key": "ctrl+s", "hold_ms": 120}, (("steps", 0),))

    assert calls == [("ctrl+s", 120)]


def test_exec_step_runs_delay() -> None:
    runner = make_runner([])
    sleeps = []
    runner.sleep = lambda ms, pause_callback=None, resume_callback=None: sleeps.append(ms)

    runner.exec_step({"type": "delay", "ms": 250}, (("steps", 0),))

    assert sleeps == [250]


def test_exec_step_types_text_with_interval(monkeypatch) -> None:
    runner = make_runner([])
    calls = []
    monkeypatch.setattr(
        "remaku.services.macro_runner.keys.type_text",
        lambda text, interval_ms: calls.append((text, interval_ms)),
    )

    runner.exec_step({"type": "text_input", "text": "哈囉", "interval_ms": 25}, (("steps", 0),))

    assert calls == [("哈囉", 25)]


def test_repeat_step_updates_progress_and_runs_children() -> None:
    runner = make_runner([])
    calls = []
    updates = []
    runner.exec_steps = lambda steps, parent_path=(), branch_key="steps": calls.append((steps, parent_path, branch_key))
    runner.update = lambda **fields: updates.append(fields)

    step = {"type": "repeat", "count": 2, "steps": [{"type": "key", "key": "enter"}]}
    runner.exec_step(step, (("steps", 0),))

    assert updates == [{"progress": 1, "repeat_total": 2}, {"progress": 2, "repeat_total": 2}]
    assert calls == [
        (step["steps"], (("steps", 0),), "steps"),
        (step["steps"], (("steps", 0),), "steps"),
    ]


def test_nested_repeat_does_not_update_top_level_progress() -> None:
    runner = make_runner([])
    updates = []
    runner.repeat_depth = 1
    runner.exec_steps = lambda steps, parent_path=(), branch_key="steps": None
    runner.update = lambda **fields: updates.append(fields)

    runner.exec_step({"type": "repeat", "count": 2, "steps": []}, (("steps", 0),))

    assert updates == []
    assert runner.repeat_depth == 1


def test_if_image_executes_then_or_else_branch() -> None:
    runner = make_runner([], templates={"start": {"label": "Start"}})
    calls = []

    def wait_for_template(template_id: str, timeout_ms: int, threshold: float) -> bool:
        return template_id == "start"

    runner.wait_for_template = wait_for_template
    runner.exec_steps = lambda steps, parent_path=(), branch_key="steps": calls.append((steps, branch_key))

    step = {
        "type": "if_image",
        "template": "start",
        "then": [{"type": "key", "key": "enter"}],
        "else": [{"type": "key", "key": "esc"}],
    }
    runner.exec_step(step, (("steps", 0),))

    assert calls == [(step["then"], "then")]


def test_if_any_image_timeout_finishes_when_configured_to_stop() -> None:
    runner = make_runner([], templates={"one": {"label": "One"}, "two": {"label": "Two"}})
    finishes = []

    def wait_for_any(template_ids: list[str], timeout_ms: int, threshold: float) -> str | None:
        return None

    runner.wait_for_any = wait_for_any
    runner.finish = lambda reason, message: finishes.append((reason, message))

    runner.exec_step(
        {"type": "if_any_image", "templates": ["one", "two"], "on_timeout": "stop"},
        (("steps", 0),),
    )

    assert finishes == [(StopReason.STALE, "wait_any_timeout: ['One', 'Two']")]


def test_wait_image_timeout_continue_does_not_finish() -> None:
    runner = make_runner([], templates={"start": {"label": "Start"}})
    finishes = []
    runner.wait_for_template = lambda template_id, timeout_ms, threshold: False
    runner.finish = lambda reason, message: finishes.append((reason, message))

    runner.exec_step({"type": "wait_image", "template": "start", "on_timeout": "continue"}, (("steps", 0),))

    assert finishes == []


def test_if_any_image_executes_matching_branch() -> None:
    runner = make_runner([], templates={"one": {"label": "One"}, "two": {"label": "Two"}})
    calls = []
    runner.wait_for_any = lambda template_ids, timeout_ms, threshold: "two"
    runner.exec_steps = lambda steps, parent_path=(), branch_key="steps": calls.append((steps, branch_key))
    step = {
        "type": "if_any_image",
        "templates": ["one", "two"],
        "branches": {"two": [{"type": "key", "key": "enter"}]},
    }

    runner.exec_step(step, (("steps", 0),))

    assert calls == [(step["branches"]["two"], "two")]


def test_if_any_image_no_matching_branch_is_noop() -> None:
    runner = make_runner([], templates={"one": {"label": "One"}})
    calls = []
    finishes = []
    runner.wait_for_any = lambda template_ids, timeout_ms, threshold: "one"
    runner.exec_steps = lambda steps, parent_path=(), branch_key="steps": calls.append((steps, branch_key))
    runner.finish = lambda reason, message: finishes.append((reason, message))

    runner.exec_step({"type": "if_any_image", "templates": ["one"], "branches": {}}, (("steps", 0),))

    assert calls == []
    assert finishes == []


def test_exec_steps_returns_when_runner_not_running() -> None:
    runner = make_runner([])
    runner.status.running = False
    calls = []
    runner.exec_step = lambda step, step_path: calls.append((step, step_path))

    runner.exec_steps([{"type": "key", "key": "enter"}])

    assert calls == []


def test_exec_steps_does_not_set_current_step_for_repeat_container() -> None:
    runner = make_runner([])
    runner.current_step = None
    runner.exec_step = lambda step, step_path: None

    runner.exec_steps([{"type": "repeat", "steps": [{"type": "key", "key": "enter"}]}])

    assert runner.current_step is None


def test_build_template_capture_sizes_uses_template_metadata(monkeypatch) -> None:
    runner = make_runner(
        [],
        templates={
            "start": {"capture_width": 320, "capture_height": 180},
            "full": {},
        },
    )
    runner.templates = {"start": np.zeros((10, 10)), "full": np.zeros((10, 10))}
    monkeypatch.setattr("remaku.services.macro_runner.window.screen_resolution", lambda: (1920, 1080))

    sizes = runner.build_template_capture_sizes()

    assert sizes == {"start": (320, 180), "full": (1920, 1080)}


def test_build_template_capture_sizes_returns_empty_for_non_gaming_mode() -> None:
    macro = Macro.from_dict(
        {
            "meta": {"name": "runner", "label": "Runner"},
            "gaming_mode": False,
            "templates": {"start": {"capture_width": 320, "capture_height": 180}},
            "steps": [],
        }
    )
    runner = MacroRunner(macro)
    runner.templates = {"start": np.zeros((10, 10))}

    assert runner.build_template_capture_sizes() == {}


def test_template_match_mode_uses_template_metadata() -> None:
    runner = make_runner([], templates={"start": {"match_mode": "color"}})

    assert runner.template_match_mode("start") == "color"
    assert runner.template_match_mode("missing") == "grayscale"


def test_grid_nav_chooses_row_then_col_branches() -> None:
    runner = make_runner([])
    calls = []
    runner.exec_steps = lambda steps, parent_path=(), branch_key="steps": calls.append(branch_key)
    step = {
        "type": "grid_nav",
        "rows": 2,
        "start": 0,
        "on_next_row": [{"type": "key", "key": "down"}],
        "on_next_col": [{"type": "key", "key": "right"}],
    }

    runner.exec_step(step, (("steps", 0),))
    runner.exec_step(step, (("steps", 0),))

    assert calls == ["on_next_row", "on_next_col"]


def test_loop_finishes_stale_when_validation_fails(monkeypatch) -> None:
    runner = make_runner([{"type": "wait_image", "template": "missing"}])
    finishes = []
    monkeypatch.setattr("remaku.paths.templates_dir", lambda macro_id: Path("missing-root"))
    runner.finish = lambda reason, message: finishes.append((reason, message))

    runner.loop()

    assert finishes == [(StopReason.STALE, "macro_format: Step 1 (wait_image): template 'missing' not found on disk")]


def test_loop_executes_steps_and_finishes_done(monkeypatch, tmp_path: Path) -> None:
    steps_input = [{"type": "key", "key": "enter"}]
    runner = make_runner(steps_input)
    calls = []
    finishes = []
    monkeypatch.setattr("remaku.paths.templates_dir", lambda macro_id: tmp_path)
    runner.exec_steps = lambda steps, parent_path=(), branch_key="steps": calls.append(("steps", steps))
    runner.finish = lambda reason, message: finishes.append((reason, message))

    runner.loop()

    assert runner.current_step is None
    assert runner.current_step_path is None
    assert calls == [("steps", runner.macro["steps"])]
    assert finishes == [(StopReason.DONE, "done")]


def test_loop_finishes_stale_when_target_window_missing(monkeypatch) -> None:
    finishes = []

    runner = make_runner([])
    runner.target_window = "Game"
    runner.finish = lambda reason, message: finishes.append((reason, message))
    runner.run = lambda: runner.finish(StopReason.STALE, "window_not_found: Game")

    runner.run()

    assert finishes == [(StopReason.STALE, "window_not_found: Game")]


def test_hold_key_until_gone_releases_when_template_never_found(qtbot, monkeypatch) -> None:
    runner = make_hold_key_runner()
    sleep_calls = []
    updates = []
    monkeypatch.setattr("remaku.services.macro_runner.window.is_foreground", lambda window: True)
    monkeypatch.setattr("remaku.services.macro_runner.keys.held", FakeHeldContext)
    monkeypatch.setattr(
        "remaku.services.macro_runner.vision.match_template",
        lambda frame, template, match_mode="grayscale": (0.3, (0, 0)),
    )
    runner.sleep = lambda ms, pause_callback=None, resume_callback=None: sleep_calls.append(ms)
    runner.update = lambda **fields: updates.append(fields)

    runner.do_hold_key_until_gone(
        {
            "type": "hold_key_until_gone",
            "key": "enter",
            "template": "start",
            "load_delay_ms": 0,
            "find_timeout_ms": 0,
            "threshold": 0.8,
        }
    )

    assert sleep_calls == [0]
    assert updates == [{"score": 0.3, "match_id": "start"}]


def test_hold_key_until_gone_stops_when_runner_stops(monkeypatch) -> None:
    runner = make_hold_key_runner()
    monkeypatch.setattr("remaku.services.macro_runner.window.is_foreground", lambda window: True)
    monkeypatch.setattr(
        "remaku.services.macro_runner.vision.match_template",
        lambda frame, template, match_mode="grayscale": (1.0, (0, 0)),
    )
    monkeypatch.setattr("remaku.services.macro_runner.keys.held", FakeHeldContext)
    sleep_calls = []

    def stop_after_tick(
        tick_start: float,
        period: float,
        pause_callback=None,
        resume_callback=None,
    ) -> None:
        sleep_calls.append(period)
        runner.status.running = False

    runner.sleep = lambda ms, pause_callback=None, resume_callback=None: None
    runner.sleep_remaining = stop_after_tick

    runner.do_hold_key_until_gone(
        {"type": "hold_key_until_gone", "key": "enter", "template": "start", "load_delay_ms": 0, "threshold": 0.8}
    )

    assert sleep_calls == [0.1]


def test_hold_key_until_gone_releases_after_grace_period(monkeypatch) -> None:
    runner = make_hold_key_runner()
    sleep_calls = []
    match_returns = iter([(1.0, (0, 0)), (0.3, (0, 0)), (0.3, (0, 0))])

    def fake_match(frame, template, match_mode="grayscale"):
        return next(match_returns)

    monkeypatch.setattr("remaku.services.macro_runner.vision.match_template", fake_match)
    monkeypatch.setattr("remaku.services.macro_runner.keys.held", FakeHeldContext)
    runner.sleep = lambda ms, pause_callback=None, resume_callback=None: sleep_calls.append(ms)

    runner.do_hold_key_until_gone(
        {
            "type": "hold_key_until_gone",
            "key": "space",
            "template": "start",
            "load_delay_ms": 0,
            "gone_grace_ms": 0,
            "threshold": 0.8,
        }
    )

    assert len(sleep_calls) >= 1


def test_hold_key_until_gone_returns_when_window_loses_foreground(monkeypatch) -> None:
    runner = make_hold_key_runner()
    foreground_calls = []

    def fake_is_foreground(window: object) -> bool:
        foreground_calls.append(window)

        return len(foreground_calls) == 1

    monkeypatch.setattr("remaku.services.macro_runner.window.is_foreground", fake_is_foreground)
    monkeypatch.setattr("remaku.services.macro_runner.keys.held", FakeHeldContext)
    monkeypatch.setattr(
        "remaku.services.macro_runner.vision.match_template",
        lambda frame, template, match_mode="grayscale": (1.0, (0, 0)),
    )
    runner.sleep = lambda ms, pause_callback=None, resume_callback=None: None
    runner.sleep_remaining = lambda tick_start, period, pause_callback=None, resume_callback=None: None

    runner.do_hold_key_until_gone(
        {"type": "hold_key_until_gone", "key": "enter", "template": "start", "load_delay_ms": 0, "threshold": 0.8}
    )

    assert len(foreground_calls) == 2


def test_validate_steps_reports_bad_format_empty_template_and_nested_errors(monkeypatch) -> None:
    monkeypatch.setattr("remaku.services.macro_runner.keys.is_valid_key", lambda key: True)

    errors = validate_steps(
        [
            {"type": "key"},
            {"type": "delay", "ms": "bad"},
            {"type": "wait_image", "template": ""},
            {"type": "if_image", "template": "start", "then": [{"type": "key", "key": 1}]},
        ]
    )

    assert errors == [
        "Step 1 (key): missing field 'key'",
        "Step 2 (delay): bad format for 'ms'",
        "Step 3 (wait_image): empty template",
        "Step 5 (key): bad format for 'key'",
    ]


def test_validate_steps_reports_missing_templates_inside_list(tmp_path: Path) -> None:
    (tmp_path / "one.png").write_bytes(b"png")

    errors = validate_steps([{"type": "if_any_image", "templates": ["one", "missing"]}], template_root=tmp_path)

    assert errors == ["Step 1 (if_any_image): template 'missing' not found on disk"]


def test_validate_steps_checks_mouse_template_target(tmp_path: Path) -> None:
    (tmp_path / "button.png").write_bytes(b"png")

    errors = validate_steps(
        [
            {"type": "mouse_click", "button": "left", "target": "template", "template": ""},
            {"type": "mouse_move", "target": "template", "template": "missing"},
            {"type": "mouse_click", "button": "left", "target": "template", "template": "button"},
        ],
        template_root=tmp_path,
    )

    assert errors == [
        "Step 1 (mouse_click): empty template for template target",
        "Step 2 (mouse_move): template 'missing' not found on disk",
    ]


def test_exec_steps_raises_when_stop_event_is_set() -> None:
    runner = make_runner([])
    runner.stop_event.set()

    with pytest.raises(Stopped):
        runner.exec_steps([{"type": "key", "key": "enter"}])


def test_exec_steps_records_current_step_path_for_non_repeat() -> None:
    runner = make_runner([])
    calls = []
    runner.exec_step = lambda step, step_path: calls.append((step, step_path))

    runner.exec_steps([{"type": "key", "key": "enter"}], (("then", 1),), "else")

    assert runner.current_step == {"type": "key", "key": "enter"}
    assert runner.current_step_path == (("then", 1), ("else", 0))
    assert calls == [({"type": "key", "key": "enter"}, (("then", 1), ("else", 0)))]


def test_wait_image_timeout_stop_finishes_with_template_label() -> None:
    runner = make_runner([], templates={"start": {"label": "Start"}})
    finishes = []
    runner.wait_for_template = lambda template_id, timeout_ms, threshold: False
    runner.finish = lambda reason, message: finishes.append((reason, message))

    runner.exec_step({"type": "wait_image", "template": "start", "on_timeout": "stop"}, (("steps", 0),))

    assert finishes == [(StopReason.STALE, "wait_timeout: Start")]


def test_repeat_step_returns_when_child_stops_runner() -> None:
    runner = make_runner([])
    calls = []

    def exec_steps(steps, parent_path=(), branch_key="steps") -> None:
        calls.append((steps, parent_path, branch_key))
        runner.status.running = False

    runner.exec_steps = exec_steps

    step = {"type": "repeat", "count": 3, "steps": [{"type": "key", "key": "enter"}]}
    runner.exec_step(step, (("steps", 0),))

    assert calls == [(step["steps"], (("steps", 0),), "steps")]


def test_if_image_executes_else_branch_when_not_found() -> None:
    runner = make_runner([], templates={"start": {"label": "Start"}})
    calls = []
    runner.wait_for_template = lambda template_id, timeout_ms, threshold: False
    runner.exec_steps = lambda steps, parent_path=(), branch_key="steps": calls.append((steps, branch_key))
    step = {
        "type": "if_image",
        "template": "start",
        "then": [{"type": "key", "key": "enter"}],
        "else": [{"type": "key", "key": "esc"}],
    }

    runner.exec_step(step, (("steps", 0),))

    assert calls == [(step["else"], "else")]


def test_if_image_macro_to_runner_dict_keeps_else_branch() -> None:
    runner = make_runner(
        [
            {
                "type": "if_image",
                "template": "start",
                "then": [{"type": "key", "key": "enter"}],
                "else": [{"type": "key", "key": "esc"}],
            }
        ],
        templates={"start": {"label": "Start"}},
    )
    calls = []
    runner.wait_for_template = lambda template_id, timeout_ms, threshold: False
    runner.exec_steps = lambda steps, parent_path=(), branch_key="steps": calls.append((steps, branch_key))

    step = runner.macro["steps"][0]
    runner.exec_step(step, (("steps", 0),))

    assert "else_" not in step
    assert calls == [(step["else"], "else")]


def test_exec_step_dispatches_hold_key_until_gone_and_ignores_unknown_action() -> None:
    runner = make_runner([])
    calls = []
    step = {"type": "hold_key_until_gone", "key": "enter", "template": "start"}
    runner.do_hold_key_until_gone = lambda step: calls.append(step)

    runner.exec_step(step, (("steps", 0),))
    runner.exec_step({"type": "unknown"}, (("steps", 1),))

    assert calls == [step]


def test_exec_step_mouse_click_coordinate(monkeypatch) -> None:
    runner = make_runner([])
    runner.capture_rect = Rect(100, 200, 300, 400)
    calls = []
    monkeypatch.setattr(
        "remaku.services.macro_runner.keys.mouse_click", lambda button, x, y: calls.append((button, x, y))
    )

    runner.exec_step(
        {"type": "mouse_click", "button": "right", "target": "coordinate", "x": 10, "y": 20, "relative": True},
        (("steps", 0),),
    )

    assert calls == [("right", 110, 220)]


def test_exec_step_mouse_click_template_handles_empty_timeout_found_and_missing_position(monkeypatch) -> None:
    runner = make_runner([], templates={"button": {"label": "Button"}})
    clicks = []
    finishes = []
    runner.finish = lambda reason, message: finishes.append((reason, message))
    monkeypatch.setattr(
        "remaku.services.macro_runner.keys.mouse_click", lambda button, x, y: clicks.append((button, x, y))
    )

    runner.exec_step(
        {"type": "mouse_click", "button": "left", "target": "template", "template": "", "on_timeout": "stop"},
        (("steps", 0),),
    )
    runner.wait_for_template_position = lambda template_id, timeout_ms, threshold: (False, 0, 0)
    runner.exec_step(
        {"type": "mouse_click", "button": "left", "target": "template", "template": "button", "on_timeout": "stop"},
        (("steps", 1),),
    )
    runner.wait_for_template_position = lambda template_id, timeout_ms, threshold: (True, 12, 34)
    runner.exec_step(
        {"type": "mouse_click", "button": "left", "target": "template", "template": "button"},
        (("steps", 2),),
    )
    runner.resolve_mouse_position = lambda step: None
    runner.exec_step(
        {"type": "mouse_click", "button": "left", "target": "coordinate"},
        (("steps", 3),),
    )

    assert finishes == [
        (StopReason.STALE, "mouse_click: empty template"),
        (StopReason.STALE, "mouse_click_timeout: Button"),
    ]
    assert clicks == [("left", 12, 34)]


def test_exec_step_mouse_move_coordinate_template_and_empty_timeout(monkeypatch) -> None:
    runner = make_runner([], templates={"button": {"label": "Button"}})
    runner.capture_rect = Rect(100, 200, 300, 400)
    moves = []
    finishes = []
    runner.finish = lambda reason, message: finishes.append((reason, message))
    monkeypatch.setattr("remaku.services.macro_runner.keys.mouse_move", lambda x, y: moves.append((x, y)))

    runner.exec_step(
        {"type": "mouse_move", "target": "coordinate", "x": 10, "y": 20, "relative": False},
        (("steps", 0),),
    )
    runner.exec_step(
        {"type": "mouse_move", "target": "template", "template": "", "on_timeout": "stop"},
        (("steps", 1),),
    )
    runner.wait_for_template_position = lambda template_id, timeout_ms, threshold: (False, 0, 0)
    runner.exec_step(
        {"type": "mouse_move", "target": "template", "template": "button", "on_timeout": "stop"},
        (("steps", 2),),
    )
    runner.wait_for_template_position = lambda template_id, timeout_ms, threshold: (True, 12, 34)
    runner.exec_step(
        {"type": "mouse_move", "target": "template", "template": "button"},
        (("steps", 3),),
    )
    runner.resolve_mouse_position = lambda step: None
    runner.exec_step({"type": "mouse_move", "target": "coordinate"}, (("steps", 4),))

    assert moves == [(10, 20), (12, 34)]
    assert finishes == [
        (StopReason.STALE, "mouse_move: empty template"),
        (StopReason.STALE, "mouse_move_timeout: Button"),
    ]


def test_exec_step_mouse_scroll_uses_clicks_and_interval(monkeypatch) -> None:
    runner = make_runner([])
    calls = []
    monkeypatch.setattr(
        "remaku.services.macro_runner.keys.mouse_scroll",
        lambda clicks, interval_ms: calls.append((clicks, interval_ms)),
    )

    runner.exec_step({"type": "mouse_scroll", "clicks": -5, "interval_ms": 25}, (("steps", 0),))

    assert calls == [(-5, 25)]


def test_hold_key_until_gone_raises_when_stop_requested(monkeypatch) -> None:
    runner = make_hold_key_runner()
    runner.stop_event.set()
    monkeypatch.setattr("remaku.services.macro_runner.keys.held", FakeHeldContext)
    runner.sleep = lambda ms, pause_callback=None, resume_callback=None: None

    with pytest.raises(Stopped):
        runner.do_hold_key_until_gone(
            {"type": "hold_key_until_gone", "key": "enter", "template": "start", "load_delay_ms": 0}
        )


def test_hold_key_until_gone_sleeps_when_frame_is_missing(monkeypatch) -> None:
    runner = make_hold_key_runner()
    sleep_calls = []
    grab_calls = []

    def fake_grab(rect: Rect):
        grab_calls.append(rect)

        return None if len(grab_calls) == 1 else np.ones((10, 10, 3), dtype=np.uint8)

    monkeypatch.setattr("remaku.services.macro_runner.window.is_foreground", lambda window: True)
    monkeypatch.setattr("remaku.services.macro_runner.keys.held", FakeHeldContext)
    monkeypatch.setattr(
        "remaku.services.macro_runner.vision.match_template",
        lambda frame, template, match_mode="grayscale": (0.0, (0, 0)),
    )
    runner.grabber.grab = fake_grab
    runner.sleep = lambda ms, pause_callback=None, resume_callback=None: sleep_calls.append(ms)

    runner.do_hold_key_until_gone(
        {
            "type": "hold_key_until_gone",
            "key": "enter",
            "template": "start",
            "load_delay_ms": 0,
            "find_timeout_ms": 0,
        }
    )

    assert sleep_calls == [0, 100.0]


def test_hold_key_until_gone_scales_template_and_releases_after_grace(monkeypatch) -> None:
    runner = make_hold_key_runner()
    runner.template_capture_sizes = {"start": (5, 5), "unused": None}
    scaled_template = np.ones((5, 5), dtype=np.uint8)
    match_returns = iter([(1.0, (0, 0)), (0.0, (0, 0))])
    scale_calls = []

    def fake_scale(template, frame_shape, capture_size):
        scale_calls.append((template, frame_shape, capture_size))

        return scaled_template

    monkeypatch.setattr("remaku.services.macro_runner.window.is_foreground", lambda window: True)
    monkeypatch.setattr("remaku.services.macro_runner.keys.held", FakeHeldContext)
    monkeypatch.setattr("remaku.services.macro_runner.vision.scale_template", fake_scale)
    monkeypatch.setattr(
        "remaku.services.macro_runner.vision.match_template",
        lambda frame, template, match_mode="grayscale": next(match_returns),
    )
    runner.sleep = lambda ms, pause_callback=None, resume_callback=None: None
    runner.sleep_remaining = lambda tick_start, period, pause_callback=None, resume_callback=None: None

    runner.do_hold_key_until_gone(
        {
            "type": "hold_key_until_gone",
            "key": "enter",
            "template": "start",
            "load_delay_ms": 0,
            "gone_grace_ms": 0,
            "threshold": 0.8,
        }
    )

    assert scale_calls == [(runner.templates["start"], (10, 10, 3), (5, 5))]


def test_hold_key_until_gone_releases_on_hard_timeout(monkeypatch) -> None:
    runner = make_hold_key_runner()
    times = iter([0.0, 0.0, 2.0])
    monkeypatch.setattr("remaku.services.macro_runner.window.is_foreground", lambda window: True)
    monkeypatch.setattr("remaku.services.macro_runner.keys.held", FakeHeldContext)
    monkeypatch.setattr(
        "remaku.services.macro_runner.vision.match_template",
        lambda frame, template, match_mode="grayscale": (1.0, (0, 0)),
    )
    monkeypatch.setattr("remaku.services.macro_runner.time.monotonic", lambda: next(times))
    runner.sleep = lambda ms, pause_callback=None, resume_callback=None: None

    runner.do_hold_key_until_gone(
        {
            "type": "hold_key_until_gone",
            "key": "enter",
            "template": "start",
            "load_delay_ms": 0,
            "hard_timeout_ms": 1000,
            "threshold": 0.8,
        }
    )


def test_wait_for_template_position_returns_center_and_updates_score(monkeypatch) -> None:
    runner = make_hold_key_runner()
    runner.capture_rect = Rect(100, 200, 300, 400)
    runner.templates = {"start": np.ones((4, 6), dtype=np.uint8)}
    runner.template_capture_sizes = cast(dict[str, tuple[int, int] | None], {"start": None})
    updates = []
    runner.capture_tick = lambda: np.ones((20, 30), dtype=np.uint8)
    runner.update = lambda **fields: updates.append(fields)
    match_calls = []

    def fake_match(frame, template, match_mode="grayscale"):
        match_calls.append((frame, template, match_mode))
        return (0.9, (7, 8))

    runner.macro["templates"]["start"]["match_mode"] = "color"
    monkeypatch.setattr("remaku.services.macro_runner.vision.match_template", fake_match)

    found, x, y = runner.wait_for_template_position("start", 1000, 0.8)

    assert (found, x, y) == (True, 110, 210)
    assert updates == [{"score": 0.9, "match_id": "start"}]
    assert len(match_calls) == 1
    assert match_calls[0][0].shape == (20, 30)
    assert match_calls[0][1] is runner.templates["start"]
    assert match_calls[0][2] == "color"


def test_wait_for_template_position_handles_missing_frame_timeout_and_stop(monkeypatch) -> None:
    runner = make_hold_key_runner()
    runner.templates = {"start": np.ones((4, 6), dtype=np.uint8)}
    sleeps = []
    frames = iter([None, np.ones((20, 30), dtype=np.uint8)])
    runner.capture_tick = lambda: next(frames)
    runner.sleep_remaining = lambda tick_start, period, pause_callback=None, resume_callback=None: sleeps.append(period)
    monkeypatch.setattr(
        "remaku.services.macro_runner.vision.match_template",
        lambda frame, template, match_mode="grayscale": (0.0, (0, 0)),
    )

    assert runner.wait_for_template_position("start", 0, 0.8) == (False, 0, 0)

    times = iter([0.0, 0.0, 0.0, 0.2])
    monkeypatch.setattr("remaku.services.macro_runner.time.monotonic", lambda: next(times))
    assert runner.wait_for_template_position("start", 100, 0.8) == (False, 0, 0)
    assert sleeps == [0.1]

    runner.stop_event.set()
    monkeypatch.setattr("remaku.services.macro_runner.time.monotonic", lambda: 0.0)
    with pytest.raises(Stopped):
        runner.wait_for_template_position("start", 100, 0.8)


def test_wait_for_template_position_sleeps_after_missed_match(monkeypatch) -> None:
    runner = make_hold_key_runner()
    runner.templates = {"start": np.ones((4, 6), dtype=np.uint8)}
    sleeps = []
    times = iter([0.0, 0.0, 0.0, 0.2])
    runner.capture_tick = lambda: np.ones((20, 30), dtype=np.uint8)
    runner.sleep_remaining = lambda tick_start, period, pause_callback=None, resume_callback=None: sleeps.append(period)
    monkeypatch.setattr("remaku.services.macro_runner.time.monotonic", lambda: next(times))
    monkeypatch.setattr(
        "remaku.services.macro_runner.vision.match_template",
        lambda frame, template, match_mode="grayscale": (0.0, (0, 0)),
    )

    assert runner.wait_for_template_position("start", 100, 0.8) == (False, 0, 0)
    assert sleeps == [0.1]
