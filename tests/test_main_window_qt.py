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
from PySide6.QtWidgets import QListWidgetItem

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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


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
        assert main_window.step_list.count() == 2

    def test_step_count_macro_b(self, main_window: MainWindow):
        main_window.macro_list.setCurrentRow(1)
        assert main_window.step_list.count() == 4  # key + repeat + key + delay

    def test_step_selection(self, main_window: MainWindow):
        main_window.step_list.setCurrentRow(0)
        assert main_window.step_list.currentRow() == 0

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
        main_window.step_list.setCurrentRow(0)
        main_window.on_delete_step()
        assert main_window.step_list.count() == 1
        assert len(get_runner(main_window).macro["steps"]) == 1

    def test_delete_last_step(self, main_window: MainWindow):
        main_window.step_list.setCurrentRow(0)
        main_window.on_delete_step()
        main_window.step_list.setCurrentRow(0)
        main_window.on_delete_step()
        assert main_window.step_list.count() == 0
        assert len(get_runner(main_window).macro["steps"]) == 0

    def test_add_step(self, main_window: MainWindow):
        initial_count = main_window.step_list.count()
        step = {"type": "key", "key": "escape"}
        main_window.do_add_step(step)
        assert main_window.step_list.count() == initial_count + 1
        assert get_runner(main_window).macro["steps"][-1]["key"] == "escape"

    def test_add_step_after_selected(self, main_window: MainWindow):
        main_window.step_list.setCurrentRow(0)
        step = {"type": "delay", "ms": 200}
        main_window.do_add_step(step)
        assert main_window.step_list.count() == 3
        steps = get_runner(main_window).macro["steps"]
        assert steps[1]["type"] == "delay"

    def test_add_multiple_steps_selects_latest(self, main_window: MainWindow):
        main_window.step_list.setCurrentRow(main_window.step_list.count() - 1)
        for _ in range(5):
            before = main_window.step_list.currentRow()
            step = {"type": "key", "key": "a"}
            main_window.do_add_step(step)
            assert main_window.step_list.currentRow() == before + 1

    def test_move_step_down(self, main_window: MainWindow):
        main_window.step_list.setCurrentRow(0)
        steps_before = [s["type"] for s in get_runner(main_window).macro["steps"]]
        main_window.on_move_step(1)
        steps_after = [s["type"] for s in get_runner(main_window).macro["steps"]]
        assert steps_before == ["key", "delay"]
        assert steps_after == ["delay", "key"]

    def test_move_step_up(self, main_window: MainWindow):
        main_window.step_list.setCurrentRow(1)
        main_window.on_move_step(-1)
        steps_after = [s["type"] for s in get_runner(main_window).macro["steps"]]
        assert steps_after == ["delay", "key"]

    def test_duplicate_step(self, main_window: MainWindow):
        main_window.step_list.setCurrentRow(0)
        main_window.duplicate_steps()
        assert main_window.step_list.count() == 3
        steps = get_runner(main_window).macro["steps"]
        assert steps[0]["key"] == steps[1]["key"]

    def test_copy_paste_step(self, main_window: MainWindow):
        main_window.step_list.setCurrentRow(0)
        main_window.copy_steps()
        main_window.step_list.setCurrentRow(1)
        main_window.paste_steps()
        assert main_window.step_list.count() == 3
        steps = get_runner(main_window).macro["steps"]
        assert steps[2]["type"] == "key"

    def test_cut_step(self, main_window: MainWindow):
        main_window.step_list.setCurrentRow(0)
        main_window.cut_steps()
        assert main_window.step_list.count() == 1
        assert hasattr(main_window, "step_clipboard")
        assert len(main_window.step_clipboard["steps"]) == 1

    def test_wrap_in_repeat(self, main_window: MainWindow):
        main_window.step_list.setCurrentRow(0)
        model = main_window.step_list.model()
        selection_model = main_window.step_list.selectionModel()
        clear_and_select = selection_model.SelectionFlag.ClearAndSelect | selection_model.SelectionFlag.Rows
        select = selection_model.SelectionFlag.Select | selection_model.SelectionFlag.Rows
        selection_model.select(model.index(0), clear_and_select)  # type: ignore
        selection_model.select(model.index(1), select)  # type: ignore
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
        main_window.step_list.setCurrentRow(0)
        main_window.on_delete_step()
        assert main_window.step_list.count() == 1
        main_window.undo()
        assert main_window.step_list.count() == 2

    def test_redo_after_undo(self, main_window: MainWindow):
        main_window.step_list.setCurrentRow(0)
        main_window.on_delete_step()
        main_window.undo()
        main_window.redo()
        assert main_window.step_list.count() == 1

    def test_undo_button_state(self, main_window: MainWindow):
        assert not main_window.btn_undo.isEnabled()
        main_window.step_list.setCurrentRow(0)
        main_window.on_delete_step()
        assert main_window.btn_undo.isEnabled()


# ---------------------------------------------------------------------------
# Empty state tests
# ---------------------------------------------------------------------------


class TestEmptyStates:
    def test_empty_macro_shows_hint(self, main_window: MainWindow):
        main_window.macro_list.setCurrentRow(0)
        main_window.step_list.setCurrentRow(0)
        main_window.on_delete_step()
        main_window.step_list.setCurrentRow(0)
        main_window.on_delete_step()
        assert main_window.step_list.count() == 0
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
        main_window.step_list.setCurrentRow(0)
        assert main_window.prop_fields_layout.count() > 0

    def test_selecting_different_step_updates_props(self, main_window: MainWindow):
        main_window.step_list.setCurrentRow(0)
        main_window.step_list.setCurrentRow(1)
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
        main_window.step_list.setCurrentRow(0)
        step = get_runner(main_window).macro["steps"][0]
        step["ms"] = 100
        edit = MagicMock()
        edit.text.return_value = "250"
        main_window.on_prop_edit(step, "ms", edit)
        assert step["ms"] == 250

    def test_edit_invalid_numeric_ignored(self, main_window: MainWindow):
        main_window.step_list.setCurrentRow(0)
        step = get_runner(main_window).macro["steps"][0]
        step["ms"] = 100
        edit = MagicMock()
        edit.text.return_value = "not_a_number"
        main_window.on_prop_edit(step, "ms", edit)
        assert step["ms"] == 100

    def test_edit_hold_ms_field(self, main_window: MainWindow):
        main_window.step_list.setCurrentRow(0)
        step = get_runner(main_window).macro["steps"][0]
        edit = MagicMock()
        edit.text.return_value = "150"
        main_window.on_prop_edit(step, "hold_ms", edit)
        assert step["hold_ms"] == 150

    def test_edit_key_field(self, main_window: MainWindow):
        main_window.step_list.setCurrentRow(0)
        step = get_runner(main_window).macro["steps"][0]
        edit = MagicMock()
        edit.text.return_value = "space"
        main_window.on_prop_edit(step, "key", edit)
        assert step["key"] == "space"

    def test_prop_bool_sets_value(self, main_window: MainWindow):
        main_window.step_list.setCurrentRow(0)
        step = get_runner(main_window).macro["steps"][0]
        step["skip"] = False
        main_window.on_prop_bool(step, "skip", True)
        assert step["skip"] is True

    def test_prop_bool_skip_repeat_propagates(self, main_window: MainWindow):
        main_window.macro_list.setCurrentRow(1)
        main_window.step_list.setCurrentRow(1)
        step = get_runner(main_window).macro["steps"][1]
        assert step["type"] == "repeat"
        step["steps"] = [{"type": "key", "key": "a"}, {"type": "delay", "ms": 100}]
        main_window.on_prop_bool(step, "skip", True)
        assert step["skip"] is True
        for child in step["steps"]:
            assert child["skip"] is True

    def test_combo_edit(self, main_window: MainWindow):
        main_window.step_list.setCurrentRow(0)
        step = get_runner(main_window).macro["steps"][0]
        main_window.on_combo_edit(step, "key", "escape")
        assert step["key"] == "escape"

    def test_threshold_changed(self, main_window: MainWindow):
        main_window.step_list.setCurrentRow(0)
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
        main_window.step_list.setCurrentRow(0)
        step = runner.macro["steps"][0]
        main_window.on_delete_template(step)
        assert step["template"] == ""

    def test_rename_template_updates_label(self, main_window: MainWindow):
        runner = get_runner(main_window)
        runner.macro["steps"] = [{"type": "wait_image", "template": "btn"}]
        runner.macro["templates"] = {"btn": {"label": "Button"}}
        main_window.on_macro_selected(0)
        main_window.step_list.setCurrentRow(0)
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
        main_window.step_list.setCurrentRow(0)
        step = runner.macro["steps"][0]
        main_window.show_props(step)
        assert main_window.prop_fields_layout.count() > 0

    def test_if_image_props(self, main_window: MainWindow):
        runner = get_runner(main_window)
        runner.macro["steps"] = [{"type": "if_image", "template": "cond", "then": [], "else": []}]
        main_window.on_macro_selected(0)
        main_window.step_list.setCurrentRow(0)
        step = runner.macro["steps"][0]
        main_window.show_props(step)
        assert main_window.prop_fields_layout.count() > 0

    def test_grid_nav_props(self, main_window: MainWindow):
        runner = get_runner(main_window)
        runner.macro["steps"] = [{"type": "grid_nav", "rows": 3, "start": 0, "on_next_row": [], "on_next_col": []}]
        main_window.on_macro_selected(0)
        main_window.step_list.setCurrentRow(0)
        step = runner.macro["steps"][0]
        main_window.show_props(step)
        assert main_window.prop_fields_layout.count() > 0

    def test_hold_key_props(self, main_window: MainWindow):
        runner = get_runner(main_window)
        runner.macro["steps"] = [{"type": "hold_key_until_gone", "key": "w", "template": "", "load_delay_ms": 2000}]
        main_window.on_macro_selected(0)
        main_window.step_list.setCurrentRow(0)
        step = runner.macro["steps"][0]
        main_window.show_props(step)
        assert main_window.prop_fields_layout.count() > 0

    def test_if_any_image_props(self, main_window: MainWindow):
        runner = get_runner(main_window)
        runner.macro["steps"] = [{"type": "if_any_image", "templates": ["a"], "branches": {"a": []}}]
        main_window.on_macro_selected(0)
        main_window.step_list.setCurrentRow(0)
        step = runner.macro["steps"][0]
        main_window.show_props(step)
        assert main_window.prop_fields_layout.count() > 0

    def test_show_props_skip_disabled_for_child_of_skipped_repeat(self, main_window: MainWindow):
        runner = get_runner(main_window)
        runner.macro["steps"] = [
            {"type": "repeat", "count": 1, "skip": True, "steps": [{"type": "key", "key": "a"}]},
        ]
        main_window.on_macro_selected(0)
        main_window.step_list.setCurrentRow(1)
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
        with patch.object(main_window, "_mutate_steps") as mock_mutate:
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
        with patch.object(main_window, "_mutate_steps") as mock_mutate:
            main_window.on_key_step_capture(event, edit, step)
        assert step["key"] == "a"
        assert edit.text() == "a"
        mock_mutate.assert_called_once()

    def test_on_key_step_capture_escape(self, main_window: MainWindow):
        edit = LineEdit()
        step = {"type": "key", "key": "a"}
        event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
        with patch.object(main_window, "_mutate_steps") as mock_mutate:
            main_window.on_key_step_capture(event, edit, step)
        assert step["key"] == ""
        assert edit.text() == ""
        mock_mutate.assert_called_once()

    def test_on_key_step_cleared(self, main_window: MainWindow):
        step = {"type": "key", "key": "a"}
        with patch.object(main_window, "_mutate_steps") as mock_mutate:
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
            patch.object(main_window, "_mutate_steps"),
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
            patch.object(main_window, "_mutate_steps"),
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
        with patch.object(main_window, "_mutate_steps") as mock_mutate:
            main_window.on_rename_template(step, edit)
        assert runner.macro["templates"]["btn"]["label"] == "Submit"
        mock_mutate.assert_called_once()

    def test_on_delete_template(self, main_window: MainWindow, templates_dir: Path):
        old = templates_dir / "btn.png"
        old.write_bytes(MINI_PNG)
        step = {"type": "wait_image", "template": "btn"}
        with (
            patch.object(main_window, "sync_macro_templates"),
            patch.object(main_window, "_mutate_steps") as mock_mutate,
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
        with patch.object(main_window, "_mutate_steps") as mock_mutate:
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
            patch.object(main_window, "_mutate_steps") as mock_mutate,
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
        with patch.object(main_window, "sync_macro_templates"), patch.object(main_window, "_mutate_steps"):
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
        model = main_window.step_list.model()
        selection_model = main_window.step_list.selectionModel()
        clear_and_select = selection_model.SelectionFlag.ClearAndSelect | selection_model.SelectionFlag.Rows
        select = selection_model.SelectionFlag.Select | selection_model.SelectionFlag.Rows
        selection_model.select(model.index(0), clear_and_select)
        selection_model.select(model.index(2), select)
        main_window.on_delete_step()
        keys = [s["key"] for s in runner.macro["steps"]]
        assert keys == ["b"]

    def test_paste_steps_with_templates(self, main_window: MainWindow, templates_dir: Path):
        (templates_dir / "btn.png").write_bytes(MINI_PNG)
        runner = get_runner(main_window)
        runner.macro["steps"] = [{"type": "wait_image", "template": "btn"}]
        runner.macro["templates"] = {"btn": {"label": "Button"}}
        main_window.on_macro_selected(0)
        main_window.step_list.setCurrentRow(0)
        main_window.copy_steps()
        main_window.step_list.clearSelection()
        main_window.paste_steps()
        assert len(runner.macro["steps"]) == 2
        assert "btn" in runner.macro.get("templates", {})

    def test_duplicate_steps(self, main_window: MainWindow):
        runner = get_runner(main_window)
        runner.macro["steps"] = [{"type": "key", "key": "a"}]
        main_window.on_macro_selected(0)
        main_window.step_list.setCurrentRow(0)
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
        main_window.step_list.setCurrentRow(0)
        main_window.wrap_in_repeat()
        assert runner.macro["steps"][0]["type"] == "repeat"
        assert len(runner.macro["steps"][0]["steps"]) == 1
        assert runner.macro["steps"][0]["steps"][0]["key"] == "a"
        assert runner.macro["steps"][1]["key"] == "b"

    def test_on_move_step_first_up_does_nothing(self, main_window: MainWindow):
        runner = get_runner(main_window)
        runner.macro["steps"] = [{"type": "key", "key": "a"}, {"type": "key", "key": "b"}]
        main_window.on_macro_selected(0)
        main_window.step_list.setCurrentRow(0)
        main_window.on_move_step(-1)
        assert runner.macro["steps"][0]["key"] == "a"
        assert runner.macro["steps"][1]["key"] == "b"

    def test_on_move_step_last_down_does_nothing(self, main_window: MainWindow):
        runner = get_runner(main_window)
        runner.macro["steps"] = [{"type": "key", "key": "a"}, {"type": "key", "key": "b"}]
        main_window.on_macro_selected(0)
        main_window.step_list.setCurrentRow(1)
        main_window.on_move_step(1)
        assert runner.macro["steps"][0]["key"] == "a"
        assert runner.macro["steps"][1]["key"] == "b"

    def test_refresh_current_step(self, main_window: MainWindow):
        main_window.refresh_current_step()

    def test_populate_steps_no_runner(self, main_window: MainWindow):
        main_window.current_runner = None
        main_window.populate_steps()
        assert main_window.step_list.count() == 0
        assert main_window.step_tree is None

    def test_on_step_selected_negative_row(self, main_window: MainWindow):
        main_window.on_step_selected(-1)
        assert main_window.prop_title.text() != ""

    def test_on_step_selected_no_runner(self, main_window: MainWindow):
        main_window.current_runner = None
        main_window.on_step_selected(0)
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
        item = QListWidgetItem("step")
        step = {"type": "key", "key": "a", "note": "  do this  "}
        main_window.apply_step_note(item, step)
        assert "do this" in item.toolTip()
        assert "do this" in item.text()


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
        assert main_window.step_list.currentRow() == 1

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
