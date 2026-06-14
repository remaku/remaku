from pathlib import Path

from remaku.models.macro_model import Macro, MacroMeta, TemplateInfo
from remaku.models.step_tree import StepTree
from remaku.services.clipboard_service import ClipboardService


def make_service(tmp_path: Path) -> ClipboardService:
    return ClipboardService(
        lambda macro_id, template_id: tmp_path / "templates" / macro_id / f"{template_id}.png",
        lambda macro_id: tmp_path / "templates" / macro_id,
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


def test_paste_steps_writes_template_and_merges_existing_meta(tmp_path: Path) -> None:
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
    assert (tmp_path / "templates" / "macro" / "button.png").read_bytes() == b"png"
    assert macro.templates["button"].label == "Button"
    assert macro.templates["button"].capture_width == 320
    assert macro.templates["button"].capture_height == 180


def test_paste_steps_returns_unchanged_for_empty_steps(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    macro = Macro(meta=MacroMeta(id="macro"))
    selected_step = {"type": "key", "key": "enter"}

    result = service.paste_steps(macro, StepTree([]), {"steps": []}, None, selected_step)

    assert result.changed is False
    assert result.selected_step is selected_step
