from typing import Any, ClassVar, cast

from PySide6.QtCore import QModelIndex, QPointF, Qt
from PySide6.QtGui import QFocusEvent, QKeyEvent, QMouseEvent
from PySide6.QtWidgets import QWidget
from qfluentwidgets import BodyLabel, CheckBox, ComboBox, LineEdit, TextEdit

from remaku.core.event_bus import event_bus
from remaku.models.macro_model import (
    DelayStep,
    GridNavStep,
    IfAnyImageStep,
    KeyStep,
    Macro,
    MacroMeta,
    MouseClickStep,
    MouseMoveStep,
    MouseScrollStep,
    RepeatStep,
    TemplateInfo,
    WaitImageStep,
)
from remaku.views.components import center_panel, left_panel, right_panel
from remaku.views.components.center_panel import CenterPanel
from remaku.views.components.hotkey_edit import HotkeyEdit
from remaku.views.components.left_panel import LeftPanel
from remaku.views.components.right_panel import RightPanel


class FakeRoundMenu:
    instances: ClassVar[list["FakeRoundMenu"]] = []

    def __init__(self, parent) -> None:
        self.parent = parent
        self.actions = []
        self.separators = 0
        self.exec_position = None
        FakeRoundMenu.instances.append(self)

    def addAction(self, action) -> None:
        self.actions.append(action)

    def addSeparator(self) -> None:
        self.separators += 1

    def exec(self, position) -> None:
        self.exec_position = position


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


def test_left_panel_item_click_emits_macro_selection(qtbot) -> None:
    panel = LeftPanel()
    qtbot.addWidget(panel)
    panel.set_macro_list([("alpha", "Alpha")])
    item = panel.macro_list.item(0)

    with qtbot.waitSignal(event_bus.macro_selected, timeout=100) as blocker:
        panel.handle_item_clicked(item)

    assert blocker.args == ["alpha"]


def test_left_panel_handlers_ignore_missing_current_item(qtbot) -> None:
    panel = LeftPanel()
    qtbot.addWidget(panel)

    panel.emit_macro_selected(None)
    panel.handle_macro_rename()
    panel.handle_macro_duplicate()
    panel.handle_macro_delete()
    panel.handle_order_changed()

    assert panel.macro_list.currentItem() is None


def test_right_panel_clear_content_removes_widgets(qtbot) -> None:
    panel = RightPanel()
    qtbot.addWidget(panel)
    panel.content_layout.addWidget(QWidget(panel.content_widget))

    panel.clear_content()

    assert panel.content_layout.count() == 0


def test_right_panel_clear_content_ignores_empty_layout_item(qtbot) -> None:
    class FakeLayout:
        def __init__(self) -> None:
            self.items = [None]

        def count(self) -> int:
            return len(self.items)

        def takeAt(self, index: int):
            return self.items.pop(index)

    panel = RightPanel()
    qtbot.addWidget(panel)
    fake_layout = FakeLayout()
    cast(Any, panel).content_layout = fake_layout

    panel.clear_content()

    assert fake_layout.count() == 0


def test_left_panel_context_menu_ignores_empty_position(qtbot) -> None:
    panel = LeftPanel()
    qtbot.addWidget(panel)

    panel.handle_context_menu(panel.macro_list.rect().center())

    assert panel.macro_list.currentItem() is None


def test_left_panel_context_menu_builds_actions_and_emits(monkeypatch, qtbot) -> None:
    panel = LeftPanel()
    qtbot.addWidget(panel)
    panel.set_macro_list([("alpha", "Alpha")])
    FakeRoundMenu.instances.clear()
    monkeypatch.setattr(left_panel, "RoundMenu", FakeRoundMenu)
    item_rect = panel.macro_list.visualItemRect(panel.macro_list.item(0))

    panel.handle_context_menu(item_rect.center())

    menu = FakeRoundMenu.instances[0]
    assert menu.parent is panel.macro_list
    assert menu.exec_position is not None
    assert [action.text() for action in menu.actions] == ["Rename", "Duplicate", "Delete"]

    with qtbot.waitSignal(event_bus.macro_rename_requested, timeout=100) as rename:
        menu.actions[0].trigger()

    with qtbot.waitSignal(event_bus.macro_duplicate_requested, timeout=100) as duplicate:
        menu.actions[1].trigger()

    with qtbot.waitSignal(event_bus.macro_delete_requested, timeout=100) as delete:
        menu.actions[2].trigger()

    assert rename.args == ["alpha"]
    assert duplicate.args == ["alpha"]
    assert delete.args == ["alpha"]


def test_left_panel_context_actions_ignore_non_string_macro_id(qtbot) -> None:
    panel = LeftPanel()
    qtbot.addWidget(panel)
    panel.set_macro_list([("alpha", "Alpha")])
    item = panel.macro_list.currentItem()
    item.setData(Qt.ItemDataRole.UserRole, 123)

    panel.emit_macro_selected(item)
    panel.handle_macro_rename()
    panel.handle_macro_duplicate()
    panel.handle_macro_delete()

    assert item.data(Qt.ItemDataRole.UserRole) == 123


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


def test_center_panel_selects_branch_from_set_step_tree(qtbot) -> None:
    panel = CenterPanel()
    qtbot.addWidget(panel)
    parent_step = {"type": "repeat"}
    selected_branch = (parent_step, "body")

    with qtbot.waitSignal(event_bus.branch_selected, timeout=100) as blocker:
        panel.set_step_tree(
            [
                {
                    "label": "Repeat",
                    "step": parent_step,
                    "children": [{"label": "Body", "branch": selected_branch}],
                }
            ],
            selected_branch=selected_branch,
        )

    assert blocker.args == [parent_step, "body"]


def test_center_panel_preserves_collapsed_state_and_expands_selected_ancestor(qtbot) -> None:
    panel = CenterPanel()
    qtbot.addWidget(panel)
    parent_step = {"type": "repeat"}
    child_step = {"type": "delay"}
    items = [
        {
            "label": "Repeat",
            "step": parent_step,
            "state_key": "parent",
            "children": [{"label": "Delay", "step": child_step, "state_key": "child"}],
        }
    ]
    panel.set_step_tree(items)
    root_item = panel.step_list.topLevelItem(0)
    assert root_item is not None
    root_item.setExpanded(False)

    panel.set_step_tree(items)
    root_item = panel.step_list.topLevelItem(0)
    assert root_item is not None

    assert not root_item.isExpanded()

    panel.set_step_tree(items, selected_step=child_step)
    root_item = panel.step_list.topLevelItem(0)
    assert root_item is not None

    assert root_item.isExpanded()


def test_center_panel_refresh_tree_icons_reloads_existing_item_icons(monkeypatch, qtbot) -> None:
    panel = CenterPanel()
    qtbot.addWidget(panel)
    calls = []
    original_path = center_panel.RemakuIcon.path

    def fake_path(self, *args, **kwargs):
        calls.append(self)
        return original_path(self, *args, **kwargs)

    monkeypatch.setattr(center_panel.RemakuIcon, "path", fake_path)
    parent_step = {"type": "repeat"}

    panel.set_step_tree(
        [
            {
                "label": "Repeat",
                "step": parent_step,
                "children": [{"label": "Body", "branch": (parent_step, "steps")}],
            }
        ]
    )

    calls.clear()
    panel.refresh_tree_icons()

    assert calls == [center_panel.RemakuIcon.REPEAT, center_panel.RemakuIcon.CORNER_DOWN_RIGHT]


def test_center_panel_mouse_press_empty_area_clears_selection(qtbot) -> None:
    panel = CenterPanel()
    qtbot.addWidget(panel)
    steps = []
    event_bus.step_selected.connect(steps.append)
    panel.set_step_tree([{"label": "Press enter", "step": {"type": "key"}}])
    position = QPointF(1000, 1000)
    event = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        position,
        position,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )

    panel.step_list.mousePressEvent(event)

    assert panel.step_list.currentItem() is None
    assert steps[-1] is None


def test_center_panel_mouse_press_item_keeps_default_handling(qtbot) -> None:
    panel = CenterPanel()
    qtbot.addWidget(panel)
    panel.set_step_tree([{"label": "Press enter", "step": {"type": "key"}}])
    item = panel.step_list.topLevelItem(0)
    assert item is not None
    item_rect = panel.step_list.visualItemRect(item)
    position = QPointF(item_rect.center())
    event = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        position,
        position,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )

    panel.step_list.mousePressEvent(event)

    assert panel.step_list.currentIndex() != QModelIndex()


def test_center_panel_context_menu_ignores_branch_item(qtbot) -> None:
    panel = CenterPanel()
    qtbot.addWidget(panel)
    parent_step = {"type": "if_image"}
    panel.set_step_tree(
        [
            {
                "label": "If image",
                "step": parent_step,
                "children": [{"label": "Then", "branch": (parent_step, "then")}],
            }
        ]
    )
    root_item = panel.step_list.topLevelItem(0)
    assert root_item is not None
    branch_item = root_item.child(0)
    assert branch_item is not None
    branch_rect = panel.step_list.visualItemRect(branch_item)
    FakeRoundMenu.instances.clear()

    panel.handle_context_menu(branch_rect.center())

    assert FakeRoundMenu.instances == []


def test_center_panel_context_menu_builds_actions_and_emits(monkeypatch, qtbot) -> None:
    panel = CenterPanel()
    qtbot.addWidget(panel)
    step = {"type": "key"}
    panel.set_step_tree([{"label": "Press enter", "step": step}])
    panel.set_has_clipboard(True)
    FakeRoundMenu.instances.clear()
    monkeypatch.setattr(center_panel, "RoundMenu", FakeRoundMenu)
    item = panel.step_list.topLevelItem(0)
    assert item is not None
    panel.step_list.setCurrentItem(item)
    rect = panel.step_list.visualItemRect(item)

    panel.handle_context_menu(rect.center())

    menu = FakeRoundMenu.instances[0]
    assert menu.parent is panel
    assert menu.separators == 2
    assert menu.exec_position is not None
    assert [action.text() for action in menu.actions] == [
        "Copy",
        "Cut",
        "Paste",
        "Duplicate Step",
        "Delete Step",
        "Wrap in Repeat",
    ]
    assert all(action.isEnabled() for action in menu.actions)

    expected_actions = ["copy", "cut", "paste", "duplicate_step", "delete_step", "wrap_in_repeat"]

    for action, expected in zip(menu.actions, expected_actions, strict=True):
        with qtbot.waitSignal(event_bus.action_triggered, timeout=100) as blocker:
            action.trigger()

        assert blocker.args == [expected]


def test_center_panel_context_menu_disables_selection_actions_without_selection(monkeypatch, qtbot) -> None:
    panel = CenterPanel()
    qtbot.addWidget(panel)
    panel.set_step_tree([{"label": "Press enter", "step": {"type": "key"}}])
    FakeRoundMenu.instances.clear()
    monkeypatch.setattr(center_panel, "RoundMenu", FakeRoundMenu)
    item = panel.step_list.topLevelItem(0)
    assert item is not None
    rect = panel.step_list.visualItemRect(item)
    panel.step_list.clearSelection()

    panel.handle_context_menu(rect.center())

    menu = FakeRoundMenu.instances[0]
    assert [action.isEnabled() for action in menu.actions] == [False, False, False, False, False, False]


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


def test_right_panel_commit_numeric_field_marks_empty_value(qtbot) -> None:
    panel = RightPanel()
    qtbot.addWidget(panel)
    field = LineEdit()
    field.setText("   ")

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


def test_right_panel_refresh_target_windows_selects_foreground_default(monkeypatch, qtbot) -> None:
    panel = RightPanel()
    qtbot.addWidget(panel)
    combo = ComboBox()
    qtbot.addWidget(combo)
    monkeypatch.setattr(right_panel.window, "list_visible_windows", lambda: ["Alpha"])

    panel.refresh_target_windows(combo, "")

    assert combo.currentData() == ""


def test_right_panel_capture_key_normalizes_supported_key(monkeypatch, qtbot) -> None:
    panel = RightPanel()
    qtbot.addWidget(panel)
    edit = LineEdit()
    qtbot.addWidget(edit)
    monkeypatch.setattr(right_panel.keys, "is_valid_key", lambda key: key == "delete")
    event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Delete, Qt.KeyboardModifier.NoModifier)

    with qtbot.waitSignal(event_bus.step_property_changed, timeout=100) as blocker:
        panel.capture_key(event, edit)

    assert edit.text() == "delete"
    assert blocker.args == ["key", "delete"]


def test_right_panel_capture_key_includes_modifier_keys(monkeypatch, qtbot) -> None:
    panel = RightPanel()
    qtbot.addWidget(panel)
    edit = LineEdit()
    qtbot.addWidget(edit)
    monkeypatch.setattr(right_panel.keys, "is_valid_key", lambda key: key == "ctrl+shift+s")
    event = QKeyEvent(
        QKeyEvent.Type.KeyPress,
        Qt.Key.Key_S,
        Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier,
    )

    with qtbot.waitSignal(event_bus.step_property_changed, timeout=100) as blocker:
        panel.capture_key(event, edit)

    assert edit.text() == "ctrl+shift+s"
    assert blocker.args == ["key", "ctrl+shift+s"]


def test_right_panel_capture_key_includes_alt_and_win_modifiers(monkeypatch, qtbot) -> None:
    panel = RightPanel()
    qtbot.addWidget(panel)
    edit = LineEdit()
    qtbot.addWidget(edit)
    monkeypatch.setattr(right_panel.keys, "is_valid_key", lambda key: key == "alt+win+a")
    event = QKeyEvent(
        QKeyEvent.Type.KeyPress,
        Qt.Key.Key_A,
        Qt.KeyboardModifier.AltModifier | Qt.KeyboardModifier.MetaModifier,
    )

    with qtbot.waitSignal(event_bus.step_property_changed, timeout=100) as blocker:
        panel.capture_key(event, edit)

    assert edit.text() == "alt+win+a"
    assert blocker.args == ["key", "alt+win+a"]


def test_right_panel_capture_key_ignores_modifier_only_key(qtbot) -> None:
    panel = RightPanel()
    qtbot.addWidget(panel)
    edit = LineEdit()
    qtbot.addWidget(edit)
    event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Shift, Qt.KeyboardModifier.ShiftModifier)

    panel.capture_key(event, edit)

    assert edit.text() == ""


def test_right_panel_capture_hotkey_emits_normalized_combo(qtbot) -> None:
    edit = HotkeyEdit()
    qtbot.addWidget(edit)
    edit.textChanged.connect(lambda text: event_bus.macro_meta_changed.emit("hotkey", text))
    event = QKeyEvent(
        QKeyEvent.Type.KeyPress,
        Qt.Key.Key_F1,
        Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier,
    )

    with qtbot.waitSignal(event_bus.macro_meta_changed, timeout=100) as blocker:
        edit.keyPressEvent(event)

    assert edit.text() == "ctrl+alt+f1"
    assert blocker.args == ["hotkey", "ctrl+alt+f1"]


def test_right_panel_capture_hotkey_includes_shift_modifier(qtbot) -> None:
    edit = HotkeyEdit()
    qtbot.addWidget(edit)
    edit.textChanged.connect(lambda text: event_bus.macro_meta_changed.emit("hotkey", text))
    event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_F2, Qt.KeyboardModifier.ShiftModifier)

    with qtbot.waitSignal(event_bus.macro_meta_changed, timeout=100) as blocker:
        edit.keyPressEvent(event)

    assert edit.text() == "shift+f2"
    assert blocker.args == ["hotkey", "shift+f2"]


def test_right_panel_capture_hotkey_ignores_modifier_only_key(qtbot) -> None:
    edit = HotkeyEdit()
    qtbot.addWidget(edit)
    event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Control, Qt.KeyboardModifier.ControlModifier)

    edit.keyPressEvent(event)

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


def test_right_panel_macro_option_hints_have_tooltips(monkeypatch, qtbot) -> None:
    panel = RightPanel()
    qtbot.addWidget(panel)
    monkeypatch.setattr(right_panel.window, "list_visible_windows", lambda: ["Game"])

    panel.show_macro_properties(Macro())

    info_icons = [icon for icon in panel.findChildren(right_panel.IconWidget) if icon.toolTip()]
    tooltips = [icon.toolTip() for icon in info_icons]

    assert len(tooltips) == 3
    assert all(tooltips)
    assert all(icon.toolTipDuration() == -1 for icon in info_icons)


def test_right_panel_show_step_properties_for_common_step_types(monkeypatch, qtbot) -> None:
    panel = RightPanel()
    qtbot.addWidget(panel)
    macro = Macro(meta=MacroMeta(id="macro"), templates={"button": TemplateInfo(label="Button")})
    monkeypatch.setattr(right_panel, "TemplateEditor", lambda macro, template_id, parent=None: LineEdit(parent))

    for step in [
        KeyStep(key="enter"),
        DelayStep(ms=250),
        right_panel.TextInputStep(text="hello", interval_ms=25),
        WaitImageStep(template="button", threshold=0.9),
        RepeatStep(count=3),
        IfAnyImageStep(templates=["button"]),
        GridNavStep(rows=2, start=1),
        MouseClickStep(x=10, y=20),
        MouseClickStep(target="template", template="button", threshold=0.9),
        MouseMoveStep(x=30, y=40),
        MouseMoveStep(target="template", template="button", threshold=0.8),
        MouseScrollStep(clicks=-3, interval_ms=25),
    ]:
        panel.show_step_properties(macro, "Step", step)
        assert panel.content_layout.count() > 0


def test_right_panel_show_step_properties_ignores_unknown_step_type(qtbot) -> None:
    panel = RightPanel()
    qtbot.addWidget(panel)
    macro = Macro(meta=MacroMeta(id="macro"))
    unknown_step = cast(Any, object())

    panel.show_step_properties(macro, "Step", unknown_step)

    assert panel.content_layout.count() == 0


def test_base_step_properties_widget_requires_fields(qtbot) -> None:
    try:
        right_panel.StepPropertiesWidget.add_step_fields(cast(Any, object()))
    except NotImplementedError:
        pass
    else:
        raise AssertionError("base StepPropertiesWidget should require add_step_fields")


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


def test_right_panel_slider_updates_label_and_emits_after_timer(qtbot) -> None:
    panel = RightPanel()
    qtbot.addWidget(panel)
    panel.add_slider("Threshold", 0.5, property_key="threshold")
    slider = panel.findChildren(right_panel.Slider)[-1]

    with qtbot.waitSignal(event_bus.step_property_changed, timeout=500) as blocker:
        slider.setValue(75)

    assert blocker.args == ["threshold", "75"]


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


def test_right_panel_gaming_mode_checkbox_emits_macro_meta(qtbot) -> None:
    panel = RightPanel()
    qtbot.addWidget(panel)
    macro = Macro(gaming_mode=False)
    panel.add_gaming_mode_checkbox(macro)
    item = panel.content_layout.itemAt(panel.content_layout.count() - 1)
    assert item is not None
    row = item.widget()
    assert row is not None
    checkbox = row.findChild(CheckBox)
    assert checkbox is not None

    with qtbot.waitSignal(event_bus.macro_meta_changed, timeout=100) as blocker:
        qtbot.mouseClick(checkbox, Qt.MouseButton.LeftButton)

    assert blocker.args == ["gaming_mode", "True"]


def test_right_panel_background_input_checkbox_emits_macro_meta(qtbot) -> None:
    panel = RightPanel()
    qtbot.addWidget(panel)
    macro = Macro(background_input=False)
    panel.add_background_input_checkbox(macro)
    item = panel.content_layout.itemAt(panel.content_layout.count() - 1)
    assert item is not None
    row = item.widget()
    assert row is not None
    checkbox = row.findChild(CheckBox)
    assert checkbox is not None

    with qtbot.waitSignal(event_bus.macro_meta_changed, timeout=100) as blocker:
        qtbot.mouseClick(checkbox, Qt.MouseButton.LeftButton)

    assert blocker.args == ["background_input", "True"]


def test_right_panel_keep_target_focused_checkbox_emits_macro_meta(qtbot) -> None:
    panel = RightPanel()
    qtbot.addWidget(panel)
    macro = Macro(keep_target_focused=False)
    panel.add_keep_target_focused_checkbox(macro)
    item = panel.content_layout.itemAt(panel.content_layout.count() - 1)
    assert item is not None
    row = item.widget()
    assert row is not None
    checkbox = row.findChild(CheckBox)
    assert checkbox is not None

    with qtbot.waitSignal(event_bus.macro_meta_changed, timeout=100) as blocker:
        qtbot.mouseClick(checkbox, Qt.MouseButton.LeftButton)

    assert blocker.args == ["keep_target_focused", "True"]


def test_right_panel_show_step_properties_for_remaining_step_types(monkeypatch, qtbot) -> None:
    panel = RightPanel()
    qtbot.addWidget(panel)
    macro = Macro(meta=MacroMeta(id="macro"), templates={"button": TemplateInfo(label="Button")})
    monkeypatch.setattr(right_panel, "TemplateEditor", lambda macro, template_id, parent=None: LineEdit(parent))

    for step in [
        right_panel.HoldKeyUntilGoneStep(template="button"),
        right_panel.IfImageStep(template="button"),
    ]:
        panel.show_step_properties(macro, "Step", step)
        assert panel.content_layout.count() > 0


def test_right_panel_show_branch_properties_add_button_emits(monkeypatch, qtbot) -> None:
    panel = RightPanel()
    qtbot.addWidget(panel)
    calls = []
    monkeypatch.setattr(
        right_panel,
        "show_step_menu",
        lambda parent, button, callback: calls.append((parent, button)) or callback("delay"),
    )
    macro = Macro(meta=MacroMeta(id="macro"))

    panel.show_branch_properties(macro, "Parent Step", "Then", [])
    button = panel.findChildren(right_panel.PushButton)[-1]

    with qtbot.waitSignal(event_bus.step_add_requested, timeout=100) as blocker:
        qtbot.mouseClick(button, Qt.MouseButton.LeftButton)

    assert calls == [(panel, button)]
    assert blocker.args == ["delay"]


def test_right_panel_handle_add_step_requested_emits(qtbot) -> None:
    panel = RightPanel()
    qtbot.addWidget(panel)

    with qtbot.waitSignal(event_bus.step_add_requested, timeout=100) as blocker:
        panel.handle_add_step_requested("key")

    assert blocker.args == ["key"]


def test_right_panel_non_numeric_text_input_emits_on_editing_finished(qtbot) -> None:
    panel = RightPanel()
    qtbot.addWidget(panel)
    panel.add_text_input("Mode", "old", "on_timeout")
    field = panel.findChildren(LineEdit)[-1]
    field.setText("continue")

    with qtbot.waitSignal(event_bus.step_property_changed, timeout=100) as blocker:
        field.editingFinished.emit()

    assert blocker.args == ["on_timeout", "continue"]


def test_right_panel_multiline_text_input_emits_on_focus_out(qtbot) -> None:
    panel = RightPanel()
    qtbot.addWidget(panel)
    panel.add_multiline_text_input("Text", "old", "text")
    field = panel.findChildren(TextEdit)[-1]
    field.setPlainText("哈囉\nworld")

    with qtbot.waitSignal(event_bus.step_property_changed, timeout=100) as blocker:
        field.focusOutEvent(QFocusEvent(QFocusEvent.Type.FocusOut))

    assert blocker.args == ["text", "哈囉\nworld"]


def test_right_panel_hotkey_text_clear_emits_empty_value(qtbot) -> None:
    panel = RightPanel()
    qtbot.addWidget(panel)
    macro = Macro(meta=MacroMeta(hotkey="ctrl+f1"))
    panel.add_hotkey_text_input(macro)
    edit = panel.findChildren(LineEdit)[-1]

    with qtbot.waitSignal(event_bus.macro_meta_changed, timeout=100) as blocker:
        edit.setText("")

    assert blocker.args == ["hotkey", ""]


def test_right_panel_capture_key_ignores_unsupported_key(monkeypatch, qtbot) -> None:
    panel = RightPanel()
    qtbot.addWidget(panel)
    edit = LineEdit()
    qtbot.addWidget(edit)
    monkeypatch.setattr(right_panel.keys, "is_valid_key", lambda key: False)
    event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_A, Qt.KeyboardModifier.NoModifier)

    panel.capture_key(event, edit)

    assert edit.text() == ""


def test_right_panel_template_card_toggles_visibility(monkeypatch, qtbot) -> None:
    panel = RightPanel()
    qtbot.addWidget(panel)
    macro = Macro(meta=MacroMeta(id="macro"), templates={"button": TemplateInfo(label="Button")})
    monkeypatch.setattr(right_panel, "TemplateEditor", lambda macro, template_id, parent=None: LineEdit(parent))

    panel.add_template_card(macro, "button")
    panel.show()
    qtbot.waitExposed(panel)
    trigger_item = panel.content_layout.itemAt(panel.content_layout.count() - 2)
    card_item = panel.content_layout.itemAt(panel.content_layout.count() - 1)
    assert trigger_item is not None
    assert card_item is not None
    trigger = trigger_item.widget()
    card = card_item.widget()
    assert trigger is not None
    assert card is not None
    assert not card.isVisible()

    cast(Any, trigger).mousePressEvent(None)
    assert not card.isHidden()

    cast(Any, trigger).mousePressEvent(None)
    assert card.isHidden()


def test_right_panel_template_card_uses_template_id_when_label_missing(monkeypatch, qtbot) -> None:
    panel = RightPanel()
    qtbot.addWidget(panel)
    macro = Macro(meta=MacroMeta(id="macro"), templates={})
    monkeypatch.setattr(right_panel, "TemplateEditor", lambda macro, template_id, parent=None: LineEdit(parent))

    panel.add_template_card(macro, "missing")
    labels = panel.findChildren(BodyLabel)

    assert any(label.text() == "missing" for label in labels)
