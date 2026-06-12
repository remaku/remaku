from PySide6.QtCore import Qt

from remaku.core.event_bus import event_bus
from remaku.models.macro_model import Macro, MacroMeta, TemplateInfo
from remaku.views.components import template_editor
from remaku.views.components.template_editor import TemplateEditor


def make_macro() -> Macro:
    return Macro(
        meta=MacroMeta(id="macro"),
        templates={"button": TemplateInfo(label="Button", capture_width=320, capture_height=180)},
    )


def test_template_editor_shows_metadata_and_missing_preview(monkeypatch, qtbot) -> None:
    monkeypatch.setattr(template_editor, "template_path", lambda macro_id, template_id: "missing.png")

    editor = TemplateEditor(make_macro(), "button")
    qtbot.addWidget(editor)

    assert editor.template_label == "Button"
    assert editor.capture_width == 320
    assert editor.capture_height == 180
    assert editor.preview_label is not None
    assert editor.preview_label.text() == "No template available"


def test_template_editor_label_edit_emits_template_meta(monkeypatch, qtbot) -> None:
    monkeypatch.setattr(template_editor, "template_path", lambda macro_id, template_id: "missing.png")
    editor = TemplateEditor(make_macro(), "button")
    qtbot.addWidget(editor)
    label_edit = editor.findChildren(template_editor.LineEdit)[0]
    label_edit.setText("New Label")

    with qtbot.waitSignal(event_bus.template_meta_changed, timeout=100) as blocker:
        label_edit.editingFinished.emit()

    assert blocker.args == ["button", "label", "New Label"]


def test_template_editor_action_buttons_emit_template_events(monkeypatch, qtbot) -> None:
    monkeypatch.setattr(template_editor, "template_path", lambda macro_id, template_id: "missing.png")
    editor = TemplateEditor(make_macro(), "button")
    qtbot.addWidget(editor)
    buttons = editor.findChildren(template_editor.PushButton)

    with qtbot.waitSignal(event_bus.template_capture_requested, timeout=100) as capture_blocker:
        qtbot.mouseClick(buttons[0], Qt.MouseButton.LeftButton)

    with qtbot.waitSignal(event_bus.template_pick_requested, timeout=100) as pick_blocker:
        qtbot.mouseClick(buttons[1], Qt.MouseButton.LeftButton)

    with qtbot.waitSignal(event_bus.template_delete_requested, timeout=100) as delete_blocker:
        qtbot.mouseClick(buttons[2], Qt.MouseButton.LeftButton)

    assert capture_blocker.args == ["button"]
    assert pick_blocker.args == ["button"]
    assert delete_blocker.args == ["button"]


def test_template_editor_update_preview_returns_without_label(monkeypatch, qtbot) -> None:
    monkeypatch.setattr(template_editor, "template_path", lambda macro_id, template_id: "missing.png")
    editor = TemplateEditor(make_macro(), "button")
    qtbot.addWidget(editor)
    editor.preview_label = None

    editor.update_preview()

    assert editor.preview_label is None


def test_template_editor_update_preview_displays_pixmap(monkeypatch, qtbot) -> None:
    monkeypatch.setattr(template_editor, "template_path", lambda macro_id, template_id: "missing.png")
    editor = TemplateEditor(make_macro(), "button")
    qtbot.addWidget(editor)

    assert editor.original_pixmap is not None, "should keep an empty pixmap when preview image is missing"
    assert editor.original_pixmap.isNull(), "missing preview image should be represented by a null pixmap"
    assert editor.preview_label is not None, "preview label should remain available after preview refresh"
    assert editor.preview_label.text() == "No template available", "preview label should explain that no image exists"


def test_template_editor_capture_size_inputs_emit_meta_changes(monkeypatch, qtbot) -> None:
    monkeypatch.setattr(template_editor, "template_path", lambda macro_id, template_id: "missing.png")
    editor = TemplateEditor(make_macro(), "button")
    qtbot.addWidget(editor)
    line_edits = editor.findChildren(template_editor.LineEdit)
    assert len(line_edits) >= 3, "should have label, capture_width, and capture_height fields"

    width_edit = next((edit for edit in line_edits if edit.text() == "320"), None)
    assert width_edit is not None
    width_edit.setText("640")

    with qtbot.waitSignal(event_bus.template_meta_changed, timeout=100) as blocker:
        width_edit.editingFinished.emit()

    assert blocker.args == ["button", "capture_width", "640"]


def test_template_editor_handles_template_without_info(monkeypatch, qtbot) -> None:
    macro = Macro(meta=MacroMeta(id="macro"), templates={})
    monkeypatch.setattr(template_editor, "template_path", lambda macro_id, template_id: "missing.png")

    editor = TemplateEditor(macro, "missing")
    qtbot.addWidget(editor)

    assert editor.template_label == ""
    assert editor.capture_width == 0
    assert editor.capture_height == 0
    assert editor.preview_label is not None
    assert editor.preview_label.text() == "No template available"
