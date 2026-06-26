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
    DEFAULT_NUMBER_CAPTURE_HEIGHT,
    DEFAULT_NUMBER_CAPTURE_WIDTH,
    DEFAULT_NUMBER_CHECK_FIRST,
    DEFAULT_NUMBER_HEIGHT,
    DEFAULT_NUMBER_OPERATOR,
    DEFAULT_NUMBER_RELATIVE,
    DEFAULT_NUMBER_STABLE_READS,
    DEFAULT_NUMBER_VALUE,
    DEFAULT_NUMBER_WIDTH,
    DEFAULT_NUMBER_X,
    DEFAULT_NUMBER_Y,
    DEFAULT_ON_TIMEOUT,
    DEFAULT_REPEAT_COUNT,
    DEFAULT_TEMPLATE_MATCH_MODE,
    DEFAULT_TEXT_INPUT_INTERVAL_MS,
    DEFAULT_TEXT_INPUT_TEXT,
    DEFAULT_THRESHOLD,
    DelayStep,
    GridNavStep,
    HoldKeyUntilGoneStep,
    IfAnyImageStep,
    IfImageStep,
    IfNumberStep,
    KeyStep,
    Macro,
    MacroModel,
    MacroVariable,
    MouseClickStep,
    MouseMoveStep,
    MouseScrollStep,
    RepeatStep,
    RepeatUntilNumberStep,
    TextInputStep,
    WaitImageStep,
    WaitNumberStep,
    get_step_button,
    get_step_count,
    get_step_find_timeout,
    get_step_gone_grace,
    get_step_hard_timeout,
    get_step_hold_ms,
    get_step_interval_ms,
    get_step_key,
    get_step_load_delay,
    get_step_mouse_relative,
    get_step_mouse_target,
    get_step_mouse_x,
    get_step_mouse_y,
    get_step_ms,
    get_step_number_capture_height,
    get_step_number_capture_width,
    get_step_number_check_first,
    get_step_number_height,
    get_step_number_operator,
    get_step_number_relative,
    get_step_number_stable_reads,
    get_step_number_value,
    get_step_number_width,
    get_step_number_x,
    get_step_number_y,
    get_step_on_timeout,
    get_step_rows,
    get_step_scroll_clicks,
    get_step_start,
    get_step_template,
    get_step_templates,
    get_step_text,
    get_step_threshold,
    get_step_timeout,
    parse_step,
    parse_steps,
    resolve_step_variables,
    slugify_variable_name,
    variable_ref,
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
    assert macro.templates["start"].match_mode == DEFAULT_TEMPLATE_MATCH_MODE
    assert isinstance(macro.steps[0], KeyStep)
    assert isinstance(macro.steps[1], RepeatStep)
    assert isinstance(macro.steps[1].steps[1], WaitImageStep)
    assert isinstance(macro.steps[2], IfImageStep)


def test_macro_to_dict_keeps_legacy_name_key(sample_macro_dict: dict) -> None:
    macro = Macro.from_dict(sample_macro_dict)

    data = macro.to_dict()

    assert data["meta"]["name"] == "sample"
    assert data["gaming_mode"] is True
    assert data["steps"][1]["steps"][1]["template"] == "start"
    assert data["steps"][2]["else"][0]["ms"] == 50
    assert "else_" not in data["steps"][2]


def test_macro_gaming_mode_defaults_and_round_trips(sample_macro_dict: dict) -> None:
    legacy_macro = Macro.from_dict(sample_macro_dict)
    non_gaming_macro = Macro.from_dict({**sample_macro_dict, "gaming_mode": False})

    assert legacy_macro.gaming_mode is True
    assert non_gaming_macro.gaming_mode is False
    assert Macro.from_dict(non_gaming_macro.to_dict()).gaming_mode is False


def test_macro_background_options_default_and_round_trip(sample_macro_dict: dict) -> None:
    legacy_macro = Macro.from_dict(sample_macro_dict)
    configured_macro = Macro.from_dict(
        {
            **sample_macro_dict,
            "background_input": False,
            "keep_target_focused": True,
        }
    )

    assert legacy_macro.background_input is True
    assert legacy_macro.keep_target_focused is False
    assert configured_macro.background_input is False
    assert configured_macro.keep_target_focused is True
    assert Macro.from_dict(configured_macro.to_dict()).background_input is False
    assert Macro.from_dict(configured_macro.to_dict()).keep_target_focused is True


def test_macro_variables_round_trip_and_step_refs(sample_macro_dict: dict) -> None:
    sample_macro_dict["variables"] = {
        "repeat_count": {"label": "Repeat Count", "type": "number", "value": "3"},
        "message": {"label": "Message", "type": "text", "value": "Hello"},
        "bad-name": {"label": "Bad", "type": "number", "value": 1},
    }
    sample_macro_dict["steps"] = [
        {"type": "repeat", "count": variable_ref("repeat_count"), "steps": []},
        {"type": "text_input", "text": variable_ref("message")},
    ]

    macro = Macro.from_dict(sample_macro_dict)
    data = macro.to_dict()

    assert set(macro.variables) == {"repeat_count", "message"}
    assert macro.variables["repeat_count"].value == 3
    assert data["variables"]["message"]["value"] == "Hello"
    assert data["steps"][0]["count"] == variable_ref("repeat_count")
    assert data["steps"][1]["text"] == variable_ref("message")


def test_slugify_variable_name_normalizes_user_text() -> None:
    assert slugify_variable_name("Repeat Count!") == "repeat_count"
    assert slugify_variable_name("  3 runs  ") == "variable_3_runs"
    assert slugify_variable_name("") == "variable"


def test_resolve_step_variables_replaces_supported_refs_and_reports_errors() -> None:
    steps = [
        {
            "type": "repeat",
            "count": variable_ref("repeat_count"),
            "steps": [{"type": "key", "key": variable_ref("go")}],
        },
        {"type": "delay", "ms": variable_ref("missing")},
        {"type": "text_input", "text": variable_ref("repeat_count")},
    ]
    variables = {
        "repeat_count": MacroVariable(type="number", value=2),
        "go": MacroVariable(type="key", value="enter"),
    }

    resolved, errors = resolve_step_variables(steps, variables)

    assert resolved[0]["count"] == 2
    assert resolved[0]["steps"][0]["key"] == "enter"
    assert errors == [
        "Step 2: missing variable 'missing' for field 'ms'",
        "Step 3: variable 'repeat_count' for field 'text' must be text",
    ]


def test_template_match_mode_round_trips_and_rejects_unknown_value(sample_macro_dict: dict) -> None:
    sample_macro_dict["templates"]["start"]["match_mode"] = "color"
    sample_macro_dict["templates"]["done"]["match_mode"] = "bad"

    macro = Macro.from_dict(sample_macro_dict)
    data = macro.to_dict()

    assert macro.templates["start"].match_mode == "color"
    assert macro.templates["done"].match_mode == DEFAULT_TEMPLATE_MATCH_MODE
    assert data["templates"]["start"]["match_mode"] == "color"


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


def test_number_steps_parse_string_values() -> None:
    wait_step = parse_step(
        {
            "type": "wait_number",
            "x": "10",
            "y": "20",
            "width": "120",
            "height": "40",
            "relative": "false",
            "capture_width": "1920",
            "capture_height": "1080",
            "operator": "≥",
            "value": "999",
            "timeout_ms": "500",
            "stable_reads": "3",
        }
    )
    if_step = parse_step(
        {
            "type": "if_number",
            "operator": "bad",
            "then": [{"type": "key", "key": "enter"}],
            "else": [{"type": "delay", "ms": 50}],
        }
    )
    repeat_step = parse_step(
        {
            "type": "repeat_until_number",
            "count": "20",
            "check_first": "false",
            "steps": [{"type": "key", "key": "space"}],
        }
    )

    assert isinstance(wait_step, WaitNumberStep)
    assert wait_step.x == 10
    assert wait_step.y == 20
    assert wait_step.width == 120
    assert wait_step.height == 40
    assert wait_step.relative is False
    assert wait_step.capture_width == 1920
    assert wait_step.capture_height == 1080
    assert wait_step.operator == "≥"
    assert wait_step.value == 999
    assert wait_step.timeout_ms == 500
    assert wait_step.stable_reads == 3
    assert isinstance(if_step, IfNumberStep)
    assert if_step.operator == DEFAULT_NUMBER_OPERATOR
    assert isinstance(if_step.then[0], KeyStep)
    assert isinstance(if_step.else_[0], DelayStep)
    assert isinstance(repeat_step, RepeatUntilNumberStep)
    assert repeat_step.count == 20
    assert repeat_step.check_first is False
    assert isinstance(repeat_step.steps[0], KeyStep)


def test_mouse_steps_parse_string_values() -> None:
    click_step = parse_step(
        {
            "type": "mouse_click",
            "skip": "true",
            "note": "press",
            "button": "right",
            "target": "template",
            "x": "10",
            "y": "20",
            "relative": "",
            "template": "button",
            "threshold": "0.9",
            "timeout_ms": "250",
            "on_timeout": "continue",
        }
    )
    move_step = parse_step(
        {
            "type": "mouse_move",
            "target": "coordinate",
            "x": "30",
            "y": "40",
            "relative": "false",
            "template": "marker",
            "threshold": "0.7",
            "timeout_ms": "500",
            "on_timeout": "stop",
        }
    )
    scroll_step = parse_step({"type": "mouse_scroll", "clicks": "-3", "interval_ms": "25"})

    assert isinstance(click_step, MouseClickStep)
    assert click_step.skip is True
    assert click_step.note == "press"
    assert click_step.button == "right"
    assert click_step.target == "template"
    assert click_step.x == 10
    assert click_step.y == 20
    assert click_step.relative is False
    assert click_step.template == "button"
    assert click_step.threshold == 0.9
    assert click_step.timeout_ms == 250
    assert click_step.on_timeout == "continue"
    assert isinstance(move_step, MouseMoveStep)
    assert move_step.x == 30
    assert move_step.y == 40
    assert move_step.relative is True
    assert move_step.template == "marker"
    assert move_step.threshold == 0.7
    assert isinstance(scroll_step, MouseScrollStep)
    assert scroll_step.clicks == -3
    assert scroll_step.interval_ms == 25


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
    assert get_step_button(step) == "left"
    assert get_step_mouse_target(step) == "coordinate"
    assert get_step_mouse_x(step) == 0
    assert get_step_mouse_y(step) == 0
    assert get_step_mouse_relative(step) is True
    assert get_step_scroll_clicks(step) == 3
    assert get_step_number_x(step) == DEFAULT_NUMBER_X
    assert get_step_number_y(step) == DEFAULT_NUMBER_Y
    assert get_step_number_width(step) == DEFAULT_NUMBER_WIDTH
    assert get_step_number_height(step) == DEFAULT_NUMBER_HEIGHT
    assert get_step_number_relative(step) == DEFAULT_NUMBER_RELATIVE
    assert get_step_number_capture_width(step) == DEFAULT_NUMBER_CAPTURE_WIDTH
    assert get_step_number_capture_height(step) == DEFAULT_NUMBER_CAPTURE_HEIGHT
    assert get_step_number_operator(step) == DEFAULT_NUMBER_OPERATOR
    assert get_step_number_value(step) == DEFAULT_NUMBER_VALUE
    assert get_step_number_stable_reads(step) == DEFAULT_NUMBER_STABLE_READS
    assert get_step_number_check_first(step) == DEFAULT_NUMBER_CHECK_FIRST


def test_all_step_to_dict_methods_return_dataclass_dicts() -> None:
    steps = [
        KeyStep(key="enter"),
        DelayStep(ms=10),
        WaitImageStep(template="start"),
        HoldKeyUntilGoneStep(key="space", template="loading"),
        TextInputStep(text="hello", interval_ms=20),
        WaitNumberStep(width=100, height=30, value=999),
        IfNumberStep(then=[KeyStep(key="a")], else_=[DelayStep(ms=1)]),
        RepeatUntilNumberStep(steps=[KeyStep(key="space")]),
        RepeatStep(steps=[KeyStep(key="tab")]),
        IfImageStep(then=[KeyStep(key="a")], else_=[DelayStep(ms=1)]),
        IfAnyImageStep(templates=["one"], branches={"one": [KeyStep(key="b")]}),
        GridNavStep(on_next_row=[KeyStep(key="down")], on_next_col=[KeyStep(key="right")]),
        MouseClickStep(button="middle", x=10, y=20),
        MouseMoveStep(x=30, y=40),
        MouseScrollStep(clicks=-2, interval_ms=25),
    ]

    for step in steps:
        assert step.to_dict()["type"] == step.type


def test_if_image_to_dict_uses_json_else_key() -> None:
    step = IfImageStep(
        then=[RepeatStep(steps=[IfImageStep(else_=[KeyStep(key="nested")])])],
        else_=[DelayStep(ms=1)],
    )

    data = step.to_dict()

    assert data["else"] == [{"type": "delay", "skip": False, "note": "", "ms": 1}]
    assert "else_" not in data
    assert data["then"][0]["steps"][0]["else"] == [
        {"type": "key", "skip": False, "note": "", "key": "nested", "hold_ms": DEFAULT_KEY_HOLD_MS}
    ]
    assert "else_" not in data["then"][0]["steps"][0]


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
    saved_step = json.loads((isolated_data_dir / "macros" / "sample.json").read_text(encoding="utf-8"))["steps"][2]
    assert saved_step["else"][0]["ms"] == 50
    assert "else_" not in saved_step


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
