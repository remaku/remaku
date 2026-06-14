import copy
import json

import pytest

from remaku.models.macro_model import (
    DEFAULT_DELAY_MS,
    DEFAULT_FIND_TIMEOUT_MS,
    DEFAULT_GONE_GRACE_MS,
    DEFAULT_GRID_ROWS,
    DEFAULT_GRID_START,
    DEFAULT_HARD_TIMEOUT_MS,
    DEFAULT_IMAGE_TIMEOUT,
    DEFAULT_KEY,
    DEFAULT_KEY_HOLD_MS,
    DEFAULT_LOAD_DELAY_MS,
    DEFAULT_ON_TIMEOUT,
    DEFAULT_REPEAT_COUNT,
    DEFAULT_TEXT_INPUT_INTERVAL_MS,
    DEFAULT_TEXT_INPUT_TEXT,
    DEFAULT_THRESHOLD,
    DelayStep,
    GridNavStep,
    HoldKeyUntilGoneStep,
    IfAnyImageStep,
    IfImageStep,
    KeyStep,
    Macro,
    MacroModel,
    RepeatStep,
    TextInputStep,
    WaitImageStep,
    get_step_count,
    get_step_find_timeout,
    get_step_gone_grace,
    get_step_hard_timeout,
    get_step_hold_ms,
    get_step_interval_ms,
    get_step_key,
    get_step_load_delay,
    get_step_ms,
    get_step_on_timeout,
    get_step_rows,
    get_step_start,
    get_step_template,
    get_step_templates,
    get_step_text,
    get_step_threshold,
    get_step_timeout,
    parse_step,
    parse_steps,
)


def test_parse_step_rejects_non_dict() -> None:
    with pytest.raises(ValueError, match="Step must be a dictionary"):
        parse_step("key")


def test_parse_step_rejects_unknown_type() -> None:
    with pytest.raises(ValueError, match="Unknown step type"):
        parse_step({"type": "missing"})


def test_parse_steps_returns_empty_list_for_non_list() -> None:
    assert parse_steps({"type": "key"}) == []


def test_macro_from_dict_parses_nested_steps(sample_macro_dict: dict) -> None:
    macro = Macro.from_dict(sample_macro_dict)

    assert macro.meta.id == "sample"
    assert macro.meta.label == "Sample Macro"
    assert macro.templates["start"].capture_width == 320
    assert isinstance(macro.steps[0], KeyStep)
    assert isinstance(macro.steps[1], RepeatStep)
    assert isinstance(macro.steps[1].steps[1], WaitImageStep)
    assert isinstance(macro.steps[2], IfImageStep)


def test_macro_to_dict_keeps_legacy_name_key(sample_macro_dict: dict) -> None:
    macro = Macro.from_dict(sample_macro_dict)

    data = macro.to_dict()

    assert data["meta"]["name"] == "sample"
    assert data["steps"][1]["steps"][1]["template"] == "start"
    assert data["steps"][2]["else_"][0]["ms"] == 50


def test_grid_nav_parses_nested_branches() -> None:
    step = parse_step(
        {
            "type": "grid_nav",
            "rows": "3",
            "start": "1",
            "on_next_row": [{"type": "key", "key": "down"}],
            "on_next_col": [{"type": "key", "key": "right"}],
        }
    )

    assert isinstance(step, GridNavStep)
    row_step = step.on_next_row[0]
    col_step = step.on_next_col[0]

    assert isinstance(row_step, KeyStep)
    assert isinstance(col_step, KeyStep)
    assert step.rows == 3
    assert step.start == 1
    assert row_step.key == "down"
    assert col_step.key == "right"


def test_if_any_image_ignores_non_dict_branches() -> None:
    step = parse_step({"type": "if_any_image", "templates": [1, "two"], "branches": "bad"})

    assert isinstance(step, IfAnyImageStep)
    assert step.templates == ["1", "two"]
    assert step.branches == {}


def test_hold_key_until_gone_parses_string_values() -> None:
    step = parse_step(
        {
            "type": "hold_key_until_gone",
            "key": "space",
            "template": "loading",
            "load_delay_ms": "10",
            "find_timeout_ms": "20",
            "gone_grace_ms": "30",
            "hard_timeout_ms": "40",
            "threshold": "0.7",
        }
    )

    assert isinstance(step, HoldKeyUntilGoneStep)
    assert step.key == "space"
    assert step.template == "loading"
    assert step.load_delay_ms == 10
    assert step.find_timeout_ms == 20
    assert step.gone_grace_ms == 30
    assert step.hard_timeout_ms == 40
    assert step.threshold == 0.7


def test_text_input_parses_string_values() -> None:
    step = parse_step({"type": "text_input", "text": "哈囉\nworld", "interval_ms": "25"})

    assert isinstance(step, TextInputStep)
    assert step.text == "哈囉\nworld"
    assert step.interval_ms == 25


def test_step_getters_return_defaults_for_missing_values() -> None:
    step = {}

    assert get_step_threshold(step) == DEFAULT_THRESHOLD
    assert get_step_timeout(step) == DEFAULT_IMAGE_TIMEOUT
    assert get_step_key(step) == DEFAULT_KEY
    assert get_step_hold_ms(step) == DEFAULT_KEY_HOLD_MS
    assert get_step_ms(step) == DEFAULT_DELAY_MS
    assert get_step_load_delay(step) == DEFAULT_LOAD_DELAY_MS
    assert get_step_find_timeout(step) == DEFAULT_FIND_TIMEOUT_MS
    assert get_step_gone_grace(step) == DEFAULT_GONE_GRACE_MS
    assert get_step_hard_timeout(step) == DEFAULT_HARD_TIMEOUT_MS
    assert get_step_count(step) == DEFAULT_REPEAT_COUNT
    assert get_step_rows(step) == DEFAULT_GRID_ROWS
    assert get_step_start(step) == DEFAULT_GRID_START
    assert get_step_on_timeout(step) == DEFAULT_ON_TIMEOUT
    assert get_step_template(step) == ""
    assert get_step_templates(step) == []
    assert get_step_text(step) == DEFAULT_TEXT_INPUT_TEXT
    assert get_step_interval_ms(step) == DEFAULT_TEXT_INPUT_INTERVAL_MS


def test_all_step_to_dict_methods_return_dataclass_dicts() -> None:
    steps = [
        KeyStep(key="enter"),
        DelayStep(ms=10),
        WaitImageStep(template="start"),
        HoldKeyUntilGoneStep(key="space", template="loading"),
        TextInputStep(text="hello", interval_ms=20),
        RepeatStep(steps=[KeyStep(key="tab")]),
        IfImageStep(then=[KeyStep(key="a")], else_=[DelayStep(ms=1)]),
        IfAnyImageStep(templates=["one"], branches={"one": [KeyStep(key="b")]}),
        GridNavStep(on_next_row=[KeyStep(key="down")], on_next_col=[KeyStep(key="right")]),
    ]

    for step in steps:
        assert step.to_dict()["type"] == step.type


def test_macro_model_round_trips_macro(isolated_data_dir, sample_macro_dict: dict) -> None:
    model = MacroModel()
    macro = Macro.from_dict(copy.deepcopy(sample_macro_dict))

    model.save(macro)
    loaded = model.load("sample")

    assert loaded is not None
    assert loaded.meta.id == "sample"
    assert loaded.meta.label == "Sample Macro"
    assert model.list_macros()[0].id == "sample"
    assert (
        json.loads((isolated_data_dir / "macros" / "sample.json").read_text(encoding="utf-8"))["meta"]["name"]
        == "sample"
    )


def test_macro_model_ignores_invalid_macro_file(isolated_data_dir) -> None:
    macro_dir = isolated_data_dir / "macros"
    macro_dir.mkdir(parents=True)
    (macro_dir / "broken.json").write_text("not json", encoding="utf-8")

    assert MacroModel().list_macros() == []
    assert MacroModel().load("broken") is None


def test_macro_model_returns_none_for_missing_or_non_dict_macro(isolated_data_dir) -> None:
    macro_dir = isolated_data_dir / "macros"
    macro_dir.mkdir(parents=True)
    (macro_dir / "list.json").write_text("[]", encoding="utf-8")

    model = MacroModel()

    assert model.load("missing") is None
    assert model.load("list") is None


def test_macro_model_delete_reports_missing_and_deleted_macro(isolated_data_dir, sample_macro_dict: dict) -> None:
    model = MacroModel()
    macro = Macro.from_dict(sample_macro_dict)
    model.save(macro)

    assert model.delete("missing") is False
    assert model.delete("sample") is True
    assert model.load("sample") is None
