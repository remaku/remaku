from pathlib import Path

from remaku.models.macro_model import Macro, MacroMeta, TemplateInfo
from remaku.models.step_tree import StepTree
from remaku.services.template_service import TemplateService


def make_service(tmp_path: Path) -> TemplateService:
    ids = iter(["new", "added"])

    return TemplateService(
        lambda: next(ids),
        lambda template_id: f"Template {template_id}",
        lambda macro_id, template_id: tmp_path / "templates" / macro_id / f"{template_id}.png",
    )


def test_apply_captured_template_replaces_step_ref_and_preserves_label(tmp_path: Path) -> None:
    step = {"type": "wait_image", "template": "old"}
    macro = Macro(meta=MacroMeta(id="macro"), templates={"old": TemplateInfo(label="Old label", match_mode="color")})
    old_file = tmp_path / "templates" / "macro" / "old.png"
    old_file.parent.mkdir(parents=True)
    old_file.write_bytes(b"old")
    service = make_service(tmp_path)

    service.apply_captured_template(macro, step, "old", "new", 320, 180)

    assert not old_file.exists()
    assert step["template"] == "new"
    assert "old" not in macro.templates
    assert macro.templates["new"].label == "Old label"
    assert macro.templates["new"].capture_width == 320
    assert macro.templates["new"].capture_height == 180
    assert macro.templates["new"].match_mode == "color"


def test_pick_template_copies_file_and_rewrites_any_image_branch(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    source.write_bytes(b"png")
    step = {"type": "if_any_image", "templates": ["old"], "branches": {"old": [{"type": "key"}]}}
    macro = Macro(meta=MacroMeta(id="macro"), templates={"old": TemplateInfo()})
    service = make_service(tmp_path)

    new_template_id = service.pick_template(macro, step, "old", str(source), 1024, 768)

    assert new_template_id == "new"
    assert (tmp_path / "templates" / "macro" / "new.png").read_bytes() == b"png"
    assert step["templates"] == ["new"]
    assert "new" in step["branches"]
    assert "old" not in step["branches"]
    assert macro.templates["new"].label == "Template new"


def test_pick_template_sets_default_match_mode_without_old_metadata(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    source.write_bytes(b"png")
    step = {"type": "wait_image", "template": "old"}
    macro = Macro(meta=MacroMeta(id="macro"), templates={"new": TemplateInfo(match_mode="")})
    service = make_service(tmp_path)

    assert service.pick_template(macro, step, "old", str(source), 1024, 768) == "new"
    assert macro.templates["new"].match_mode == "grayscale"


def test_pick_template_preserves_existing_match_mode_without_old_metadata(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    source.write_bytes(b"png")
    step = {"type": "wait_image", "template": "old"}
    macro = Macro(meta=MacroMeta(id="macro"), templates={"new": TemplateInfo(match_mode="color")})
    service = make_service(tmp_path)

    assert service.pick_template(macro, step, "old", str(source), 1024, 768) == "new"
    assert macro.templates["new"].match_mode == "color"


def test_delete_template_removes_files_metadata_and_step_refs(tmp_path: Path) -> None:
    steps = [
        {"type": "wait_image", "template": "button"},
        {"type": "if_any_image", "templates": ["button", "other"], "branches": {"button": []}},
    ]
    macro = Macro(meta=MacroMeta(id="macro"), templates={"button": TemplateInfo()})
    template_file = tmp_path / "templates" / "macro" / "button.png"
    template_file.parent.mkdir(parents=True)
    template_file.write_bytes(b"png")
    step_tree = StepTree(steps)
    service = make_service(tmp_path)

    service.delete_template(macro, step_tree, "button")

    assert not template_file.exists()
    assert "button" not in macro.templates
    assert step_tree.steps[0]["template"] == ""
    assert step_tree.steps[1]["templates"] == ["other"]
    assert "button" not in step_tree.steps[1]["branches"]


def test_delete_template_removes_empty_branches_after_pop(tmp_path: Path) -> None:
    step = {"type": "if_any_image", "templates": ["single"], "branches": {"single": [{"type": "key"}]}}
    macro = Macro(meta=MacroMeta(id="macro"), templates={"single": TemplateInfo()})
    template_file = tmp_path / "templates" / "macro" / "single.png"
    template_file.parent.mkdir(parents=True)
    template_file.write_bytes(b"png")
    step_tree = StepTree([step])
    service = make_service(tmp_path)

    service.delete_template(macro, step_tree, "single")

    assert "branches" not in step


def test_add_template_only_adds_to_if_any_image(tmp_path: Path) -> None:
    macro = Macro(meta=MacroMeta(id="macro"))
    service = make_service(tmp_path)
    step = {"type": "if_any_image", "templates": []}

    assert service.add_template(macro, step) is True
    assert step["templates"] == ["new"]
    assert "new" in macro.templates
    assert service.add_template(macro, {"type": "wait_image"}) is False


def test_add_template_uses_unique_id_when_provider_collides(tmp_path: Path) -> None:
    macro = Macro(meta=MacroMeta(id="macro"), templates={"123": TemplateInfo()})
    step = {"type": "if_any_image", "templates": ["123"], "branches": {"123": []}}
    service = TemplateService(
        lambda: "123",
        lambda template_id: f"Template {template_id}",
        lambda macro_id, template_id: tmp_path / "templates" / macro_id / f"{template_id}.png",
    )

    assert service.add_template(macro, step) is True

    assert step["templates"] == ["123", "124"]
    assert set(macro.templates) == {"123", "124"}


def test_update_template_meta_updates_valid_fields_and_rejects_invalid_values(tmp_path: Path) -> None:
    macro = Macro(meta=MacroMeta(id="macro"), templates={"button": TemplateInfo()})
    service = make_service(tmp_path)

    assert service.update_template_meta(macro, "button", "label", "Button") is True
    assert service.update_template_meta(macro, "button", "capture_width", "320") is True
    assert service.update_template_meta(macro, "button", "capture_height", "240") is True
    assert service.update_template_meta(macro, "button", "match_mode", "color") is True
    assert service.update_template_meta(macro, "button", "match_mode", "bad") is False
    assert service.update_template_meta(macro, "button", "capture_height", "bad") is False
    assert service.update_template_meta(macro, "missing", "label", "Missing") is False
    assert macro.templates["button"].label == "Button"
    assert macro.templates["button"].capture_width == 320
    assert macro.templates["button"].capture_height == 240
    assert macro.templates["button"].match_mode == "color"


def test_update_template_meta_rejects_unknown_field(tmp_path: Path) -> None:
    macro = Macro(meta=MacroMeta(id="macro"), templates={"button": TemplateInfo()})
    service = make_service(tmp_path)

    assert service.update_template_meta(macro, "button", "unknown", "value") is False


def test_pick_template_uses_screen_size_provider_when_capture_dims_omitted(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    source.write_bytes(b"png")
    step = {"type": "wait_image", "template": "old"}
    macro = Macro(meta=MacroMeta(id="macro"), templates={"old": TemplateInfo()})
    ids = iter(["new"])
    service = TemplateService(
        lambda: next(ids),
        lambda template_id: f"Template {template_id}",
        lambda macro_id, template_id: tmp_path / "templates" / macro_id / f"{template_id}.png",
        screen_size_provider=lambda: (3840, 2160),
    )

    service.pick_template(macro, step, "old", str(source))

    assert macro.templates["new"].capture_width == 3840
    assert macro.templates["new"].capture_height == 2160
