import copy
import json

import pytest

from remaku.models.macro_model import (
    GridNavStep,
    IfImageStep,
    KeyStep,
    Macro,
    MacroModel,
    RepeatStep,
    WaitImageStep,
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
