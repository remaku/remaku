from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from qfluentwidgets import ComboBox, LineEdit

from remaku.core.event_bus import event_bus
from remaku.models.macro_model import (
    DelayStep,
    GridNavStep,
    IfAnyImageStep,
    KeyStep,
    Macro,
    MacroMeta,
    RepeatStep,
    TemplateInfo,
    WaitImageStep,
)
from remaku.views.components import right_panel
from remaku.views.components.center_panel import CenterPanel
from remaku.views.components.left_panel import LeftPanel
from remaku.views.components.right_panel import RightPanel


def test_left_panel_sets_macro_list_and_emits_selection(qtbot) -> None:
    panel = LeftPanel()
    qtbot.addWidget(panel)

    with qtbot.waitSignal(event_bus.macro_selected, timeout=100) as blocker:
        panel.set_macro_list([("alpha", "Alpha"), ("beta", "Beta")], selected_macro_id="beta")

    assert blocker.args == ["beta"]
    assert panel.macro_list.count() == 2
    assert panel.macro_list.currentItem().text() == "Beta"
    assert panel.empty_label.isHidden()


def test_left_panel_shows_empty_state(qtbot) -> None:
    panel = LeftPanel()
    qtbot.addWidget(panel)

    panel.set_macro_list([])

    assert panel.macro_list.isHidden()
    assert not panel.empty_label.isHidden()


def test_left_panel_add_button_emits_new_macro_request(qtbot) -> None:
    panel = LeftPanel()
    qtbot.addWidget(panel)

    with qtbot.waitSignal(event_bus.new_macro_requested, timeout=100):
        qtbot.mouseClick(panel.new_macro_button, Qt.MouseButton.LeftButton)


def test_left_panel_selects_first_macro_when_selected_id_missing(qtbot) -> None:
    panel = LeftPanel()
    qtbot.addWidget(panel)

    with qtbot.waitSignal(event_bus.macro_selected, timeout=100) as blocker:
        panel.set_macro_list([("alpha", "Alpha"), ("beta", "Beta")], selected_macro_id="missing")

    assert blocker.args == ["alpha"]
    assert panel.macro_list.currentItem().text() == "Alpha"


def test_left_panel_context_actions_emit_current_macro_id(qtbot) -> None:
    panel = LeftPanel()
    qtbot.addWidget(panel)
    panel.set_macro_list([("alpha", "Alpha")])

    with qtbot.waitSignal(event_bus.macro_rename_requested, timeout=100) as rename:
        panel.handle_macro_rename()

    with qtbot.waitSignal(event_bus.macro_duplicate_requested, timeout=100) as duplicate:
        panel.handle_macro_duplicate()

    with qtbot.waitSignal(event_bus.macro_delete_requested, timeout=100) as delete:
        panel.handle_macro_delete()

    assert rename.args == ["alpha"]
    assert duplicate.args == ["alpha"]
    assert delete.args == ["alpha"]


def test_left_panel_order_change_emits_and_keeps_current_item(qtbot) -> None:
    panel = LeftPanel()
    qtbot.addWidget(panel)
    panel.set_macro_list([("alpha", "Alpha"), ("beta", "Beta")], selected_macro_id="beta")

    with qtbot.waitSignal(event_bus.macro_order_changed, timeout=100):
        panel.handle_order_changed()

    assert panel.macro_list.currentItem().data(Qt.ItemDataRole.UserRole) == "beta"


def test_center_panel_sets_step_tree_and_emits_selected_step(qtbot) -> None:
    panel = CenterPanel()
    qtbot.addWidget(panel)
    step = {"type": "key", "key": "enter"}

    with qtbot.waitSignal(event_bus.step_selected, timeout=100) as blocker:
        panel.set_step_tree([{"label": "Press enter", "step": step, "state_key": ("steps", 0)}], selected_step=step)

    assert blocker.args == [step]
    assert panel.step_list.topLevelItemCount() == 1
    assert panel.empty_label.isHidden()


def test_center_panel_branch_selection_emits_branch(qtbot) -> None:
    panel = CenterPanel()
    qtbot.addWidget(panel)
    parent_step = {"type": "if_image"}
    panel.set_step_tree(
        [
            {
                "label": "If image",
                "step": parent_step,
                "children": [{"label": "Then", "branch": (parent_step, "then"), "state_key": ("then", 0)}],
            }
        ]
    )
    root_item = panel.step_list.topLevelItem(0)
    assert root_item is not None
    branch_item = root_item.child(0)

    with qtbot.waitSignal(event_bus.branch_selected, timeout=100) as blocker:
        panel.step_list.setCurrentItem(branch_item)

    assert blocker.args == [parent_step, "then"]


def test_center_panel_clear_selection_emits_empty_selection(qtbot) -> None:
    panel = CenterPanel()
    qtbot.addWidget(panel)
    branches = []
    steps = []
    event_bus.branch_selected.connect(lambda parent, key: branches.append((parent, key)))
    event_bus.step_selected.connect(steps.append)

    panel.clear_selection()

    assert branches[-1] == (None, "")
    assert steps[-1] is None


def test_right_panel_commit_numeric_field_emits_valid_value(qtbot) -> None:
    panel = RightPanel()
    qtbot.addWidget(panel)
    field = LineEdit()
    field.setText(" 123 ")

    with qtbot.waitSignal(event_bus.step_property_changed, timeout=100) as blocker:
        panel.commit_numeric_field("ms", field)

    assert blocker.args == ["ms", "123"]
    assert not field.isError()


def test_right_panel_commit_numeric_field_marks_invalid_value(qtbot) -> None:
    panel = RightPanel()
    qtbot.addWidget(panel)
    field = LineEdit()
    field.setText("bad")

    panel.commit_numeric_field("ms", field)

    assert field.isError()


def test_right_panel_refresh_target_windows_preserves_unknown_selection(monkeypatch, qtbot) -> None:
    panel = RightPanel()
    qtbot.addWidget(panel)
    combo = ComboBox()
    qtbot.addWidget(combo)
    monkeypatch.setattr(right_panel.window, "list_visible_windows", lambda: ["Alpha", "Beta"])

    panel.refresh_target_windows(combo, "Missing")

    assert [combo.itemData(index) for index in range(combo.count())] == ["", "Alpha", "Beta", "Missing"]
    assert combo.currentData() == "Missing"


def test_right_panel_capture_key_normalizes_supported_key(monkeypatch, qtbot) -> None:
    panel = RightPanel()
    qtbot.addWidget(panel)
    edit = LineEdit()
    qtbot.addWidget(edit)
    monkeypatch.setattr(right_panel.pdi, "KEYBOARD_MAPPING", {"delete": object()})
    event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Delete, Qt.KeyboardModifier.NoModifier)

    with qtbot.waitSignal(event_bus.step_property_changed, timeout=100) as blocker:
        panel.capture_key(event, edit)

    assert edit.text() == "delete"
    assert blocker.args == ["key", "delete"]


def test_right_panel_capture_key_ignores_modifier_only_key(qtbot) -> None:
    panel = RightPanel()
    qtbot.addWidget(panel)
    edit = LineEdit()
    qtbot.addWidget(edit)
    event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Shift, Qt.KeyboardModifier.ShiftModifier)

    panel.capture_key(event, edit)

    assert edit.text() == ""


def test_right_panel_capture_hotkey_emits_normalized_combo(qtbot) -> None:
    panel = RightPanel()
    qtbot.addWidget(panel)
    edit = LineEdit()
    qtbot.addWidget(edit)
    event = QKeyEvent(
        QKeyEvent.Type.KeyPress,
        Qt.Key.Key_F1,
        Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier,
    )

    with qtbot.waitSignal(event_bus.macro_meta_changed, timeout=100) as blocker:
        panel.capture_hotkey(event, edit)

    assert edit.text() == "ctrl+alt+f1"
    assert blocker.args == ["hotkey", "ctrl+alt+f1"]


def test_right_panel_capture_hotkey_ignores_modifier_only_key(qtbot) -> None:
    panel = RightPanel()
    qtbot.addWidget(panel)
    edit = LineEdit()
    qtbot.addWidget(edit)
    event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Control, Qt.KeyboardModifier.ControlModifier)

    panel.capture_hotkey(event, edit)

    assert edit.text() == ""


def test_right_panel_show_macro_properties_renders_fields(monkeypatch, qtbot) -> None:
    panel = RightPanel()
    qtbot.addWidget(panel)
    monkeypatch.setattr(right_panel.window, "list_visible_windows", lambda: ["Game"])
    macro = Macro(meta=MacroMeta(target_window="Game", hotkey="ctrl+f1", enabled=True))

    panel.show_macro_properties(macro)

    line_edits = panel.findChildren(LineEdit)
    assert len(line_edits) == 1, "should have exactly the hotkey LineEdit"
    hotkey_edit = line_edits[0]
    assert hotkey_edit.text() == "ctrl+f1"


def test_right_panel_show_step_properties_for_common_step_types(monkeypatch, qtbot) -> None:
    panel = RightPanel()
    qtbot.addWidget(panel)
    macro = Macro(meta=MacroMeta(id="macro"), templates={"button": TemplateInfo(label="Button")})
    monkeypatch.setattr(right_panel, "TemplateEditor", lambda macro, template_id, parent=None: LineEdit(parent))

    for step in [
        KeyStep(key="enter"),
        DelayStep(ms=250),
        WaitImageStep(template="button", threshold=0.9),
        RepeatStep(count=3),
        IfAnyImageStep(templates=["button"]),
        GridNavStep(rows=2, start=1),
    ]:
        panel.show_step_properties(macro, "Step", step)
        assert panel.content_layout.count() > 0


def test_right_panel_note_input_emits_step_property(qtbot) -> None:
    panel = RightPanel()
    qtbot.addWidget(panel)
    panel.add_note_input("old")
    edit = panel.findChildren(LineEdit)[-1]
    edit.setText("new note")

    with qtbot.waitSignal(event_bus.step_property_changed, timeout=100) as blocker:
        edit.editingFinished.emit()

    assert blocker.args == ["note", "new note"]


def test_right_panel_dropdown_emits_current_data(qtbot) -> None:
    panel = RightPanel()
    qtbot.addWidget(panel)
    panel.add_dropdown("Mode", "stop", [("Stop", "stop"), ("Continue", "continue")], "on_timeout")
    combo = panel.findChildren(ComboBox)[-1]

    with qtbot.waitSignal(event_bus.step_property_changed, timeout=100) as blocker:
        combo.setCurrentIndex(1)

    assert blocker.args == ["on_timeout", "continue"]


def test_right_panel_slider_updates_label_and_emits_after_timer(monkeypatch, qtbot) -> None:
    panel = RightPanel()
    qtbot.addWidget(panel)
    starts = []

    class FakeTimer:
        def __init__(self, parent=None) -> None:
            self.timeout = event_bus.step_property_changed

        def setSingleShot(self, value: bool) -> None:
            pass

        def setInterval(self, value: int) -> None:
            pass

        def start(self) -> None:
            starts.append("start")

    monkeypatch.setattr(right_panel, "QTimer", FakeTimer)
    panel.add_slider("Threshold", 0.5, property_key="threshold")
    slider = panel.findChildren(right_panel.Slider)[-1]

    slider.setValue(75)

    assert starts == ["start"]


def test_right_panel_template_list_editor_add_button_emits(monkeypatch, qtbot) -> None:
    panel = RightPanel()
    qtbot.addWidget(panel)
    macro = Macro(meta=MacroMeta(id="macro"), templates={"button": TemplateInfo(label="Button")})
    monkeypatch.setattr(right_panel, "TemplateEditor", lambda macro, template_id, parent=None: LineEdit(parent))

    panel.add_template_list_editor(macro, ["button"])
    buttons = panel.findChildren(right_panel.PushButton)

    with qtbot.waitSignal(event_bus.template_add_requested, timeout=100):
        qtbot.mouseClick(buttons[-1], Qt.MouseButton.LeftButton)


def test_right_panel_enabled_checkbox_emits_macro_meta(qtbot) -> None:
    panel = RightPanel()
    qtbot.addWidget(panel)
    macro = Macro(meta=MacroMeta(enabled=False))
    panel.add_enabled_checkbox(macro)
    item = panel.content_layout.itemAt(panel.content_layout.count() - 1)
    assert item is not None
    checkbox = item.widget()
    assert checkbox is not None

    with qtbot.waitSignal(event_bus.macro_meta_changed, timeout=100) as blocker:
        qtbot.mouseClick(checkbox, Qt.MouseButton.LeftButton)

    assert blocker.args == ["enabled", "True"]
