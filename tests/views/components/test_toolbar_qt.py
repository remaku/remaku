from PySide6.QtCore import Qt

from remaku.core.event_bus import event_bus
from remaku.views.components.toolbar import Toolbar


def test_toolbar_updates_run_button_for_running_state(qtbot) -> None:
    toolbar = Toolbar()
    qtbot.addWidget(toolbar)

    toolbar.handle_macro_running_changed(True)
    assert toolbar.run_button.text() == "Stop"

    toolbar.handle_macro_running_changed(False)
    assert toolbar.run_button.text() == "Run"


def test_toolbar_run_button_emits_action(qtbot) -> None:
    toolbar = Toolbar()
    qtbot.addWidget(toolbar)

    with qtbot.waitSignal(event_bus.action_triggered, timeout=100) as blocker:
        qtbot.mouseClick(toolbar.run_button, Qt.MouseButton.LeftButton)

    assert blocker.args == ["run"]


def test_toolbar_step_buttons_emit_actions(qtbot) -> None:
    toolbar = Toolbar()
    qtbot.addWidget(toolbar)

    buttons = [
        (toolbar.delete_button, "delete_step"),
        (toolbar.move_up_button, "move_up"),
        (toolbar.move_down_button, "move_down"),
        (toolbar.undo_button, "undo"),
        (toolbar.redo_button, "redo"),
    ]

    for button, action_id in buttons:
        with qtbot.waitSignal(event_bus.action_triggered, timeout=100) as blocker:
            qtbot.mouseClick(button, Qt.MouseButton.LeftButton)

        assert blocker.args == [action_id]


def test_toolbar_show_add_menu_routes_selected_step_type(monkeypatch, qtbot) -> None:
    toolbar = Toolbar()
    qtbot.addWidget(toolbar)

    def fake_show_step_menu(parent, button, callback) -> None:
        assert parent is toolbar
        assert button is toolbar.add_button
        callback("delay")

    monkeypatch.setattr("remaku.views.components.toolbar.show_step_menu", fake_show_step_menu)

    with qtbot.waitSignal(event_bus.step_add_requested, timeout=100) as blocker:
        toolbar.show_add_menu()

    assert blocker.args == ["delay"]


def test_toolbar_file_menu_contains_expected_actions(monkeypatch, qtbot) -> None:
    toolbar = Toolbar()
    qtbot.addWidget(toolbar)
    menus = []
    monkeypatch.setattr(toolbar, "popup_menu", lambda button, items: menus.append((button, items)))

    toolbar.show_file_menu()

    button, items = menus[0]
    action_ids = [item["id"] for item in items if "id" in item]
    shortcuts = {item["id"]: item.get("shortcut") for item in items if "id" in item}

    assert button is toolbar.file_menu_button
    assert action_ids == [
        "new_macro",
        "duplicate_macro",
        "import_macro",
        "export_macro",
        "open_macro_folder",
        "settings",
        "quit",
    ]
    assert shortcuts["new_macro"] == "Ctrl+N"
    assert shortcuts["settings"] == "Ctrl+,"


def test_toolbar_edit_and_help_menus_contain_expected_actions(monkeypatch, qtbot) -> None:
    toolbar = Toolbar()
    qtbot.addWidget(toolbar)
    menus = []
    monkeypatch.setattr(toolbar, "popup_menu", lambda button, items: menus.append((button, items)))

    toolbar.show_edit_menu()
    toolbar.show_help_menu()

    edit_ids = [item["id"] for item in menus[0][1] if "id" in item]
    help_ids = [item["id"] for item in menus[1][1] if "id" in item]

    assert edit_ids == [
        "undo",
        "redo",
        "cut",
        "copy",
        "paste",
        "add_step",
        "duplicate_step",
        "delete_step",
        "move_up",
        "move_down",
    ]
    assert help_ids == ["about", "support_author", "check_updates", "open_logs"]
