from pathlib import Path

from remaku.models.macro_model import Macro
from remaku.services.engine import StopReason
from remaku.services.macro_runner import MacroRunner, validate_steps


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


def test_validate_steps_accepts_existing_templates(tmp_path: Path) -> None:
    (tmp_path / "start.png").write_bytes(b"png")

    assert validate_steps([{"type": "wait_image", "template": "start"}], template_root=tmp_path) == []


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
