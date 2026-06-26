from pathlib import Path

from remaku.models.macro_model import Macro, MacroMeta, MacroVariable, TemplateInfo, variable_ref
from remaku.models.step_tree import StepTree
from remaku.services.clipboard_service import ClipboardService


def make_service(tmp_path: Path, ids: list[str] | None = None) -> ClipboardService:
    id_iter = iter(ids or ["copied"])

    return ClipboardService(
        lambda macro_id, template_id: tmp_path / "templates" / macro_id / f"{template_id}.png",
        lambda macro_id: tmp_path / "templates" / macro_id,
        lambda: next(id_iter),
        lambda template_id: f"Template {template_id}",
    )


def test_copy_selected_steps_includes_template_data_and_meta(tmp_path: Path) -> None:
    step = {"type": "wait_image", "template": "button"}
    macro = Macro.from_dict(
        {
            "meta": {"name": "macro"},
            "templates": {"button": {"label": "Button", "capture_width": 320}},
            "steps": [step],
        }
    )
    service = make_service(tmp_path)
    template_file = tmp_path / "templates" / "macro" / "button.png"
    template_file.parent.mkdir(parents=True)
    template_file.write_bytes(b"png")
    step_tree = StepTree([step])

    clipboard = service.copy_selected_steps(macro, step_tree, step_tree.flatten())

    assert clipboard is not None
    assert clipboard["steps"] == [{"type": "wait_image", "template": "button"}]
    assert clipboard["templates"] == {"button": b"png"}
    assert clipboard["template_meta"] == {
        "button": {
            "label": "Button",
            "capture_width": 320,
            "capture_height": 0,
            "match_mode": "grayscale",
        }
    }


def test_copy_selected_steps_includes_used_variables(tmp_path: Path) -> None:
    step = {"type": "repeat", "count": variable_ref("runs"), "steps": []}
    macro = Macro(
        meta=MacroMeta(id="macro"),
        variables={
            "runs": MacroVariable(label="Runs", type="number", value=3),
            "message": MacroVariable(label="Message", type="text", value="hello"),
        },
    )
    service = make_service(tmp_path)
    step_tree = StepTree([step])

    clipboard = service.copy_selected_steps(macro, step_tree, step_tree.flatten())

    assert clipboard is not None
    assert clipboard["variables"] == {"runs": {"label": "Runs", "type": "number", "value": 3}}


def test_paste_steps_clones_template_and_metadata(tmp_path: Path) -> None:
    macro = Macro(meta=MacroMeta(id="macro"), templates={"button": TemplateInfo()})
    service = make_service(tmp_path)
    step_tree = StepTree([])
    clipboard = {
        "steps": [{"type": "wait_image", "template": "button"}],
        "templates": {"button": b"png"},
        "template_meta": {"button": {"label": "Button", "capture_width": 320, "capture_height": 180}},
    }

    result = service.paste_steps(macro, step_tree, clipboard, None, None)

    assert result.changed is True
    assert result.selected_step == step_tree.steps[0]
    assert step_tree.steps[0]["template"] == "copied"
    assert (tmp_path / "templates" / "macro" / "copied.png").read_bytes() == b"png"
    assert macro.templates["button"].label == ""
    assert macro.templates["copied"].label == "Button"
    assert macro.templates["copied"].capture_width == 320
    assert macro.templates["copied"].capture_height == 180


def test_paste_steps_adds_missing_variables(tmp_path: Path) -> None:
    macro = Macro(meta=MacroMeta(id="macro"))
    service = make_service(tmp_path)
    step_tree = StepTree([])
    clipboard = {
        "steps": [{"type": "repeat", "count": variable_ref("runs"), "steps": []}],
        "variables": {"runs": {"label": "Runs", "type": "number", "value": 3}},
    }

    service.paste_steps(macro, step_tree, clipboard, None, None)

    assert step_tree.steps[0]["count"] == variable_ref("runs")
    assert macro.variables["runs"] == MacroVariable(label="Runs", type="number", value=3)


def test_paste_steps_renames_conflicting_variables(tmp_path: Path) -> None:
    macro = Macro(
        meta=MacroMeta(id="macro"),
        variables={"runs": MacroVariable(label="Runs", type="number", value=10)},
    )
    service = make_service(tmp_path)
    step_tree = StepTree([])
    clipboard = {
        "steps": [
            {
                "type": "repeat",
                "count": variable_ref("runs"),
                "steps": [{"type": "delay", "ms": variable_ref("runs")}],
            }
        ],
        "variables": {"runs": {"label": "Runs", "type": "number", "value": 3}},
    }

    service.paste_steps(macro, step_tree, clipboard, None, None)

    assert macro.variables["runs"].value == 10
    assert macro.variables["runs_2"] == MacroVariable(label="Runs", type="number", value=3)
    assert step_tree.steps[0]["count"] == variable_ref("runs_2")
    assert step_tree.steps[0]["steps"][0]["ms"] == variable_ref("runs_2")


def test_paste_steps_clones_each_template_slot_independently(tmp_path: Path) -> None:
    macro = Macro(meta=MacroMeta(id="macro"))
    service = make_service(tmp_path, ["copy", "copy", "copy"])
    step_tree = StepTree([])
    clipboard = {
        "steps": [
            {
                "type": "if_any_image",
                "templates": ["button"],
                "branches": {"button": [{"type": "wait_image", "template": "button"}]},
            },
            {"type": "wait_image", "template": "button"},
        ],
        "templates": {"button": b"png"},
        "template_meta": {"button": {"label": "Button", "capture_width": 320, "capture_height": 180}},
    }

    service.paste_steps(macro, step_tree, clipboard, None, None)

    assert step_tree.steps[0]["templates"] == ["copy"]
    assert step_tree.steps[0]["branches"]["copy"][0]["template"] == "copy1"
    assert step_tree.steps[1]["template"] == "copy2"
    assert set(macro.templates) == {"copy", "copy1", "copy2"}
    assert (tmp_path / "templates" / "macro" / "copy.png").read_bytes() == b"png"
    assert (tmp_path / "templates" / "macro" / "copy1.png").read_bytes() == b"png"
    assert (tmp_path / "templates" / "macro" / "copy2.png").read_bytes() == b"png"


def test_paste_steps_returns_unchanged_for_empty_steps(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    macro = Macro(meta=MacroMeta(id="macro"))
    selected_step = {"type": "key", "key": "enter"}

    result = service.paste_steps(macro, StepTree([]), {"steps": []}, None, selected_step)

    assert result.changed is False
    assert result.selected_step is selected_step
