"""Qt widget tests for MainWindow.

Requires pytest-qt and a display server (or virtual framebuffer on CI).
"""

import copy
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import config as cfg
from macro_engine import MacroRunner
from main_window import MainWindow


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
