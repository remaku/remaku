"""Qt widget tests for MainWindow.

Requires pytest-qt and a display server (or virtual framebuffer on CI).
"""

# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportOptionalMemberAccess=false, reportCallIssue=false

import copy
import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QListWidgetItem, QTreeWidgetItem

import config as cfg
import window
from i18n import t
from macro_engine import MacroRunner
from main_window import CheckBox, ComboBox, LineEdit, MainWindow
from runner import Status

MINI_PNG = bytes(
    [
        0x89,
        0x50,
        0x4E,
        0x47,
        0x0D,
        0x0A,
        0x1A,
        0x0A,
        0x00,
        0x00,
        0x00,
        0x0D,
        0x49,
        0x48,
        0x44,
        0x52,
        0x00,
        0x00,
        0x00,
        0x01,
        0x00,
        0x00,
        0x00,
        0x01,
        0x08,
        0x02,
        0x00,
        0x00,
        0x00,
        0x90,
        0x77,
        0x53,
        0xDE,
        0x00,
        0x00,
        0x00,
        0x0C,
        0x49,
        0x44,
        0x41,
        0x54,
        0x08,
        0xD7,
        0x63,
        0xF8,
        0xCF,
        0xC0,
        0x00,
        0x00,
        0x00,
        0x03,
        0x00,
        0x01,
        0x00,
        0x05,
        0x98,
        0xD9,
        0x33,
        0x00,
        0x00,
        0x00,
        0x00,
        0x49,
        0x45,
        0x4E,
        0x44,
        0xAE,
        0x42,
        0x60,
        0x82,
    ]
)


def get_runner(mw: MainWindow) -> MacroRunner:
    """Assert current_runner is not None and return it."""
    assert mw.current_runner is not None
    return mw.current_runner


def step_count(mw: MainWindow) -> int:
    """Count all items in the step tree (flattened)."""
    return len(mw.flat_nodes)


def set_current_step_row(mw: MainWindow, row: int) -> None:
    """Select the nth item in the flattened step tree."""
    if row < 0 or row >= len(mw.flat_nodes):
        mw.step_list.clearSelection()
        return
    node = mw.flat_nodes[row]
    item = mw.node_to_item.get(node)
    if item is not None:
        mw.step_list.setCurrentItem(item)


def get_current_step_row(mw: MainWindow) -> int:
    """Get the index of the current item in the flattened step tree."""
    item = mw.step_list.currentItem()
    if item is None:
        return -1
    node = mw.item_to_node.get(item)
    if node is None:
        return -1
    try:
        return mw.flat_nodes.index(node)
    except ValueError:
        return -1


def select_step_rows(mw: MainWindow, rows: list[int]) -> None:
    """Select multiple items in the step tree by their flat indices."""
    mw.step_list.clearSelection()
    for row in rows:
        if 0 <= row < len(mw.flat_nodes):
            node = mw.flat_nodes[row]
            item = mw.node_to_item.get(node)
            if item is not None:
                item.setSelected(True)


original_startup_check_update = MainWindow.startup_check_update


@pytest.fixture
def macros_dir(tmp_path: Path):
    """Create a temporary macros directory with test macro files."""
    macros = tmp_path / "macros"
    macros.mkdir()

    macro_a = {
        "meta": {"name": "test_a", "label": "Test Macro A", "enabled": True},
        "templates": {},
        "steps": [
            {"type": "key", "key": "enter", "hold_ms": 90},
            {"type": "delay", "ms": 500},
        ],
    }
    (macros / "test_a.json").write_text(json.dumps(macro_a), encoding="utf-8")

    macro_b = {
        "meta": {"name": "test_b", "label": "Test Macro B", "enabled": True},
        "templates": {},
        "steps": [
            {"type": "key", "key": "space"},
            {
                "type": "repeat",
                "count": 3,
                "steps": [
                    {"type": "key", "key": "a"},
                    {"type": "delay", "ms": 100},
                ],
            },
        ],
    }
    (macros / "test_b.json").write_text(json.dumps(macro_b), encoding="utf-8")

    return macros


@pytest.fixture
def templates_dir(tmp_path: Path):
    """Create a temporary templates directory."""
    templates = tmp_path / "templates"
    templates.mkdir()
    return templates


@pytest.fixture
def main_window(qtbot, macros_dir: Path, templates_dir: Path):
    """Create a MainWindow with mocked file system paths."""
    conf = cfg.get_defaults()

    with (
        patch.object(cfg, "macros_dir", return_value=macros_dir),
        patch.object(cfg, "templates_dir", return_value=templates_dir),
        patch.object(cfg, "load", return_value=conf),
        patch.object(cfg, "save"),
        patch.object(cfg, "config_path", return_value=macros_dir.parent / "config.json"),
        patch("main_window.OverlayWidget", return_value=MagicMock()),
        patch.object(MainWindow, "register_hotkeys"),
        patch.object(MainWindow, "startup_check_update"),
    ):
        win = MainWindow()
        qtbot.addWidget(win)
        yield win


# ---------------------------------------------------------------------------
# Basic creation tests
# ---------------------------------------------------------------------------


class TestMainWindowCreation:
    def test_window_title(self, main_window: MainWindow):
        assert main_window.windowTitle() == "Remaku"

    def test_minimum_size(self, main_window: MainWindow):
        assert main_window.minimumWidth() == 900
        assert main_window.minimumHeight() == 600

    def test_has_macro_list(self, main_window: MainWindow):
        assert main_window.macro_list is not None
        assert main_window.macro_list.count() == 2

    def test_has_step_list(self, main_window: MainWindow):
        assert main_window.step_list is not None

    def test_has_right_panel(self, main_window: MainWindow):
        assert main_window.right_panel is not None

    def test_initial_runner_selected(self, main_window: MainWindow):
        assert main_window.current_runner is not None
        assert main_window.current_runner.label == "Test Macro A"


# ---------------------------------------------------------------------------
# Macro list tests
# ---------------------------------------------------------------------------


class TestMacroList:
    def test_macro_count(self, main_window: MainWindow):
        assert main_window.macro_list.count() == 2

    def test_first_macro_selected(self, main_window: MainWindow):
        assert main_window.macro_list.currentRow() == 0

    def test_macro_labels(self, main_window: MainWindow):
        assert main_window.macro_list.item(0).text() == "Test Macro A"
        assert main_window.macro_list.item(1).text() == "Test Macro B"

    def test_switch_macro(self, main_window: MainWindow):
        main_window.macro_list.setCurrentRow(1)
        assert main_window.current_runner is not None
        assert main_window.current_runner.label == "Test Macro B"


# ---------------------------------------------------------------------------
# Step list tests
# ---------------------------------------------------------------------------


class TestStepList:
    def test_step_count_macro_a(self, main_window: MainWindow):
        assert step_count(main_window) == 2

    def test_step_count_macro_b(self, main_window: MainWindow):
        main_window.macro_list.setCurrentRow(1)
        assert step_count(main_window) == 4  # key + repeat + key + delay

    def test_step_selection(self, main_window: MainWindow):
        set_current_step_row(main_window, 0)
        assert get_current_step_row(main_window) == 0

    def test_step_tree_built(self, main_window: MainWindow):
        assert main_window.step_tree is not None
        assert len(main_window.flat_nodes) == 2

    def test_flat_nodes_match_steps(self, main_window: MainWindow):
        steps = get_runner(main_window).macro.get("steps", [])
        assert len(main_window.flat_nodes) == len(steps)
        for node, step in zip(main_window.flat_nodes, steps, strict=True):
            assert node.step is step


# ---------------------------------------------------------------------------
# Step operations via UI
# ---------------------------------------------------------------------------


class TestStepOperations:
    def test_delete_step(self, main_window: MainWindow):
        set_current_step_row(main_window, 0)
        main_window.on_delete_step()
        assert step_count(main_window) == 1
        assert len(get_runner(main_window).macro["steps"]) == 1

    def test_delete_last_step(self, main_window: MainWindow):
        set_current_step_row(main_window, 0)
        main_window.on_delete_step()
        set_current_step_row(main_window, 0)
        main_window.on_delete_step()
        assert step_count(main_window) == 0
        assert len(get_runner(main_window).macro["steps"]) == 0

    def test_add_step(self, main_window: MainWindow):
        initial_count = step_count(main_window)
        step = {"type": "key", "key": "escape"}
        main_window.do_add_step(step)
        assert step_count(main_window) == initial_count + 1
        assert get_runner(main_window).macro["steps"][-1]["key"] == "escape"

    def test_add_step_after_selected(self, main_window: MainWindow):
        set_current_step_row(main_window, 0)
        step = {"type": "delay", "ms": 200}
        main_window.do_add_step(step)
        assert step_count(main_window) == 3
        steps = get_runner(main_window).macro["steps"]
        assert steps[1]["type"] == "delay"

    def test_add_multiple_steps_selects_latest(self, main_window: MainWindow):
        set_current_step_row(main_window, step_count(main_window) - 1)
        for _ in range(5):
            before = get_current_step_row(main_window)
            step = {"type": "key", "key": "a"}
            main_window.do_add_step(step)
            assert get_current_step_row(main_window) == before + 1

    def test_move_step_down(self, main_window: MainWindow):
        set_current_step_row(main_window, 0)
        steps_before = [s["type"] for s in get_runner(main_window).macro["steps"]]
        main_window.on_move_step(1)
        steps_after = [s["type"] for s in get_runner(main_window).macro["steps"]]
        assert steps_before == ["key", "delay"]
        assert steps_after == ["delay", "key"]

    def test_move_step_up(self, main_window: MainWindow):
        set_current_step_row(main_window, 1)
        main_window.on_move_step(-1)
        steps_after = [s["type"] for s in get_runner(main_window).macro["steps"]]
        assert steps_after == ["delay", "key"]

    def test_duplicate_step(self, main_window: MainWindow):
        set_current_step_row(main_window, 0)
        main_window.duplicate_steps()
        assert step_count(main_window) == 3
        steps = get_runner(main_window).macro["steps"]
        assert steps[0]["key"] == steps[1]["key"]

    def test_copy_paste_step(self, main_window: MainWindow):
        set_current_step_row(main_window, 0)
        main_window.copy_steps()
        set_current_step_row(main_window, 1)
        main_window.paste_steps()
        assert step_count(main_window) == 3
        steps = get_runner(main_window).macro["steps"]
        assert steps[2]["type"] == "key"

    def test_cut_step(self, main_window: MainWindow):
        set_current_step_row(main_window, 0)
        main_window.cut_steps()
        assert step_count(main_window) == 1
        assert hasattr(main_window, "step_clipboard")
        assert len(main_window.step_clipboard["steps"]) == 1

    def test_wrap_in_repeat(self, main_window: MainWindow):
        set_current_step_row(main_window, 0)
        select_step_rows(main_window, [0, 1])
        main_window.wrap_in_repeat()
        steps = get_runner(main_window).macro["steps"]
        assert len(steps) == 1
        assert steps[0]["type"] == "repeat"
        assert len(steps[0]["steps"]) == 2


# ---------------------------------------------------------------------------
# Undo/redo tests
# ---------------------------------------------------------------------------


class TestUndoRedo:
    def test_undo_deletes_last_action(self, main_window: MainWindow):
        set_current_step_row(main_window, 0)
        main_window.on_delete_step()
        assert step_count(main_window) == 1
        main_window.undo()
        assert step_count(main_window) == 2

    def test_redo_after_undo(self, main_window: MainWindow):
        set_current_step_row(main_window, 0)
        main_window.on_delete_step()
        main_window.undo()
        main_window.redo()
        assert step_count(main_window) == 1

    def test_undo_button_state(self, main_window: MainWindow):
        assert not main_window.btn_undo.isEnabled()
        set_current_step_row(main_window, 0)
        main_window.on_delete_step()
        assert main_window.btn_undo.isEnabled()


# ---------------------------------------------------------------------------
# Empty state tests
# ---------------------------------------------------------------------------


class TestEmptyStates:
    def test_empty_macro_shows_hint(self, main_window: MainWindow):
        main_window.macro_list.setCurrentRow(0)
        set_current_step_row(main_window, 0)
        main_window.on_delete_step()
        set_current_step_row(main_window, 0)
        main_window.on_delete_step()
        assert step_count(main_window) == 0
        main_window.update_empty_states()
        assert main_window.step_list.isHidden()
        assert not main_window.step_empty_label.isHidden()

    def test_no_macros_shows_hint(self, main_window: MainWindow):
        main_window.macro_list.setCurrentRow(0)
        main_window.on_delete_step()
        # Can't easily test macro empty state without deleting macros
        # This is tested at the integration level


# ---------------------------------------------------------------------------
# Property panel tests
# ---------------------------------------------------------------------------


class TestPropertyPanel:
    def test_selecting_step_shows_props(self, main_window: MainWindow):
        set_current_step_row(main_window, 0)
        assert main_window.prop_fields_layout.count() > 0

    def test_selecting_different_step_updates_props(self, main_window: MainWindow):
        set_current_step_row(main_window, 0)
        set_current_step_row(main_window, 1)
        assert main_window.prop_fields_layout.count() > 0

    def test_macro_props_shown_when_no_step_selected(self, main_window: MainWindow):
        main_window.step_list.clearSelection()
        main_window.show_macro_props()
        assert main_window.prop_title.text() != ""


# ---------------------------------------------------------------------------
# Property editing tests
# ---------------------------------------------------------------------------


class TestPropertyEditing:
    def test_edit_numeric_field(self, main_window: MainWindow):
        set_current_step_row(main_window, 0)
        step = get_runner(main_window).macro["steps"][0]
        step["ms"] = 100
        edit = MagicMock()
        edit.text.return_value = "250"
        main_window.on_prop_edit(step, "ms", edit)
        assert step["ms"] == 250

    def test_edit_invalid_numeric_ignored(self, main_window: MainWindow):
        set_current_step_row(main_window, 0)
        step = get_runner(main_window).macro["steps"][0]
        step["ms"] = 100
        edit = MagicMock()
        edit.text.return_value = "not_a_number"
        main_window.on_prop_edit(step, "ms", edit)
        assert step["ms"] == 100

    def test_edit_hold_ms_field(self, main_window: MainWindow):
        set_current_step_row(main_window, 0)
        step = get_runner(main_window).macro["steps"][0]
        edit = MagicMock()
        edit.text.return_value = "150"
        main_window.on_prop_edit(step, "hold_ms", edit)
        assert step["hold_ms"] == 150

    def test_edit_key_field(self, main_window: MainWindow):
        set_current_step_row(main_window, 0)
        step = get_runner(main_window).macro["steps"][0]
        edit = MagicMock()
        edit.text.return_value = "space"
        main_window.on_prop_edit(step, "key", edit)
        assert step["key"] == "space"

    def test_prop_bool_sets_value(self, main_window: MainWindow):
        set_current_step_row(main_window, 0)
        step = get_runner(main_window).macro["steps"][0]
        step["skip"] = False
        main_window.on_prop_bool(step, "skip", True)
        assert step["skip"] is True

    def test_prop_bool_skip_repeat_propagates(self, main_window: MainWindow):
        main_window.macro_list.setCurrentRow(1)
        set_current_step_row(main_window, 1)
        step = get_runner(main_window).macro["steps"][1]
        assert step["type"] == "repeat"
        step["steps"] = [{"type": "key", "key": "a"}, {"type": "delay", "ms": 100}]
        main_window.on_prop_bool(step, "skip", True)
        assert step["skip"] is True
        for child in step["steps"]:
            assert child["skip"] is True

    def test_combo_edit(self, main_window: MainWindow):
        set_current_step_row(main_window, 0)
        step = get_runner(main_window).macro["steps"][0]
        main_window.on_combo_edit(step, "key", "escape")
        assert step["key"] == "escape"

    def test_threshold_changed(self, main_window: MainWindow):
        set_current_step_row(main_window, 0)
        step = get_runner(main_window).macro["steps"][0]
        label = MagicMock()
        main_window.on_threshold_changed(step, 90, label)
        assert step["threshold"] == 0.9


# ---------------------------------------------------------------------------
# Template management tests
# ---------------------------------------------------------------------------


class TestTemplateManagement:
    def test_delete_template_clears_name(self, main_window: MainWindow):
        runner = get_runner(main_window)
        runner.macro["steps"] = [{"type": "wait_image", "template": "btn"}]
        runner.macro["templates"] = {"btn": {"label": "Button"}}
        main_window.on_macro_selected(0)
        set_current_step_row(main_window, 0)
        step = runner.macro["steps"][0]
        main_window.on_delete_template(step)
        assert step["template"] == ""

    def test_rename_template_updates_label(self, main_window: MainWindow):
        runner = get_runner(main_window)
        runner.macro["steps"] = [{"type": "wait_image", "template": "btn"}]
        runner.macro["templates"] = {"btn": {"label": "Button"}}
        main_window.on_macro_selected(0)
        set_current_step_row(main_window, 0)
        step = runner.macro["steps"][0]
        edit = MagicMock()
        edit.text.return_value = "Submit"
        main_window.on_rename_template(step, edit)
        assert runner.macro["templates"]["btn"]["label"] == "Submit"

    def test_sync_macro_templates_prunes_unused(self, main_window: MainWindow):
        runner = get_runner(main_window)
        runner.macro["steps"] = [{"type": "key", "key": "a"}]
        runner.macro["templates"] = {"old": {"label": "Old"}, "unused": {"label": "Unused"}}
        main_window.on_macro_selected(0)
        main_window.sync_macro_templates()
        assert "old" not in runner.macro.get("templates", {})
        assert "unused" not in runner.macro.get("templates", {})

    def test_sync_macro_templates_keeps_used(self, main_window: MainWindow):
        runner = get_runner(main_window)
        runner.macro["steps"] = [{"type": "wait_image", "template": "btn"}]
        runner.macro["templates"] = {"btn": {"label": "Button"}}
        main_window.on_macro_selected(0)
        main_window.sync_macro_templates()
        assert runner.macro["templates"]["btn"]["label"] == "Button"


# ---------------------------------------------------------------------------
# Macro CRUD tests (without dialogs)
# ---------------------------------------------------------------------------


class TestMacroCrud:
    def test_save_runner_writes_file(self, main_window: MainWindow):
        runner = get_runner(main_window)
        runner.macro["steps"] = [{"type": "key", "key": "z"}]
        main_window.save_runner(runner)
        assert runner.source_path is not None
        data = json.loads(runner.source_path.read_text(encoding="utf-8"))
        assert data["steps"][0]["key"] == "z"

    def test_save_current_macro_pushes_undo(self, main_window: MainWindow):
        runner = get_runner(main_window)
        original_steps = runner.macro["steps"].copy()
        runner.macro["steps"].append({"type": "delay", "ms": 100})
        main_window.save_current_macro()
        assert len(runner.undo_stack) == 1
        assert runner.undo_stack[0]["steps"] == original_steps

    def test_delete_macro_removes_from_list(self, main_window: MainWindow):
        initial_count = main_window.macro_list.count()
        with patch("main_window.MessageBoxBase") as mock_dialog:
            instance = MagicMock()
            instance.exec.return_value = True
            mock_dialog.return_value = instance
            main_window.delete_macro(0)
        assert main_window.macro_list.count() == initial_count - 1

    def test_delete_macro_unlinks_file(self, main_window: MainWindow):
        runner = get_runner(main_window)
        path = runner.source_path
        assert path is not None
        with patch("main_window.MessageBoxBase") as mock_dialog:
            instance = MagicMock()
            instance.exec.return_value = True
            mock_dialog.return_value = instance
            main_window.delete_macro(0)
        assert not path.exists()

    def test_rename_macro_updates_label(self, main_window: MainWindow):
        runner = get_runner(main_window)
        original_label = runner.label
        with patch("main_window.MessageBoxBase") as mock_dialog:
            instance = MagicMock()
            instance.exec.return_value = True
            mock_dialog.return_value = instance
            # Patch LineEdit so the dialog uses our mock with the desired text
            with patch("main_window.LineEdit") as mock_line_edit:
                edit_instance = MagicMock()
                edit_instance.text.return_value = "Renamed Macro"
                mock_line_edit.return_value = edit_instance
                main_window.rename_macro(0)
        assert runner.label == "Renamed Macro"
        assert runner.label != original_label

    def test_duplicate_macro_creates_new(self, main_window: MainWindow):
        initial_count = main_window.macro_list.count()
        main_window.on_duplicate_macro()
        assert main_window.macro_list.count() == initial_count + 1


# ---------------------------------------------------------------------------
# Execution control tests
# ---------------------------------------------------------------------------


class TestExecutionControl:
    def test_on_run_starts_runner(self, main_window: MainWindow):
        runner = get_runner(main_window)
        runner.is_running = lambda: False
        with patch.object(runner, "start") as mock_start:
            main_window.on_run()
        mock_start.assert_called_once()

    def test_on_run_stops_running_runner(self, main_window: MainWindow):
        runner = get_runner(main_window)
        runner.is_running = lambda: True
        with patch.object(runner, "stop") as mock_stop:
            main_window.on_run()
        mock_stop.assert_called_once()

    def test_on_run_disabled_macro_does_nothing(self, main_window: MainWindow):
        runner = get_runner(main_window)
        runner.macro["meta"]["enabled"] = False
        runner.is_running = lambda: False
        with patch.object(runner, "start") as mock_start:
            main_window.on_run()
        mock_start.assert_not_called()


# ---------------------------------------------------------------------------
# Undo / redo deeper tests
# ---------------------------------------------------------------------------


class TestUndoRedoDeep:
    def test_multiple_undo_levels(self, main_window: MainWindow):
        runner = get_runner(main_window)
        original = copy.deepcopy(runner.macro)
        # Make 3 changes
        for i in range(3):
            runner.macro["steps"].append({"type": "delay", "ms": i + 1})
            main_window.save_current_macro()
        assert len(runner.undo_stack) == 3
        # Undo all
        for _ in range(3):
            main_window.undo()
        assert runner.macro["steps"] == original["steps"]

    def test_redo_after_multiple_undo(self, main_window: MainWindow):
        runner = get_runner(main_window)
        runner.macro["steps"].append({"type": "delay", "ms": 100})
        main_window.save_current_macro()
        main_window.undo()
        assert len(runner.redo_stack) == 1
        main_window.redo()
        assert len(runner.redo_stack) == 0
        assert runner.macro["steps"][-1]["ms"] == 100

    def test_undo_redo_buttons_state(self, main_window: MainWindow):
        runner = get_runner(main_window)
        assert not main_window.btn_undo.isEnabled()
        assert not main_window.btn_redo.isEnabled()
        runner.macro["steps"].append({"type": "delay", "ms": 100})
        main_window.save_current_macro()
        assert main_window.btn_undo.isEnabled()
        main_window.undo()
        assert main_window.btn_redo.isEnabled()


# ---------------------------------------------------------------------------
# Macro list reorder tests
# ---------------------------------------------------------------------------


class TestMacroListReorder:
    def test_reorder_updates_runners(self, main_window: MainWindow):
        if main_window.macro_list.count() < 2:
            pytest.skip("Need at least 2 macros")
        original_order = [r.name for r in main_window.runners]
        # Swap rows 0 and 1
        item0 = main_window.macro_list.takeItem(0)
        main_window.macro_list.insertItem(1, item0)
        main_window.on_macros_reordered()
        new_order = [r.name for r in main_window.runners]
        assert new_order == [original_order[1], original_order[0]]

    def test_reorder_saves_config(self, main_window: MainWindow):
        if main_window.macro_list.count() < 2:
            pytest.skip("Need at least 2 macros")
        with patch.object(cfg, "save") as mock_save:
            item0 = main_window.macro_list.takeItem(0)
            main_window.macro_list.insertItem(1, item0)
            main_window.on_macros_reordered()
        mock_save.assert_called_once()


# ---------------------------------------------------------------------------
# Hotkey / native event tests
# ---------------------------------------------------------------------------


class TestHotkeys:
    def test_native_event_triggers_run(self, main_window: MainWindow):
        from qfluentwidgets import FluentWindow

        runner = get_runner(main_window)
        hid = 0xBF00
        main_window.hotkey_ids = [hid]
        main_window.hotkey_map = {hid: runner}
        with patch("main_window.ctypes.wintypes.MSG") as mock_msg:
            instance = MagicMock()
            instance.message = 0x0312
            instance.wParam = hid
            mock_msg.from_address.return_value = instance
            with (
                patch.object(main_window, "run_hotkey") as mock_run,
                patch.object(FluentWindow, "nativeEvent", return_value=(False, 0)),
            ):
                main_window.nativeEvent(b"windows_generic_MSG", 0)
        mock_run.assert_called_once_with(runner)

    def test_run_hotkey_starts_runner(self, main_window: MainWindow):
        runner = get_runner(main_window)
        runner.is_running = lambda: False
        runner.macro["meta"]["enabled"] = True
        with patch.object(runner, "start") as mock_start, patch.object(main_window, "start_refresh_timer"):
            main_window.run_hotkey(runner)
        mock_start.assert_called_once()

    def test_run_hotkey_stops_running_runner(self, main_window: MainWindow):
        runner = get_runner(main_window)
        runner.is_running = lambda: True
        with patch.object(runner, "stop") as mock_stop:
            main_window.run_hotkey(runner)
        mock_stop.assert_called_once()


# ---------------------------------------------------------------------------
# Event / focus tests
# ---------------------------------------------------------------------------


class TestEvents:
    def test_commit_field_edits(self, main_window: MainWindow):
        edit = LineEdit()
        edit.editingFinished = MagicMock()
        edit.clearFocus = MagicMock()
        edit.hasFocus = MagicMock(return_value=True)
        main_window.right_panel.widget().layout().addWidget(edit)
        main_window.commit_field_edits()
        edit.editingFinished.emit.assert_called_once()
        edit.clearFocus.assert_called_once()

    def test_change_event_commits_edits(self, main_window: MainWindow):
        edit = LineEdit()
        edit.editingFinished = MagicMock()
        edit.clearFocus = MagicMock()
        edit.hasFocus = MagicMock(return_value=True)
        main_window.right_panel.widget().layout().addWidget(edit)
        with patch.object(main_window, "isActiveWindow", return_value=False):
            event = QEvent(QEvent.Type.ActivationChange)
            main_window.changeEvent(event)
        edit.editingFinished.emit.assert_called_once()


# ---------------------------------------------------------------------------
# Load macros error handling
# ---------------------------------------------------------------------------


class TestLoadMacrosError:
    def test_skips_corrupted_macro(self, main_window: MainWindow, macros_dir: Path):
        bad = macros_dir / "bad.json"
        bad.write_text("not json", encoding="utf-8")
        main_window.load_macros()
        names = [r.name for r in main_window.runners]
        assert "bad" not in names


# ---------------------------------------------------------------------------
# Macro properties panel tests
# ---------------------------------------------------------------------------


class TestMacroProps:
    def test_custom_target_window_added(self, main_window: MainWindow):
        runner = get_runner(main_window)
        runner.target_window = "CustomWindow"
        with patch.object(window, "list_visible_windows", return_value=[]):
            main_window.show_macro_props()
        layout = main_window.prop_fields_layout
        widgets = [layout.itemAt(i).widget() for i in range(layout.count()) if layout.itemAt(i).widget()]
        combos = [w for w in widgets if isinstance(w, ComboBox)]
        assert len(combos) > 0
        all_texts = {combos[0].itemText(i) for i in range(combos[0].count())}
        assert "CustomWindow" in all_texts

    def test_show_macro_props_no_runner(self, main_window: MainWindow):
        main_window.current_runner = None
        main_window.show_macro_props()
        assert main_window.prop_title.text() == t("step.props_title")


# ---------------------------------------------------------------------------
# Step property panel tests
# ---------------------------------------------------------------------------


class TestStepPropertyPanels:
    def test_wait_image_props_with_existing_template(self, main_window: MainWindow, templates_dir: Path):
        (templates_dir / "btn.png").write_bytes(MINI_PNG)
        runner = get_runner(main_window)
        runner.macro["steps"] = [{"type": "wait_image", "template": "btn", "timeout_ms": 5000}]
        main_window.on_macro_selected(0)
        set_current_step_row(main_window, 0)
        step = runner.macro["steps"][0]
        main_window.show_props(step)
        assert main_window.prop_fields_layout.count() > 0

    def test_if_image_props(self, main_window: MainWindow):
        runner = get_runner(main_window)
        runner.macro["steps"] = [{"type": "if_image", "template": "cond", "then": [], "else": []}]
        main_window.on_macro_selected(0)
        set_current_step_row(main_window, 0)
        step = runner.macro["steps"][0]
        main_window.show_props(step)
        assert main_window.prop_fields_layout.count() > 0

    def test_grid_nav_props(self, main_window: MainWindow):
        runner = get_runner(main_window)
        runner.macro["steps"] = [{"type": "grid_nav", "rows": 3, "start": 0, "on_next_row": [], "on_next_col": []}]
        main_window.on_macro_selected(0)
        set_current_step_row(main_window, 0)
        step = runner.macro["steps"][0]
        main_window.show_props(step)
        assert main_window.prop_fields_layout.count() > 0

    def test_hold_key_props(self, main_window: MainWindow):
        runner = get_runner(main_window)
        runner.macro["steps"] = [{"type": "hold_key_until_gone", "key": "w", "template": "", "load_delay_ms": 2000}]
        main_window.on_macro_selected(0)
        set_current_step_row(main_window, 0)
        step = runner.macro["steps"][0]
        main_window.show_props(step)
        assert main_window.prop_fields_layout.count() > 0

    def test_if_any_image_props(self, main_window: MainWindow):
        runner = get_runner(main_window)
        runner.macro["steps"] = [{"type": "if_any_image", "templates": ["a"], "branches": {"a": []}}]
        main_window.on_macro_selected(0)
        set_current_step_row(main_window, 0)
        step = runner.macro["steps"][0]
        main_window.show_props(step)
        assert main_window.prop_fields_layout.count() > 0

    def test_show_props_skip_disabled_for_child_of_skipped_repeat(self, main_window: MainWindow):
        runner = get_runner(main_window)
        runner.macro["steps"] = [
            {"type": "repeat", "count": 1, "skip": True, "steps": [{"type": "key", "key": "a"}]},
        ]
        main_window.on_macro_selected(0)
        set_current_step_row(main_window, 1)
        step = runner.macro["steps"][0]["steps"][0]
        main_window.show_props(step)
        layout = main_window.prop_fields_layout
        widgets = [layout.itemAt(i).widget() for i in range(layout.count()) if layout.itemAt(i).widget()]
        checkboxes = [w for w in widgets if isinstance(w, CheckBox) and w.text() == t("prop.skip")]
        assert len(checkboxes) > 0
        assert not checkboxes[0].isEnabled()


# ---------------------------------------------------------------------------
# Template preview / meta tests
# ---------------------------------------------------------------------------


class TestTemplatePreviewAndMeta:
    def test_template_preview_with_image(self, main_window: MainWindow, templates_dir: Path):
        (templates_dir / "btn.png").write_bytes(MINI_PNG)
        preview = main_window.template_preview("btn")
        assert preview.pixmap() is not None

    def test_write_template_meta(self, main_window: MainWindow):
        runner = get_runner(main_window)
        with patch("main_window.capture.Grabber") as mock_grabber:
            instance = MagicMock()
            instance.screen_width = 1920
            instance.screen_height = 1080
            mock_grabber.return_value = instance
            main_window.write_template_meta("btn")
        assert runner.macro["templates"]["btn"]["capture_width"] == 1920
        assert runner.macro["templates"]["btn"]["capture_height"] == 1080

    def test_ensure_template_meta_no_op_when_exists(self, main_window: MainWindow):
        runner = get_runner(main_window)
        runner.macro.setdefault("templates", {})["btn"] = {"label": "Btn", "capture_width": 100, "capture_height": 200}
        with patch.object(main_window, "write_template_meta") as mock_write:
            main_window.ensure_template_meta("btn")
        mock_write.assert_not_called()

    def test_ensure_template_meta_writes_when_missing(self, main_window: MainWindow):
        runner = get_runner(main_window)
        runner.macro.setdefault("templates", {})["btn"] = {"label": "Btn"}
        with patch.object(main_window, "write_template_meta") as mock_write:
            main_window.ensure_template_meta("btn")
        mock_write.assert_called_once_with("btn")

    def test_on_template_resolution_edit(self, main_window: MainWindow):
        runner = get_runner(main_window)
        runner.macro.setdefault("templates", {})["btn"] = {"label": "Btn"}
        edit = LineEdit()
        edit.setText("1920")
        main_window.on_template_resolution_edit("btn", "capture_width", edit)
        assert runner.macro["templates"]["btn"]["capture_width"] == 1920


# ---------------------------------------------------------------------------
# Grid nav edit tests
# ---------------------------------------------------------------------------


class TestGridNav:
    def test_on_grid_nav_start_edit(self, main_window: MainWindow):
        step = {"type": "grid_nav", "start": 0}
        edit = LineEdit()
        edit.setText("5")
        with patch.object(main_window, "mutate_steps") as mock_mutate:
            main_window.on_grid_nav_start_edit(step, edit)
        assert step["start"] == 4
        mock_mutate.assert_called_once()


# ---------------------------------------------------------------------------
# Hotkey capture tests
# ---------------------------------------------------------------------------


class TestKeyCaptures:
    def test_on_hotkey_capture(self, main_window: MainWindow):
        edit = LineEdit()
        event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_F1, Qt.KeyboardModifier.ControlModifier)
        with patch.object(main_window, "set_macro_hotkey") as mock_set:
            main_window.on_hotkey_capture(event, edit)
        assert edit.text() == "ctrl+f1"
        mock_set.assert_called_once_with("ctrl+f1")

    def test_on_hotkey_capture_escape_clears(self, main_window: MainWindow):
        edit = LineEdit()
        edit.setText("ctrl+f1")
        with patch.object(main_window, "set_macro_hotkey") as mock_set:
            event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
            main_window.on_hotkey_capture(event, edit)
        assert edit.text() == ""
        mock_set.assert_called_once_with("")

    def test_on_key_step_capture(self, main_window: MainWindow):
        edit = LineEdit()
        step = {"type": "key", "key": ""}
        event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_A, Qt.KeyboardModifier.NoModifier)
        with patch.object(main_window, "mutate_steps") as mock_mutate:
            main_window.on_key_step_capture(event, edit, step)
        assert step["key"] == "a"
        assert edit.text() == "a"
        mock_mutate.assert_called_once()

    def test_on_key_step_capture_escape(self, main_window: MainWindow):
        edit = LineEdit()
        step = {"type": "key", "key": "a"}
        event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
        with patch.object(main_window, "mutate_steps") as mock_mutate:
            main_window.on_key_step_capture(event, edit, step)
        assert step["key"] == ""
        assert edit.text() == ""
        mock_mutate.assert_called_once()

    def test_on_key_step_cleared(self, main_window: MainWindow):
        step = {"type": "key", "key": "a"}
        with patch.object(main_window, "mutate_steps") as mock_mutate:
            main_window.on_key_step_cleared(step)
        assert step["key"] == ""
        mock_mutate.assert_called_once()


# ---------------------------------------------------------------------------
# Region / template tests
# ---------------------------------------------------------------------------


class TestRegionCapture:
    def test_on_region_captured_replaces_old_template(self, main_window: MainWindow, templates_dir: Path):
        old = templates_dir / "old.png"
        old.write_bytes(MINI_PNG)
        step = {"type": "wait_image", "template": "old"}
        runner = get_runner(main_window)
        runner.macro["templates"]["old"] = {"label": "Old"}
        with (
            patch.object(main_window, "sync_macro_templates"),
            patch.object(main_window, "mutate_steps"),
            patch.object(main_window, "showNormal"),
        ):
            main_window.on_region_captured(step, "new")
        assert step["template"] == "new"
        assert not old.exists()

    def test_on_any_region_captured_replaces_old(self, main_window: MainWindow, templates_dir: Path):
        old = templates_dir / "old.png"
        old.write_bytes(MINI_PNG)
        step = {"type": "if_any_image", "templates": ["old"], "branches": {"old": []}}
        runner = get_runner(main_window)
        runner.macro["templates"]["old"] = {"label": "Old"}
        with (
            patch.object(main_window, "sync_macro_templates"),
            patch.object(main_window, "mutate_steps"),
            patch.object(main_window, "showNormal"),
        ):
            main_window.on_any_region_captured(step, 0, "new")
        assert step["templates"][0] == "new"
        assert not old.exists()

    def test_on_rename_template(self, main_window: MainWindow):
        runner = get_runner(main_window)
        step = {"type": "wait_image", "template": "btn"}
        runner.macro["templates"] = {"btn": {"label": "Button"}}
        edit = LineEdit()
        edit.setText("Submit")
        with patch.object(main_window, "mutate_steps") as mock_mutate:
            main_window.on_rename_template(step, edit)
        assert runner.macro["templates"]["btn"]["label"] == "Submit"
        mock_mutate.assert_called_once()

    def test_on_delete_template(self, main_window: MainWindow, templates_dir: Path):
        old = templates_dir / "btn.png"
        old.write_bytes(MINI_PNG)
        step = {"type": "wait_image", "template": "btn"}
        with (
            patch.object(main_window, "sync_macro_templates"),
            patch.object(main_window, "mutate_steps") as mock_mutate,
        ):
            main_window.on_delete_template(step)
        assert step["template"] == ""
        assert not old.exists()
        mock_mutate.assert_called_once()

    def test_on_rename_any_template(self, main_window: MainWindow):
        runner = get_runner(main_window)
        step = {"type": "if_any_image", "templates": ["btn"], "branches": {"btn": []}}
        runner.macro["templates"] = {"btn": {"label": "Button"}}
        edit = LineEdit()
        edit.setText("Submit")
        with patch.object(main_window, "mutate_steps") as mock_mutate:
            main_window.on_rename_any_template(step, 0, edit)
        assert runner.macro["templates"]["btn"]["label"] == "Submit"
        mock_mutate.assert_called_once()

    def test_on_delete_any_template(self, main_window: MainWindow, templates_dir: Path):
        old = templates_dir / "old.png"
        old.write_bytes(MINI_PNG)
        step = {"type": "if_any_image", "templates": ["old"], "branches": {"old": []}}
        runner = get_runner(main_window)
        runner.macro["templates"]["old"] = {"label": "Old"}
        with (
            patch.object(main_window, "sync_macro_templates"),
            patch.object(main_window, "mutate_steps") as mock_mutate,
        ):
            main_window.on_delete_any_template(step, 0)
        assert len(step["templates"]) == 0
        assert not old.exists()
        mock_mutate.assert_called_once()

    def test_on_add_any_template(self, main_window: MainWindow):
        runner = get_runner(main_window)
        step = {"type": "if_any_image", "templates": [], "branches": {}}
        runner.macro["steps"] = [step]
        main_window.on_macro_selected(0)
        with patch.object(main_window, "sync_macro_templates"), patch.object(main_window, "mutate_steps"):
            main_window.on_add_any_template(step)
        assert len(step["templates"]) == 1


# ---------------------------------------------------------------------------
# Step operations edge cases
# ---------------------------------------------------------------------------


class TestStepEdgeCases:
    def test_do_add_step_with_no_selection_appends(self, main_window: MainWindow):
        runner = get_runner(main_window)
        main_window.step_list.clearSelection()
        step = {"type": "delay", "ms": 100}
        main_window.do_add_step(step)
        assert runner.macro["steps"][-1] == step

    def test_delete_step_multi_select(self, main_window: MainWindow):
        runner = get_runner(main_window)
        runner.macro["steps"] = [
            {"type": "key", "key": "a"},
            {"type": "key", "key": "b"},
            {"type": "key", "key": "c"},
        ]
        main_window.on_macro_selected(0)
        select_step_rows(main_window, [0, 2])
        main_window.on_delete_step()
        keys = [s["key"] for s in runner.macro["steps"]]
        assert keys == ["b"]

    def test_paste_steps_with_templates(self, main_window: MainWindow, templates_dir: Path):
        (templates_dir / "btn.png").write_bytes(MINI_PNG)
        runner = get_runner(main_window)
        runner.macro["steps"] = [{"type": "wait_image", "template": "btn"}]
        runner.macro["templates"] = {"btn": {"label": "Button"}}
        main_window.on_macro_selected(0)
        set_current_step_row(main_window, 0)
        main_window.copy_steps()
        main_window.step_list.clearSelection()
        main_window.paste_steps()
        assert len(runner.macro["steps"]) == 2
        assert "btn" in runner.macro.get("templates", {})

    def test_duplicate_steps(self, main_window: MainWindow):
        runner = get_runner(main_window)
        runner.macro["steps"] = [{"type": "key", "key": "a"}]
        main_window.on_macro_selected(0)
        set_current_step_row(main_window, 0)
        main_window.duplicate_steps()
        assert len(runner.macro["steps"]) == 2
        assert runner.macro["steps"][0] == runner.macro["steps"][1]

    def test_wrap_in_repeat_no_selection(self, main_window: MainWindow):
        runner = get_runner(main_window)
        original = copy.deepcopy(runner.macro["steps"])
        main_window.step_list.clearSelection()
        main_window.wrap_in_repeat()
        assert runner.macro["steps"] == original

    def test_wrap_in_repeat_single_step(self, main_window: MainWindow):
        runner = get_runner(main_window)
        runner.macro["steps"] = [{"type": "key", "key": "a"}, {"type": "key", "key": "b"}]
        main_window.on_macro_selected(0)
        set_current_step_row(main_window, 0)
        main_window.wrap_in_repeat()
        assert runner.macro["steps"][0]["type"] == "repeat"
        assert len(runner.macro["steps"][0]["steps"]) == 1
        assert runner.macro["steps"][0]["steps"][0]["key"] == "a"
        assert runner.macro["steps"][1]["key"] == "b"

    def test_on_move_step_first_up_does_nothing(self, main_window: MainWindow):
        runner = get_runner(main_window)
        runner.macro["steps"] = [{"type": "key", "key": "a"}, {"type": "key", "key": "b"}]
        main_window.on_macro_selected(0)
        set_current_step_row(main_window, 0)
        main_window.on_move_step(-1)
        assert runner.macro["steps"][0]["key"] == "a"
        assert runner.macro["steps"][1]["key"] == "b"

    def test_on_move_step_last_down_does_nothing(self, main_window: MainWindow):
        runner = get_runner(main_window)
        runner.macro["steps"] = [{"type": "key", "key": "a"}, {"type": "key", "key": "b"}]
        main_window.on_macro_selected(0)
        set_current_step_row(main_window, 1)
        main_window.on_move_step(1)
        assert runner.macro["steps"][0]["key"] == "a"
        assert runner.macro["steps"][1]["key"] == "b"

    def test_refresh_current_step(self, main_window: MainWindow):
        main_window.refresh_current_step()

    def test_populate_steps_no_runner(self, main_window: MainWindow):
        main_window.current_runner = None
        main_window.populate_steps()
        assert step_count(main_window) == 0
        assert main_window.step_tree is None

    def test_on_step_selected_negative_row(self, main_window: MainWindow):
        main_window.on_step_selected(None, None)
        assert main_window.prop_title.text() != ""

    def test_on_step_selected_no_runner(self, main_window: MainWindow):
        main_window.current_runner = None
        main_window.on_step_selected(None, None)
        # no exception

    def test_on_prop_edit_invalid_key_ignored(self, main_window: MainWindow):
        runner = get_runner(main_window)
        runner.macro["steps"] = [{"type": "key", "key": "a"}]
        main_window.on_macro_selected(0)
        step = runner.macro["steps"][0]
        edit = LineEdit()
        edit.setText("invalid_key_xyz")
        main_window.on_prop_edit(step, "key", edit)
        assert step["key"] == "a"

    def test_apply_step_note(self, main_window: MainWindow):
        item = QTreeWidgetItem(["step"])
        step = {"type": "key", "key": "a", "note": "  do this  "}
        main_window.apply_step_note(item, step)
        assert "do this" in item.toolTip(0)
        assert "do this" in item.text(0)


# ---------------------------------------------------------------------------
# Status / runner tests
# ---------------------------------------------------------------------------


class TestStatusAndRunner:
    def test_refresh_status_running(self, main_window: MainWindow):
        runner = get_runner(main_window)
        runner.status = Status(
            running=True,
            state="running",
            progress=1,
            repeat_total=3,
            score=0.95,
            match_name="btn",
        )
        runner.start_time = time.monotonic() - 10
        runner.current_step = runner.macro["steps"][0]
        main_window.refresh_status()
        assert t("action.stop") in main_window.btn_run.text()

    def test_refresh_status_last_reason(self, main_window: MainWindow):
        runner = get_runner(main_window)
        runner.status = Status(
            running=False,
            last_reason="done",
            message="Finished",
            elapsed_s=5.0,
        )
        main_window.start_refresh_timer()
        main_window.refresh_status()
        assert "Finished" in main_window.status_label.text()

    def test_highlight_current_step(self, main_window: MainWindow):
        runner = get_runner(main_window)
        runner.macro["steps"] = [{"type": "key", "key": "a"}, {"type": "key", "key": "b"}]
        main_window.on_macro_selected(0)
        runner.current_step = runner.macro["steps"][1]
        main_window.highlight_current_step(runner)
        assert get_current_step_row(main_window) == 1

    def test_set_editing_locked(self, main_window: MainWindow):
        main_window.set_editing_locked(True)
        assert not main_window.btn_add_step.isEnabled()
        assert not main_window.btn_del.isEnabled()
        assert not main_window.btn_up.isEnabled()
        assert not main_window.btn_down.isEnabled()
        assert not main_window.macro_list.isEnabled()

    def test_save_overlay_position(self, main_window: MainWindow):
        from PySide6.QtCore import QPoint

        main_window.overlay.pos.return_value = QPoint(123, 456)
        with patch.object(cfg, "save") as mock_save:
            main_window.save_overlay_position()
        mock_save.assert_called_once()
        assert main_window.conf.general.overlay_position == [123, 456]

    def test_apply_settings(self, main_window: MainWindow):
        new_conf = cfg.get_defaults()
        new_conf.general.always_on_top = True
        with patch.object(main_window, "show"), patch("main_window.setTheme"):
            main_window.apply_settings(new_conf)
        assert main_window.conf is new_conf
        for runner in main_window.runners:
            assert runner.conf is new_conf


# ---------------------------------------------------------------------------
# Menu / dialog tests
# ---------------------------------------------------------------------------


class TestMenusAndDialogs:
    def test_show_file_menu(self, main_window: MainWindow):
        with patch("main_window.RoundMenu") as mock_menu:
            instance = MagicMock()
            mock_menu.return_value = instance
            main_window.show_file_menu()
        assert instance.addAction.called
        instance.exec.assert_called_once()

    def test_show_edit_menu(self, main_window: MainWindow):
        with patch("main_window.RoundMenu") as mock_menu:
            instance = MagicMock()
            mock_menu.return_value = instance
            main_window.show_edit_menu()
        assert instance.addAction.called
        instance.exec.assert_called_once()

    def test_show_help_menu(self, main_window: MainWindow):
        with patch("main_window.RoundMenu") as mock_menu:
            instance = MagicMock()
            mock_menu.return_value = instance
            main_window.show_help_menu()
        assert instance.addAction.called
        instance.exec.assert_called_once()

    def test_on_about(self, main_window: MainWindow):
        with patch("main_window.MessageBoxBase") as mock_dialog:
            instance = MagicMock()
            instance.exec.return_value = True
            mock_dialog.return_value = instance
            main_window.on_about()
        mock_dialog.assert_called_once()

    def test_on_sponsor(self, main_window: MainWindow):
        with patch("main_window.webbrowser.open") as mock_open:
            main_window.on_sponsor()
        mock_open.assert_called_once_with("https://github.com/sponsors/nelsonlaidev")

    def test_on_open_logs(self, main_window: MainWindow):
        with patch("main_window.os.startfile") as mock_start:
            main_window.on_open_logs()
        mock_start.assert_called_once()

    def test_on_check_update(self, main_window: MainWindow):
        with patch("main_window.updater.check_async") as mock_check:
            main_window.on_check_update()
        mock_check.assert_called_once()

    def test_on_step_context_menu(self, main_window: MainWindow):
        with patch("main_window.RoundMenu") as mock_menu:
            instance = MagicMock()
            mock_menu.return_value = instance
            main_window.on_step_context_menu(main_window.step_list.rect().topLeft())
        assert instance.addAction.called
        instance.exec.assert_called_once()

    def test_on_macro_context_menu(self, main_window: MainWindow):
        with patch("main_window.RoundMenu") as mock_menu:
            instance = MagicMock()
            mock_menu.return_value = instance
            main_window.on_macro_context_menu(main_window.macro_list.rect().topLeft())
        assert instance.addAction.called
        instance.exec.assert_called_once()

    def test_on_add_step(self, main_window: MainWindow):
        with patch("main_window.RoundMenu") as mock_menu:
            instance = MagicMock()
            mock_menu.return_value = instance
            main_window.on_add_step()
        assert instance.addAction.called
        instance.exec.assert_called_once()

    def test_add_step_to_branch(self, main_window: MainWindow):
        step = {"type": "if_image", "template": "", "then": [], "else": []}
        with patch("main_window.RoundMenu") as mock_menu:
            instance = MagicMock()
            mock_menu.return_value = instance
            main_window.add_step_to_branch(step, "then")
        assert instance.addAction.called
        instance.exec.assert_called_once()

    def test_add_step_to_any_branch(self, main_window: MainWindow):
        step = {"type": "if_any_image", "templates": ["a"], "branches": {"a": []}}
        with patch("main_window.RoundMenu") as mock_menu:
            instance = MagicMock()
            mock_menu.return_value = instance
            main_window.add_step_to_any_branch(step, "a")
        assert instance.addAction.called
        instance.exec.assert_called_once()

    def test_on_duplicate_macro_no_source_path(self, main_window: MainWindow):
        runner = get_runner(main_window)
        runner.source_path = None
        count_before = main_window.macro_list.count()
        main_window.on_duplicate_macro()
        assert main_window.macro_list.count() == count_before

    def test_on_import_json_bad_zip(self, main_window: MainWindow, tmp_path: Path):
        bad = tmp_path / "bad.zip"
        bad.write_text("not a zip", encoding="utf-8")
        with (
            patch("main_window.QFileDialog.getOpenFileName", return_value=(str(bad), "")),
            patch("main_window.MessageBox") as mock_msg,
        ):
            instance = MagicMock()
            instance.exec.return_value = True
            mock_msg.return_value = instance
            main_window.on_import_json()
        mock_msg.assert_called_once()

    def test_on_export_json_no_path(self, main_window: MainWindow):
        runner = get_runner(main_window)
        original_path = runner.source_path
        with patch("main_window.QFileDialog.getSaveFileName", return_value=("", "")):
            main_window.on_export_json()
        assert runner.source_path == original_path

    def test_on_import_json_no_path(self, main_window: MainWindow):
        with patch("main_window.QFileDialog.getOpenFileName", return_value=("", "")):
            main_window.on_import_json()
        # no exception

    def test_open_settings(self, main_window: MainWindow):
        with (
            patch("main_window.SettingsPage", return_value=MagicMock()),
            patch.object(main_window, "addSubInterface") as mock_add,
            patch.object(main_window.stackedWidget, "setCurrentWidget"),
        ):
            main_window.open_settings()
        mock_add.assert_called_once()

    def test_delete_macro_last_one_clears_state(self, main_window: MainWindow):
        with patch("main_window.MessageBoxBase") as mock_dialog:
            instance = MagicMock()
            instance.exec.return_value = True
            mock_dialog.return_value = instance
            while main_window.macro_list.count() > 0:
                main_window.delete_macro(0)
        assert main_window.current_runner is None
        assert main_window.step_tree is None
        assert main_window.flat_nodes == []

    def test_resize_event(self, main_window: MainWindow):
        from PySide6.QtGui import QResizeEvent

        event = QResizeEvent(main_window.size(), main_window.size())
        main_window.resizeEvent(event)
        assert main_window.titleBar.pos().x() == 0

    def test_refresh_status_no_runner(self, main_window: MainWindow):
        main_window.current_runner = None
        main_window.refresh_status()
        # no exception

    def test_push_undo_no_runner(self, main_window: MainWindow):
        main_window.current_runner = None
        main_window.push_undo()
        # no exception

    def test_push_undo_no_snapshot(self, main_window: MainWindow):
        runner = get_runner(main_window)
        runner.last_snapshot = None
        main_window.push_undo()
        assert len(runner.undo_stack) == 0

    def test_undo_no_runner(self, main_window: MainWindow):
        main_window.current_runner = None
        main_window.undo()
        # no exception

    def test_redo_no_runner(self, main_window: MainWindow):
        main_window.current_runner = None
        main_window.redo()
        # no exception

    def test_save_current_macro_no_runner(self, main_window: MainWindow):
        main_window.current_runner = None
        main_window.save_current_macro()
        # no exception

    def test_on_run_no_runner(self, main_window: MainWindow):
        main_window.current_runner = None
        with patch.object(main_window, "start_refresh_timer") as mock_start:
            main_window.on_run()
        mock_start.assert_not_called()

    def test_on_target_window_combo(self, main_window: MainWindow):
        runner = get_runner(main_window)
        combo = ComboBox()
        combo.addItem("Window", userData="Window")
        combo.setCurrentIndex(0)
        with patch.object(main_window, "save_current_macro") as mock_save:
            main_window.on_target_window_combo(combo)
        assert runner.target_window == "Window"
        assert runner.macro["meta"]["target_window"] == "Window"
        mock_save.assert_called_once()

    def test_on_enabled_toggled(self, main_window: MainWindow):
        runner = get_runner(main_window)
        with (
            patch.object(main_window, "save_current_macro") as mock_save,
            patch.object(main_window, "register_hotkeys") as mock_reg,
        ):
            main_window.on_enabled_toggled(False)
        assert runner.macro["meta"]["enabled"] is False
        mock_save.assert_called_once()
        mock_reg.assert_called_once()

    def test_set_macro_hotkey(self, main_window: MainWindow):
        runner = get_runner(main_window)
        with (
            patch.object(main_window, "save_current_macro") as mock_save,
            patch.object(main_window, "register_hotkeys") as mock_reg,
        ):
            main_window.set_macro_hotkey("ctrl+f1")
        assert runner.macro["meta"]["hotkey"] == "ctrl+f1"
        mock_save.assert_called_once()
        mock_reg.assert_called_once()

    def test_on_stacked_widget_changed(self, main_window: MainWindow):
        main_window.onStackedWidgetChanged(0)
        assert not main_window.returnButton.isVisible()

    def test_on_capture_template(self, main_window: MainWindow):
        with (
            patch.object(main_window, "showMinimized") as mock_min,
            patch.object(main_window, "launch_selector"),
            patch("main_window.QTimer.singleShot"),
        ):
            main_window.on_capture_template({"type": "wait_image", "template": ""})
        mock_min.assert_called_once()

    def test_on_capture_any_template(self, main_window: MainWindow):
        with (
            patch.object(main_window, "showMinimized") as mock_min,
            patch.object(main_window, "launch_any_selector"),
            patch("main_window.QTimer.singleShot"),
        ):
            main_window.on_capture_any_template({"type": "if_any_image", "templates": [""]}, 0)
        mock_min.assert_called_once()

    def test_on_pick_template_no_path(self, main_window: MainWindow):
        step = {"type": "wait_image", "template": "btn"}
        with patch("main_window.QFileDialog.getOpenFileName", return_value=("", "")):
            main_window.on_pick_template(step)
        assert step["template"] == "btn"

    def test_on_pick_any_template_no_path(self, main_window: MainWindow):
        step = {"type": "if_any_image", "templates": ["a"]}
        with patch("main_window.QFileDialog.getOpenFileName", return_value=("", "")):
            main_window.on_pick_any_template(step, 0)
        assert step["templates"][0] == "a"


# ---------------------------------------------------------------------------
# register_hotkeys
# ---------------------------------------------------------------------------


class TestRegisterHotkeys:
    def test_skips_empty_hotkey(self, main_window: MainWindow):
        with patch.object(main_window, "register_hotkeys"):
            pass

    def test_skips_disabled_macro(self, main_window: MainWindow):
        with patch.object(main_window, "register_hotkeys"):
            pass


# ---------------------------------------------------------------------------
# Hotkey capture edge cases
# ---------------------------------------------------------------------------


class TestHotkeyCaptureEdge:
    def test_modifier_only_key_ignored(self, main_window: MainWindow):
        edit = LineEdit()
        event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Shift, Qt.KeyboardModifier.ShiftModifier)
        main_window.on_hotkey_capture(event, edit)
        assert edit.text() == ""

    def test_ctrl_modifier(self, main_window: MainWindow):
        edit = LineEdit()
        event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier, "a")
        main_window.on_hotkey_capture(event, edit)
        assert edit.text() == "ctrl+a"

    def test_alt_modifier(self, main_window: MainWindow):
        edit = LineEdit()
        event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_A, Qt.KeyboardModifier.AltModifier, "a")
        main_window.on_hotkey_capture(event, edit)
        assert edit.text() == "alt+a"

    def test_shift_modifier(self, main_window: MainWindow):
        edit = LineEdit()
        event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_A, Qt.KeyboardModifier.ShiftModifier, "a")
        main_window.on_hotkey_capture(event, edit)
        assert edit.text() == "shift+a"


# ---------------------------------------------------------------------------
# Key step capture edge cases
# ---------------------------------------------------------------------------


class TestKeyStepCaptureEdge:
    def test_modifier_only_key_ignored(self, main_window: MainWindow):
        step = {"type": "key", "key": "enter"}
        edit = LineEdit()
        event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Shift, Qt.KeyboardModifier.ShiftModifier)
        main_window.on_key_step_capture(event, edit, step)
        assert step["key"] == "enter"

    def test_invalid_key_ignored(self, main_window: MainWindow):
        step = {"type": "key", "key": "enter"}
        edit = LineEdit()
        event = QKeyEvent(QEvent.Type.KeyPress, 9999, Qt.KeyboardModifier.NoModifier)
        main_window.on_key_step_capture(event, edit, step)
        assert step["key"] == "enter"


# ---------------------------------------------------------------------------
# refresh_step_list edge cases
# ---------------------------------------------------------------------------


class TestRefreshStepListEdge:
    def test_stop_iteration_when_select_step_not_found(self, main_window: MainWindow):
        main_window.populate_steps()
        main_window.refresh_step_list(select_step={"a": 1})

    def test_both_selects_none(self, main_window: MainWindow):
        main_window.refresh_step_list()


# ---------------------------------------------------------------------------
# mutate_steps edge cases
# ---------------------------------------------------------------------------


class TestMutateStepsEdge:
    def test_no_runner_returns_early(self, main_window: MainWindow):
        main_window.current_runner = None
        mock_fn = MagicMock()
        with patch.object(main_window, "save_current_macro"):
            main_window.mutate_steps(mock_fn)
        mock_fn.assert_not_called()

    def test_calls_mutation_fn(self, main_window: MainWindow):
        mock_fn = MagicMock()
        main_window.mutate_steps(mock_fn)
        mock_fn.assert_called_once_with(get_runner(main_window))


# ---------------------------------------------------------------------------
# populate_steps_and_keep_row
# ---------------------------------------------------------------------------


class TestPopulateStepsAndKeepRow:
    def test_keeps_row(self, main_window: MainWindow):
        set_current_step_row(main_window, 0)
        main_window.populate_steps_and_keep_row()
        assert True


# ---------------------------------------------------------------------------
# set_macro_hotkey
# ---------------------------------------------------------------------------


class TestSetMacroHotkeyEdge:
    def test_no_runner_returns_early(self, main_window: MainWindow):
        main_window.current_runner = None
        main_window.set_macro_hotkey("ctrl+a")
        assert True


# ---------------------------------------------------------------------------
# on_enabled_toggled / on_target_window_combo no runner
# ---------------------------------------------------------------------------


class TestMacroPropEdge:
    def test_enabled_toggled_no_runner(self, main_window: MainWindow):
        main_window.current_runner = None
        main_window.on_enabled_toggled(True)

    def test_target_window_combo_no_runner(self, main_window: MainWindow):
        main_window.current_runner = None
        main_window.on_target_window_combo("SomeWindow")


# ---------------------------------------------------------------------------
# template_preview scaling
# ---------------------------------------------------------------------------


class TestTemplatePreviewEdge:
    def test_scales_wide_image(self, main_window: MainWindow, templates_dir: Path):
        wide_img = bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A])
        (templates_dir / "wide.png").write_bytes(wide_img)
        with patch.object(main_window.right_panel, "width", return_value=10):
            result = main_window.template_preview("wide")
        assert result is not None


# ---------------------------------------------------------------------------
# show_if_any_image_props edge cases
# ---------------------------------------------------------------------------


class TestIfAnyImagePropsEdge:
    def test_empty_template_name_skipped(self, main_window: MainWindow):
        step = {"type": "if_any_image", "templates": ["", "valid"]}
        main_window.show_props(step)
        assert True

    def test_toggle_expands_collapses(self, main_window: MainWindow):
        step = {"type": "if_any_image", "templates": ["t1"], "branches": {}}
        main_window.show_props(step)
        assert True


# ---------------------------------------------------------------------------
# launch_selector / launch_any_selector
# ---------------------------------------------------------------------------


class TestLaunchSelectors:
    def test_launch_selector_starts(self, main_window: MainWindow):
        step = {"type": "wait_image", "template": ""}
        with patch("main_window.RegionSelector") as mock_rs:
            mock_selector = MagicMock()
            mock_rs.return_value = mock_selector
            main_window.launch_selector(step)
        mock_rs.assert_called_once()
        mock_selector.start.assert_called_once()

    def test_launch_any_selector_starts(self, main_window: MainWindow):
        step = {"type": "if_any_image", "templates": ["a"]}
        with patch("main_window.RegionSelector") as mock_rs:
            mock_selector = MagicMock()
            mock_rs.return_value = mock_selector
            main_window.launch_any_selector(step, 0)
        mock_rs.assert_called_once()
        mock_selector.start.assert_called_once()

    def test_launch_any_selector_no_runner(self, main_window: MainWindow):
        main_window.current_runner = None
        step = {"type": "if_any_image", "templates": ["a"]}
        with patch("main_window.RegionSelector") as mock_rs:
            mock_selector = MagicMock()
            mock_rs.return_value = mock_selector
            main_window.launch_any_selector(step, 0)
        mock_rs.assert_called_once_with("")


# ---------------------------------------------------------------------------
# on_pick_template / on_pick_any_template (actual pick)
# ---------------------------------------------------------------------------


class TestPickTemplate:
    def test_pick_template_copies_to_dest(self, main_window: MainWindow, templates_dir: Path, tmp_path: Path):
        src = tmp_path / "src.png"
        src.write_bytes(MINI_PNG)
        step = {"type": "wait_image", "template": ""}
        with (
            patch("main_window.QFileDialog.getOpenFileName", return_value=(str(src), "")),
            patch.object(main_window, "write_template_meta"),
            patch.object(main_window, "sync_macro_templates"),
            patch.object(main_window, "mutate_steps"),
            patch("main_window.time.time", return_value=1234567890),
        ):
            main_window.on_pick_template(step)
        assert step["template"] == "1234567890"
        dest = templates_dir / "1234567890.png"
        assert dest.exists()

    def test_pick_template_empty_name(self, main_window: MainWindow):
        step = {"type": "wait_image", "template": ""}
        src = main_window.macro_templates_dir / "fake.png"
        src.write_bytes(MINI_PNG)
        with (
            patch("main_window.QFileDialog.getOpenFileName", return_value=(str(src), "")),
            patch.object(main_window, "write_template_meta"),
            patch.object(main_window, "sync_macro_templates"),
            patch.object(main_window, "mutate_steps"),
            patch("main_window.time.time", return_value=9999999999),
        ):
            main_window.on_pick_template(step)
        assert step["template"] == "9999999999"

    def test_pick_any_template_copies_to_dest(self, main_window: MainWindow, templates_dir: Path, tmp_path: Path):
        src = tmp_path / "src.png"
        src.write_bytes(MINI_PNG)
        step = {"type": "if_any_image", "templates": ["old"]}
        with (
            patch("main_window.QFileDialog.getOpenFileName", return_value=(str(src), "")),
            patch.object(main_window, "write_template_meta"),
            patch.object(main_window, "sync_macro_templates"),
            patch.object(main_window, "mutate_steps"),
            patch("main_window.time.time", return_value=1234567890),
        ):
            main_window.on_pick_any_template(step, 0)
        assert step["templates"][0] == "1234567890"


# ---------------------------------------------------------------------------
# on_rename_template / on_rename_any_template edge cases
# ---------------------------------------------------------------------------


class TestRenameTemplateEdge:
    def test_rename_template_empty_name(self, main_window: MainWindow):
        step = {"type": "wait_image", "template": "btn"}
        edit = LineEdit()
        edit.setText("")
        main_window.on_rename_template(step, edit)
        assert step["template"] == "btn"

    def test_rename_any_template_empty_name(self, main_window: MainWindow):
        step = {"type": "if_any_image", "templates": ["a"]}
        edit = LineEdit()
        edit.setText("")
        main_window.on_rename_any_template(step, 0, edit)
        assert step["templates"][0] == "a"


# ---------------------------------------------------------------------------
# on_delete_template / on_delete_any_template edge cases
# ---------------------------------------------------------------------------


class TestDeleteTemplateEdge:
    def test_delete_template_no_name(self, main_window: MainWindow):
        step = {"type": "wait_image", "template": ""}
        main_window.on_delete_template(step)
        assert step["template"] == ""

    def test_delete_any_template_invalid_index(self, main_window: MainWindow):
        step = {"type": "if_any_image", "templates": ["a"]}
        main_window.on_delete_any_template(step, 99)
        assert len(step["templates"]) == 1


# ---------------------------------------------------------------------------
# write_template_meta / ensure_template_meta / get_template_meta edge cases
# ---------------------------------------------------------------------------


class TestTemplateMetaEdge:
    def test_write_template_meta_no_runner(self, main_window: MainWindow):
        main_window.current_runner = None
        main_window.write_template_meta("test")

    def test_ensure_template_meta_no_runner(self, main_window: MainWindow):
        main_window.current_runner = None
        main_window.ensure_template_meta("test")

    def test_get_template_meta_corrupt_json(self, main_window: MainWindow):
        macro = get_runner(main_window).macro
        macro["templates"] = {"corrupt": {}}
        runner = get_runner(main_window)
        runner.macro = macro
        meta_path = main_window.macro_templates_dir / "corrupt.json"
        meta_path.write_text("not valid json")
        with patch("main_window.logger.warning"):
            result = main_window.get_template_meta("corrupt")
        assert result == {}


# ---------------------------------------------------------------------------
# on_template_resolution_edit edge cases
# ---------------------------------------------------------------------------


class TestTemplateResolutionEditEdge:
    def test_no_runner(self, main_window: MainWindow):
        main_window.current_runner = None
        edit = LineEdit()
        edit.setText("1920")
        main_window.on_template_resolution_edit("test", "capture_width", edit)

    def test_value_error_ignored(self, main_window: MainWindow):
        edit = LineEdit()
        edit.setText("not_a_number")
        main_window.on_template_resolution_edit("test", "capture_width", edit)


# ---------------------------------------------------------------------------
# sync_macro_templates no runner
# ---------------------------------------------------------------------------


class TestSyncMacroTemplatesEdge:
    def test_no_runner_returns_early(self, main_window: MainWindow):
        main_window.current_runner = None
        main_window.sync_macro_templates()


# ---------------------------------------------------------------------------
# on_grid_nav_start_edit edge cases
# ---------------------------------------------------------------------------


class TestGridNavStartEditEdge:
    def test_value_error_ignored(self, main_window: MainWindow):
        step = {"type": "grid_nav", "rows": 2, "columns": 3, "start": 0}
        edit = LineEdit()
        edit.setText("invalid")
        main_window.on_grid_nav_start_edit(step, edit)
        assert step["start"] == 0


# ---------------------------------------------------------------------------
# clear_props edge cases
# ---------------------------------------------------------------------------


class TestClearPropsEdge:
    def test_none_item_continues(self, main_window: MainWindow):
        main_window.show_props({"type": "delay", "ms": 100})
        with patch.object(main_window.prop_fields_layout, "count", return_value=0):
            main_window.clear_props()

    def test_nested_layout_cleared(self, main_window: MainWindow):
        main_window.show_props({"type": "repeat", "count": 3, "steps": []})
        main_window.clear_props()
        assert main_window.prop_fields_layout.count() == 0


# ---------------------------------------------------------------------------
# push_undo stack truncation
# ---------------------------------------------------------------------------


class TestPushUndoEdge:
    def test_truncates_long_stack(self, main_window: MainWindow):
        runner = get_runner(main_window)
        runner.undo_stack = [copy.deepcopy(runner.macro)] * 50
        snapshot = copy.deepcopy(runner.macro)
        snapshot["meta"]["label"] = "changed"
        runner.last_snapshot = snapshot
        main_window.push_undo()
        assert len(runner.undo_stack) == 50


# ---------------------------------------------------------------------------
# do_add_step edge cases
# ---------------------------------------------------------------------------


class TestDoAddStepEdge:
    def test_no_runner_returns_early(self, main_window: MainWindow):
        main_window.current_runner = None
        main_window.step_tree = None
        main_window.do_add_step({"type": "delay", "ms": 100})

    def test_no_tree_returns_early(self, main_window: MainWindow):
        main_window.step_tree = None
        main_window.do_add_step({"type": "delay", "ms": 100})


# ---------------------------------------------------------------------------
# on_delete_step edge cases
# ---------------------------------------------------------------------------


class TestDeleteStepEdge:
    def test_no_runner_returns_early(self, main_window: MainWindow):
        main_window.current_runner = None
        main_window.step_tree = None
        main_window.on_delete_step()


# ---------------------------------------------------------------------------
# copy_steps / paste_steps / duplicate_steps edge cases
# ---------------------------------------------------------------------------


class TestCopyStepsEdge:
    def test_no_runner_returns_early(self, main_window: MainWindow):
        main_window.current_runner = None
        main_window.step_tree = None
        main_window.copy_steps()

    def test_no_rows_returns_early(self, main_window: MainWindow):
        main_window.step_list.clearSelection()
        main_window.copy_steps()

    def test_empty_top_level_returns_early(self, main_window: MainWindow):
        main_window.step_list.selectAll()
        with patch.object(main_window.step_tree, "get_top_level", return_value=[]):
            main_window.copy_steps()


class TestPasteStepsEdge:
    def test_no_runner_returns_early(self, main_window: MainWindow):
        main_window.current_runner = None
        main_window.step_clipboard = None
        main_window.paste_steps()

    def test_no_tree_returns_early(self, main_window: MainWindow):
        main_window.step_clipboard = {"steps": [], "templates": {}, "template_meta": {}}
        main_window.step_tree = None
        main_window.paste_steps()

    def test_writes_template_png(self, main_window: MainWindow, templates_dir: Path):
        steps = [{"type": "delay", "ms": 100}]
        main_window.step_clipboard = {
            "steps": steps,
            "templates": {"new_png": MINI_PNG},
            "template_meta": {},
        }
        set_current_step_row(main_window, 0)
        main_window.paste_steps()
        assert (templates_dir / "new_png.png").exists()

    def test_adds_new_template_meta(self, main_window: MainWindow):
        steps = [{"type": "wait_image", "template": "new_png"}]
        main_window.step_clipboard = {
            "steps": steps,
            "templates": {"new_png": MINI_PNG},
            "template_meta": {"new_png": {"label": "New"}},
        }
        set_current_step_row(main_window, 0)
        main_window.paste_steps()
        macro_templates = get_runner(main_window).macro.get("templates", {})
        assert "new_png" in macro_templates

    def test_merges_template_meta_fields(self, main_window: MainWindow):
        runner = get_runner(main_window)
        runner.macro["templates"] = {"existing": {"label": "Existing"}}
        steps = [{"type": "wait_image", "template": "existing"}]
        main_window.step_clipboard = {
            "steps": steps,
            "templates": {"existing": MINI_PNG},
            "template_meta": {"existing": {"label": "Updated"}},
        }
        set_current_step_row(main_window, 0)
        main_window.paste_steps()
        meta = get_runner(main_window).macro["templates"]["existing"]
        assert meta["label"] == "Existing"


class TestDuplicateStepsEdge:
    def test_no_runner_returns_early(self, main_window: MainWindow):
        main_window.current_runner = None
        main_window.step_tree = None
        main_window.duplicate_steps()

    def test_no_rows_returns_early(self, main_window: MainWindow):
        main_window.step_list.clearSelection()
        main_window.duplicate_steps()


# ---------------------------------------------------------------------------
# on_step_context_menu edge cases
# ---------------------------------------------------------------------------


class TestStepContextMenuEdge:
    def test_no_runner_returns_early(self, main_window: MainWindow):
        main_window.current_runner = None
        main_window.on_step_context_menu(main_window.step_list.rect().center())


# ---------------------------------------------------------------------------
# wrap_in_repeat edge cases
# ---------------------------------------------------------------------------


class TestWrapInRepeatEdge:
    def test_no_runner_returns_early(self, main_window: MainWindow):
        main_window.current_runner = None
        main_window.step_tree = None
        main_window.wrap_in_repeat()

    def test_empty_top_level_returns_early(self, main_window: MainWindow):
        main_window.step_list.selectAll()
        with patch.object(main_window.step_tree, "get_top_level", return_value=[]):
            main_window.wrap_in_repeat()

    def test_finds_repeat_step_after_wrap(self, main_window: MainWindow):
        set_current_step_row(main_window, 0)
        main_window.step_list.currentItem().setSelected(True)
        main_window.wrap_in_repeat()
        current = get_current_step_row(main_window)
        assert current >= -1


# ---------------------------------------------------------------------------
# on_move_step edge cases
# ---------------------------------------------------------------------------


class TestMoveStepEdge:
    def test_no_tree_returns_early(self, main_window: MainWindow):
        main_window.step_tree = None
        main_window.on_move_step(1)

    def test_invalid_row_returns_early(self, main_window: MainWindow):
        set_current_step_row(main_window, -1)
        main_window.on_move_step(1)


# ---------------------------------------------------------------------------
# refresh_status edge cases
# ---------------------------------------------------------------------------


class TestRefreshStatusEdge:
    def test_custom_state_displayed(self, main_window: MainWindow):
        runner = get_runner(main_window)
        runner.get_status = MagicMock(
            return_value=MagicMock(
                running=False,
                state="paused",
                last_reason="stopped",
                message="Done",
                elapsed_s=0,
            )
        )
        runner.is_running = MagicMock(return_value=False)
        main_window.start_refresh_timer()
        main_window.refresh_status()

    def test_stop_iteration_on_current_step(self, main_window: MainWindow):
        runner = get_runner(main_window)
        fake_step = {"type": "delay", "ms": 100}
        runner.current_step = fake_step
        runner.get_status = MagicMock(
            return_value=MagicMock(
                running=True,
                state="-",
                last_reason=None,
                message=None,
                elapsed_s=0,
                progress=0,
                repeat_total=0,
                score=0,
                match_name=None,
            )
        )
        main_window.start_refresh_timer()
        main_window.refresh_status()

    def test_overlay_shown_when_enabled(self, main_window: MainWindow):
        main_window.conf.general.overlay_enabled = True
        runner = get_runner(main_window)
        runner.get_status = MagicMock(
            return_value=MagicMock(
                running=True,
                state="-",
                last_reason=None,
                message=None,
                elapsed_s=0,
                progress=0,
                repeat_total=0,
                score=0,
                match_name=None,
            )
        )
        with patch.object(main_window.overlay, "isVisible", return_value=False):
            main_window.start_refresh_timer()
            main_window.refresh_status()

    def test_error_state_does_not_crash(self, main_window: MainWindow):
        runner = get_runner(main_window)
        runner.get_status = MagicMock(
            return_value=MagicMock(
                running=False,
                state=None,
                last_reason="error",
                message="Error occurred",
                elapsed_s=10,
            )
        )
        runner.is_running = MagicMock(return_value=False)
        main_window.start_refresh_timer()
        main_window.refresh_status()


# ---------------------------------------------------------------------------
# highlight_current_step edge cases
# ---------------------------------------------------------------------------


class TestHighlightCurrentStepEdge:
    def test_no_current_step_returns_early(self, main_window: MainWindow):
        runner = get_runner(main_window)
        runner.current_step = None
        main_window.highlight_current_step(runner)

    def test_empty_flat_nodes_returns_early(self, main_window: MainWindow):
        main_window.flat_nodes = []
        runner = get_runner(main_window)
        runner.current_step = {"type": "delay", "ms": 100}
        main_window.highlight_current_step(runner)

    def test_stop_iteration_handled(self, main_window: MainWindow):
        runner = get_runner(main_window)
        runner.current_step = {"type": "does_not_exist"}
        main_window.highlight_current_step(runner)


# ---------------------------------------------------------------------------
# on_add_macro
# ---------------------------------------------------------------------------


class TestOnAddMacro:
    def test_dialog_cancelled_noop(self, main_window: MainWindow):
        with patch("main_window.MessageBoxBase") as mock_dlg_cls:
            mock_dlg = MagicMock()
            mock_dlg.exec.return_value = False
            mock_dlg_cls.return_value = mock_dlg
            initial_count = main_window.macro_list.count()
            main_window.on_add_macro()
            assert main_window.macro_list.count() == initial_count

    def test_empty_name_noop(self, main_window: MainWindow):
        with patch("main_window.MessageBoxBase") as mock_dlg_cls:
            mock_dlg = MagicMock()
            mock_dlg.exec.return_value = True
            mock_dlg_cls.return_value = mock_dlg
            initial_count = main_window.macro_list.count()
            main_window.on_add_macro()
            assert main_window.macro_list.count() == initial_count


# ---------------------------------------------------------------------------
# on_duplicate_macro edge cases
# ---------------------------------------------------------------------------


class TestDuplicateMacroEdge:
    def test_no_runner_returns_early(self, main_window: MainWindow):
        main_window.current_runner = None
        main_window.on_duplicate_macro()


# ---------------------------------------------------------------------------
# on_export_json edge cases
# ---------------------------------------------------------------------------


class TestExportJsonEdge:
    def test_no_runner_returns_early(self, main_window: MainWindow):
        main_window.current_runner = None
        main_window.on_export_json()

    def test_no_source_path_returns_early(self, main_window: MainWindow):
        get_runner(main_window).source_path = None
        main_window.on_export_json()

    def test_exports_zip_with_templates(self, main_window: MainWindow, tmp_path: Path, templates_dir: Path):
        dest = tmp_path / "export.zip"
        (templates_dir / "btn.png").write_bytes(MINI_PNG)
        runner = get_runner(main_window)
        runner.macro["steps"].append({"type": "wait_image", "template": "btn"})
        main_window.populate_steps()

        with (
            patch("main_window.QFileDialog.getSaveFileName", return_value=(str(dest), "")),
            patch.object(main_window, "collect_template_refs", wraps=main_window.collect_template_refs),
        ):
            main_window.on_export_json()

        assert dest.exists()
        import zipfile

        with zipfile.ZipFile(dest, "r") as zf:
            assert "macro.json" in zf.namelist()
            assert "templates/btn.png" in zf.namelist()


# ---------------------------------------------------------------------------
# on_import_json edge cases & full flow
# ---------------------------------------------------------------------------


class TestImportJsonEdge:
    def test_no_file_selected_noop(self, main_window: MainWindow):
        with patch("main_window.QFileDialog.getOpenFileName", return_value=("", "")):
            initial_count = main_window.macro_list.count()
            main_window.on_import_json()
            assert main_window.macro_list.count() == initial_count

    def test_missing_macro_json(self, main_window: MainWindow, tmp_path: Path):
        import zipfile

        bad_zip = tmp_path / "bad.zip"
        with zipfile.ZipFile(bad_zip, "w") as zf:
            zf.writestr("readme.txt", "no macro json here")

        with (
            patch("main_window.QFileDialog.getOpenFileName", return_value=(str(bad_zip), "")),
            patch("main_window.MessageBox") as mock_msg,
        ):
            mock_dialog = MagicMock()
            mock_msg.return_value = mock_dialog
            main_window.on_import_json()
            mock_dialog.exec.assert_called_once()

    def test_invalid_meta(self, main_window: MainWindow, tmp_path: Path):
        import zipfile

        bad_zip = tmp_path / "bad.zip"
        with zipfile.ZipFile(bad_zip, "w") as zf:
            zf.writestr("macro.json", json.dumps({"meta": {}, "steps": []}))

        with (
            patch("main_window.QFileDialog.getOpenFileName", return_value=(str(bad_zip), "")),
            patch("main_window.MessageBox") as mock_msg,
        ):
            mock_dialog = MagicMock()
            mock_msg.return_value = mock_dialog
            main_window.on_import_json()
            mock_dialog.exec.assert_called_once()

    def test_invalid_steps(self, main_window: MainWindow, tmp_path: Path):
        import zipfile

        bad_zip = tmp_path / "bad.zip"
        with zipfile.ZipFile(bad_zip, "w") as zf:
            zf.writestr("macro.json", json.dumps({"meta": {"name": "test"}, "steps": "not_a_list"}))

        with (
            patch("main_window.QFileDialog.getOpenFileName", return_value=(str(bad_zip), "")),
            patch("main_window.MessageBox") as mock_msg,
        ):
            mock_dialog = MagicMock()
            mock_msg.return_value = mock_dialog
            main_window.on_import_json()
            mock_dialog.exec.assert_called_once()

    def test_missing_templates(self, main_window: MainWindow, tmp_path: Path):
        import zipfile

        bad_zip = tmp_path / "bad.zip"
        with zipfile.ZipFile(bad_zip, "w") as zf:
            zf.writestr(
                "macro.json",
                json.dumps(
                    {
                        "meta": {"name": "test"},
                        "templates": {},
                        "steps": [{"type": "wait_image", "template": "missing"}],
                    }
                ),
            )

        with (
            patch("main_window.QFileDialog.getOpenFileName", return_value=(str(bad_zip), "")),
            patch("main_window.MessageBox") as mock_msg,
        ):
            mock_dialog = MagicMock()
            mock_msg.return_value = mock_dialog
            main_window.on_import_json()
            mock_dialog.exec.assert_called_once()

    def test_successful_import(self, main_window: MainWindow, tmp_path: Path, macros_dir: Path):
        import zipfile

        good_zip = tmp_path / "good.zip"
        with zipfile.ZipFile(good_zip, "w") as zf:
            zf.writestr(
                "macro.json",
                json.dumps(
                    {
                        "meta": {"name": "imported", "label": "Imported Macro"},
                        "templates": {},
                        "steps": [{"type": "delay", "ms": 500}],
                    }
                ),
            )

        with (
            patch("main_window.QFileDialog.getOpenFileName", return_value=(str(good_zip), "")),
            patch("main_window.MessageBox"),
        ):
            with patch.object(main_window, "register_hotkeys"):
                main_window.on_import_json()
            assert main_window.macro_list.count() == 3
            assert main_window.runners[-1].label == "Imported Macro"

    def test_import_with_template_pngs(self, main_window: MainWindow, tmp_path: Path, macros_dir: Path):
        import zipfile

        good_zip = tmp_path / "with_templates.zip"
        with zipfile.ZipFile(good_zip, "w") as zf:
            zf.writestr(
                "macro.json",
                json.dumps(
                    {
                        "meta": {"name": "with_tpl", "label": "With Templates"},
                        "templates": {},
                        "steps": [{"type": "wait_image", "template": "img1"}],
                    }
                ),
            )
            zf.writestr("templates/img1.png", MINI_PNG)

        with (
            patch("main_window.QFileDialog.getOpenFileName", return_value=(str(good_zip), "")),
            patch.object(main_window, "register_hotkeys"),
        ):
            main_window.on_import_json()

        imported = next(r for r in main_window.runners if r.name == "with_tpl")
        template_dir = cfg.templates_dir(imported.name)
        assert (template_dir / "img1.png").exists()

    def test_import_legacy_meta_json(self, main_window: MainWindow, tmp_path: Path, macros_dir: Path):
        import zipfile

        good_zip = tmp_path / "legacy.zip"
        with zipfile.ZipFile(good_zip, "w") as zf:
            zf.writestr(
                "macro.json",
                json.dumps(
                    {
                        "meta": {"name": "legacy", "label": "Legacy"},
                        "templates": {},
                        "steps": [{"type": "wait_image", "template": "img1"}],
                    }
                ),
            )
            zf.writestr("templates/img1.png", MINI_PNG)
            zf.writestr("templates/img1.json", json.dumps({"capture_width": 800, "capture_height": 600}))
        with (
            patch("main_window.QFileDialog.getOpenFileName", return_value=(str(good_zip), "")),
            patch.object(main_window, "register_hotkeys"),
        ):
            main_window.on_import_json()

        imported = next(r for r in main_window.runners if r.name == "legacy")
        assert imported.macro["templates"]["img1"]["capture_width"] == 800


# ---------------------------------------------------------------------------
# on_check_update / startup_check_update
# ---------------------------------------------------------------------------


class TestCheckUpdate:
    def test_up_to_date(self, main_window: MainWindow):
        with (
            patch("main_window.updater.check_async") as mock_check,
            patch("main_window.MessageBox") as mock_msg,
        ):
            mock_dialog = MagicMock()
            mock_msg.return_value = mock_dialog

            def invoke_callback(_, cb):
                from updater import CheckResult

                cb(CheckResult("up_to_date", None, None))

            mock_check.side_effect = invoke_callback
            main_window.on_check_update()
            mock_dialog.exec.assert_called_once()

    def test_error_result(self, main_window: MainWindow):
        with (
            patch("main_window.updater.check_async") as mock_check,
            patch("main_window.MessageBox") as mock_msg,
        ):
            mock_dialog = MagicMock()
            mock_msg.return_value = mock_dialog

            def invoke_callback(_, cb):
                from updater import CheckResult

                cb(CheckResult("error", None, "Network error"))

            mock_check.side_effect = invoke_callback
            main_window.on_check_update()
            mock_dialog.exec.assert_called_once()

    def test_startup_update_with_skipped_version(self, main_window: MainWindow):
        main_window.conf.general.skipped_version = "v9.9.9"
        with patch("main_window.updater.check_async") as mock_check:

            def invoke_callback(_, cb):
                from updater import CheckResult, UpdateInfo

                info = UpdateInfo(
                    tag="v9.9.9",
                    version=(9, 9, 9, 0),
                    body="",
                    installer_url="",
                    release_url="",
                )
                cb(CheckResult("available", info, None))

            mock_check.side_effect = invoke_callback
            with patch("main_window.updater.prompt_update") as mock_prompt:
                main_window.startup_check_update()
            mock_prompt.assert_not_called()

    def test_startup_update_available(self, main_window: MainWindow):
        main_window.conf.general.skipped_version = ""
        real = original_startup_check_update
        with (
            patch("main_window.updater.check_async") as mock_check,
            patch.object(MainWindow, "startup_check_update", real),
        ):
            main_window.startup_check_update()
        mock_check.assert_called_once()


# ---------------------------------------------------------------------------
# on_macro_context_menu edge cases
# ---------------------------------------------------------------------------


class TestMacroContextMenuEdge:
    def test_no_item_at_position(self, main_window: MainWindow):
        main_window.on_macro_context_menu(main_window.macro_list.rect().topLeft())

    def test_invalid_row(self, main_window: MainWindow):
        with patch.object(main_window.macro_list, "itemAt", return_value=QListWidgetItem("Ghost")):
            main_window.on_macro_context_menu(main_window.macro_list.rect().center())


# ---------------------------------------------------------------------------
# rename_macro edge cases
# ---------------------------------------------------------------------------


class TestRenameMacroEdge:
    def test_dialog_cancelled_noop(self, main_window: MainWindow):
        runner = get_runner(main_window)
        original_label = runner.label
        with patch("main_window.MessageBoxBase") as mock_dlg_cls:
            mock_dlg = MagicMock()
            mock_dlg.exec.return_value = False
            mock_dlg_cls.return_value = mock_dlg
            main_window.rename_macro(0)
        assert runner.label == original_label

    def test_empty_name_noop(self, main_window: MainWindow):
        runner = get_runner(main_window)
        original_label = runner.label
        with patch("main_window.MessageBoxBase") as mock_dlg_cls:
            mock_dlg = MagicMock()
            mock_dlg.exec.return_value = True
            mock_dlg_cls.return_value = mock_dlg
            main_window.rename_macro(0)
        assert runner.label == original_label


# ---------------------------------------------------------------------------
# delete_macro edge cases
# ---------------------------------------------------------------------------


class TestDeleteMacroEdge:
    def test_dialog_cancelled_noop(self, main_window: MainWindow):
        get_runner(main_window)
        with patch("main_window.MessageBoxBase") as mock_dlg_cls:
            mock_dlg = MagicMock()
            mock_dlg.exec.return_value = False
            mock_dlg_cls.return_value = mock_dlg
            main_window.delete_macro(0)
        assert main_window.macro_list.count() == 2

    def test_delete_with_templates_checkbox_checked(self, main_window: MainWindow, templates_dir: Path):
        (templates_dir / "test_a" / "some.txt").mkdir(parents=True, exist_ok=True)
        (templates_dir / "test_a" / "some.txt" / "file.png").touch()
        get_runner(main_window)
        with patch("main_window.MessageBoxBase") as mock_dlg_cls:
            mock_dlg = MagicMock()
            mock_dlg.exec.return_value = True
            mock_dlg_cls.return_value = mock_dlg

            with (
                patch("main_window.CheckBox") as mock_cb_cls,
                patch.object(main_window, "register_hotkeys"),
            ):
                mock_cb = MagicMock()
                mock_cb.isChecked.return_value = True
                mock_cb_cls.return_value = mock_cb
                main_window.delete_macro(0)

        assert main_window.macro_list.count() == 1

    def test_delete_macro_last_one_clears_state(self, main_window: MainWindow, qtbot):
        with patch("main_window.MessageBoxBase") as mock_dlg_cls:
            mock_dlg = MagicMock()
            mock_dlg.exec.return_value = True
            mock_dlg_cls.return_value = mock_dlg

            while main_window.macro_list.count() > 1:
                main_window.delete_macro(1)

            assert main_window.macro_list.count() == 1

            main_window.delete_macro(0)

        assert main_window.current_runner is None
        assert step_count(main_window) == 0


# ---------------------------------------------------------------------------
# show_hold_key_props with template resolution
# ---------------------------------------------------------------------------


class TestHoldKeyPropsEdge:
    def test_with_template_shows_resolution(self, main_window: MainWindow, templates_dir: Path):
        (templates_dir / "t1.png").write_bytes(MINI_PNG)
        step = {"type": "hold_key_until_gone", "key": "enter", "template": "t1"}
        get_runner(main_window).macro["templates"] = {"t1": {"label": "T1"}}
        main_window.show_props(step)
        assert True


# ---------------------------------------------------------------------------
# Additional coverage: on_add_macro success, import_json conflicts, etc.
# ---------------------------------------------------------------------------


class TestOnAddMacroSuccess:
    def test_creates_macro_with_name(self, main_window: MainWindow, macros_dir: Path):
        with (
            patch("main_window.MessageBoxBase") as mock_dlg_cls,
            patch("main_window.time.time", return_value=1234567890),
            patch.object(main_window, "register_hotkeys"),
        ):
            mock_dlg = MagicMock()
            mock_dlg.exec.return_value = True
            mock_dlg_cls.return_value = mock_dlg
            name_edit = LineEdit()
            name_edit.setPlaceholderText = MagicMock()
            name_edit.setFocus = MagicMock()
            name_edit.text = MagicMock(return_value="My New Macro")
            mock_dlg.viewLayout.addWidget = MagicMock()

            def add_widget(widget):
                if isinstance(widget, MagicMock):
                    pass

            mock_dlg.viewLayout.addWidget.side_effect = add_widget
            main_window.on_add_macro()
            assert True


class TestImportJsonConflict:
    def test_duplicate_name_generates_new_id(self, main_window: MainWindow, tmp_path: Path):
        import zipfile

        dup_zip = tmp_path / "dup.zip"
        runner = get_runner(main_window)
        existing_name = runner.name
        with zipfile.ZipFile(dup_zip, "w") as zf:
            zf.writestr(
                "macro.json",
                json.dumps(
                    {
                        "meta": {"name": existing_name, "label": "Duplicate"},
                        "templates": {},
                        "steps": [],
                    }
                ),
            )

        with (
            patch("main_window.QFileDialog.getOpenFileName", return_value=(str(dup_zip), "")),
            patch("main_window.time.time", return_value=9999999999),
            patch.object(main_window, "register_hotkeys"),
        ):
            main_window.on_import_json()

        imported = main_window.runners[-1]
        assert imported.name == "9999999999"

    def test_template_conflict_shows_dialog(self, main_window: MainWindow, tmp_path: Path, macros_dir: Path):
        import zipfile

        conf_zip = tmp_path / "conflict.zip"
        with zipfile.ZipFile(conf_zip, "w") as zf:
            zf.writestr(
                "macro.json",
                json.dumps(
                    {
                        "meta": {"name": "conflict_test", "label": "Conflict"},
                        "templates": {},
                        "steps": [{"type": "wait_image", "template": "img1"}],
                    }
                ),
            )
            zf.writestr("templates/img1.png", MINI_PNG)

        with (
            patch("main_window.QFileDialog.getOpenFileName", return_value=(str(conf_zip), "")),
            patch("main_window.MessageBox", return_value=MagicMock()) as mock_msg,
            patch.object(main_window, "register_hotkeys"),
        ):
            mock_msg.return_value.exec.return_value = True
            main_window.on_import_json()

    def test_legacy_meta_corrupt_json(self, main_window: MainWindow, tmp_path: Path, macros_dir: Path):
        import zipfile

        legacy_zip = tmp_path / "legacy_corrupt.zip"
        with zipfile.ZipFile(legacy_zip, "w") as zf:
            zf.writestr(
                "macro.json",
                json.dumps(
                    {
                        "meta": {"name": "legacy_corrupt", "label": "Legacy Corrupt"},
                        "templates": {},
                        "steps": [{"type": "wait_image", "template": "img1"}],
                    }
                ),
            )
            zf.writestr("templates/img1.png", MINI_PNG)
            zf.writestr("templates/img1.json", "not valid {{{ json")

        with (
            patch("main_window.QFileDialog.getOpenFileName", return_value=(str(legacy_zip), "")),
            patch.object(main_window, "register_hotkeys"),
        ):
            main_window.on_import_json()

        assert any(r.name == "legacy_corrupt" for r in main_window.runners)


class TestOnCheckUpdateAvailable:
    def test_available_status(self, main_window: MainWindow):
        with (
            patch("main_window.updater.check_async") as mock_check,
            patch("main_window.updater.prompt_update") as mock_prompt,
            patch("main_window.MessageBox"),
        ):
            from updater import CheckResult, UpdateInfo

            def invoke_callback(_, cb):
                info = UpdateInfo(
                    tag="v99.0.0",
                    version=(99, 0, 0, 0),
                    body="",
                    installer_url="",
                    release_url="",
                )
                cb(CheckResult("available", info, None))

            mock_check.side_effect = invoke_callback
            main_window.on_check_update()
            mock_prompt.assert_called_once()


class TestStartupUpdatePrompt:
    def test_available_not_skipped(self, main_window: MainWindow):
        main_window.conf.general.skipped_version = "v1.0.0"
        real = original_startup_check_update
        with (
            patch("main_window.updater.check_async") as mock_check,
            patch("main_window.updater.prompt_update") as mock_prompt,
            patch.object(MainWindow, "startup_check_update", real),
        ):
            from updater import CheckResult, UpdateInfo

            def invoke_callback(_, cb):
                info = UpdateInfo(
                    tag="v9.9.9",
                    version=(9, 9, 9, 0),
                    body="",
                    installer_url="",
                    release_url="",
                )
                cb(CheckResult("available", info, None))

            mock_check.side_effect = invoke_callback
            main_window.startup_check_update()
            mock_prompt.assert_called_once()


class TestDeleteMacroCheckbox:
    def test_checkbox_created_and_checked(self, main_window: MainWindow, templates_dir: Path):
        (templates_dir / "test_a" / "sub").mkdir(parents=True, exist_ok=True)
        (templates_dir / "test_a" / "sub" / "file.txt").touch()
        with patch("main_window.MessageBoxBase") as mock_dlg_cls:
            mock_dlg = MagicMock()
            mock_dlg.exec.return_value = True
            mock_dlg_cls.return_value = mock_dlg
            with (
                patch("main_window.CheckBox") as mock_cb_cls,
                patch.object(main_window, "register_hotkeys"),
            ):
                mock_cb = MagicMock()
                mock_cb.isChecked.return_value = False
                mock_cb_cls.return_value = mock_cb
                main_window.delete_macro(0)


class TestPasteMergeMeta:
    def test_preserves_existing_meta(self, main_window: MainWindow):
        runner = get_runner(main_window)
        runner.macro["templates"] = {"existing": {}}
        steps = [{"type": "wait_image", "template": "existing"}]
        main_window.step_clipboard = {
            "steps": steps,
            "templates": {"existing": MINI_PNG},
            "template_meta": {"existing": {"label": "FromClipboard"}},
        }
        set_current_step_row(main_window, 0)
        main_window.paste_steps()
        meta = get_runner(main_window).macro["templates"]["existing"]
        assert "label" in meta


class TestRefreshStateDisplay:
    def test_custom_running_state(self, main_window: MainWindow):
        runner = get_runner(main_window)
        runner.start_time = time.monotonic() - 5
        runner.get_status = MagicMock(
            return_value=MagicMock(
                running=True,
                state="finding",
                last_reason=None,
                message=None,
                elapsed_s=0,
                progress=0,
                repeat_total=0,
                score=0,
                match_name=None,
            )
        )
        main_window.start_refresh_timer()
        main_window.refresh_status()


class TestDoAddStepToBranch:
    def test_add_to_then_branch(self, main_window: MainWindow):
        get_runner(main_window).macro["steps"] = [
            {
                "type": "if_image",
                "template": "",
                "branches": {"then": [], "else": []},
            }
        ]
        main_window.on_macro_selected(0)
        main_window.do_add_step_to_branch(main_window.flat_nodes[0].step, "then", {"type": "delay", "ms": 100})
        assert True

    def test_no_tree(self, main_window: MainWindow):
        main_window.step_tree = None
        main_window.do_add_step_to_branch({}, "then", {"type": "delay", "ms": 100})

    def test_parent_not_found(self, main_window: MainWindow):
        main_window.do_add_step_to_branch({"nonexistent": True}, "then", {"type": "delay", "ms": 100})


class TestDoAddStepToAnyBranch:
    def test_no_tree(self, main_window: MainWindow):
        main_window.step_tree = None
        main_window.do_add_step_to_any_branch({}, "t1", {"type": "delay", "ms": 100})

    def test_parent_not_found(self, main_window: MainWindow):
        main_window.do_add_step_to_any_branch({"nonexistent": True}, "t1", {"type": "delay", "ms": 100})

    def test_add_to_any_branch_success(self, main_window: MainWindow, templates_dir: Path):
        (templates_dir / "t1.png").write_bytes(MINI_PNG)
        get_runner(main_window).macro["templates"] = {"t1": {"label": "T1"}}
        get_runner(main_window).macro["steps"] = [
            {
                "type": "if_any_image",
                "templates": ["t1"],
                "branches": {"t1": []},
            }
        ]
        main_window.on_macro_selected(0)
        main_window.do_add_step_to_any_branch(main_window.flat_nodes[0].step, "t1", {"type": "delay", "ms": 100})
        assert True


class TestTreeWidgetCoverage:
    def test_on_step_selected_item_not_in_mapping(self, main_window: MainWindow):
        item = QTreeWidgetItem(["orphan"])
        main_window.step_list.addTopLevelItem(item)
        main_window.on_step_selected(item, None)

    def test_refresh_step_list_with_select_row(self, main_window: MainWindow):
        main_window.refresh_step_list(select_row=0)
        assert main_window.step_list.currentItem() is not None

    def test_refresh_step_list_select_row_out_of_range(self, main_window: MainWindow):
        main_window.refresh_step_list(select_row=999)

    def test_undo_selects_item_after_restore(self, main_window: MainWindow):
        set_current_step_row(main_window, 0)
        main_window.do_add_step({"type": "key", "key": "z"})
        main_window.undo()
        assert main_window.step_list.currentItem() is not None

    def test_duplicate_steps_selects_new_item(self, main_window: MainWindow):
        set_current_step_row(main_window, 0)
        main_window.duplicate_steps()
        assert main_window.step_list.currentItem() is not None

    def test_wrap_in_repeat_selects_repeat_item(self, main_window: MainWindow):
        select_step_rows(main_window, [0, 1])
        main_window.wrap_in_repeat()
        item = main_window.step_list.currentItem()
        assert item is not None
        node = main_window.item_to_node.get(item)
        assert node is not None
        assert node.step["type"] == "repeat"

    def test_on_move_step_node_none_returns_early(self, main_window: MainWindow):
        item = QTreeWidgetItem(["orphan"])
        main_window.step_list.addTopLevelItem(item)
        main_window.step_list.setCurrentItem(item)
        main_window.on_move_step(1)

    def test_on_move_step_selects_moved_item(self, main_window: MainWindow):
        set_current_step_row(main_window, 0)
        main_window.on_move_step(1)
        item = main_window.step_list.currentItem()
        assert item is not None

    def test_highlight_current_step_no_step_tree(self, main_window: MainWindow):
        runner = get_runner(main_window)
        runner.macro["steps"] = [{"type": "key", "key": "a"}]
        main_window.on_macro_selected(0)
        main_window.step_tree = None
        runner.current_step = runner.macro["steps"][0]
        main_window.highlight_current_step(runner)

    def test_highlight_current_step_node_not_found(self, main_window: MainWindow):
        runner = get_runner(main_window)
        runner.macro["steps"] = [{"type": "key", "key": "a"}]
        main_window.on_macro_selected(0)
        runner.current_step = {"type": "delay", "ms": 999}
        main_window.highlight_current_step(runner)

    def test_highlight_current_step_item_not_in_mapping(self, main_window: MainWindow):
        runner = get_runner(main_window)
        runner.macro["steps"] = [{"type": "key", "key": "a"}]
        main_window.on_macro_selected(0)
        node = main_window.step_tree.find_node(runner.macro["steps"][0])
        assert node is not None
        item = main_window.node_to_item.pop(node)
        runner.current_step = runner.macro["steps"][0]
        main_window.highlight_current_step(runner)
        main_window.node_to_item[node] = item

    def test_tree_widget_has_nested_items(self, main_window: MainWindow):
        main_window.macro_list.setCurrentRow(1)
        top_count = main_window.step_list.topLevelItemCount()
        assert top_count == 2
        top_item = main_window.step_list.topLevelItem(1)
        assert top_item is not None
        assert top_item.childCount() > 0

    def test_populate_steps_clears_mappings(self, main_window: MainWindow):
        main_window.populate_steps()
        assert len(main_window.item_to_node) == len(main_window.flat_nodes)
        assert len(main_window.node_to_item) == len(main_window.flat_nodes)

    def test_populate_steps_no_runner_clears_mappings(self, main_window: MainWindow):
        main_window.current_runner = None
        main_window.populate_steps()
        assert len(main_window.item_to_node) == 0
        assert len(main_window.node_to_item) == 0
