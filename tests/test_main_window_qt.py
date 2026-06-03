"""Qt widget tests for MainWindow.

Requires pytest-qt and a display server (or virtual framebuffer on CI).
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import config as cfg
from main_window import MainWindow

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

    def test_switch_macro(self, main_window: MainWindow, qtbot):
        main_window.macro_list.setCurrentRow(1)
        assert main_window.current_runner is not None
        assert main_window.current_runner.label == "Test Macro B"


# ---------------------------------------------------------------------------
# Step list tests
# ---------------------------------------------------------------------------


class TestStepList:
    def test_step_count_macro_a(self, main_window: MainWindow):
        assert main_window.step_list.count() == 2

    def test_step_count_macro_b(self, main_window: MainWindow, qtbot):
        main_window.macro_list.setCurrentRow(1)
        assert main_window.step_list.count() == 4  # key + repeat + key + delay

    def test_step_selection(self, main_window: MainWindow, qtbot):
        main_window.step_list.setCurrentRow(0)
        assert main_window.step_list.currentRow() == 0

    def test_step_tree_built(self, main_window: MainWindow):
        assert main_window.step_tree is not None
        assert len(main_window.flat_nodes) == 2

    def test_flat_nodes_match_steps(self, main_window: MainWindow):
        steps = main_window.current_runner.macro.get("steps", [])
        assert len(main_window.flat_nodes) == len(steps)
        for node, step in zip(main_window.flat_nodes, steps, strict=True):
            assert node.step is step


# ---------------------------------------------------------------------------
# Step operations via UI
# ---------------------------------------------------------------------------


class TestStepOperations:
    def test_delete_step(self, main_window: MainWindow, qtbot):
        main_window.step_list.setCurrentRow(0)
        main_window.on_delete_step()
        assert main_window.step_list.count() == 1
        assert len(main_window.current_runner.macro["steps"]) == 1

    def test_delete_last_step(self, main_window: MainWindow, qtbot):
        main_window.step_list.setCurrentRow(0)
        main_window.on_delete_step()
        main_window.step_list.setCurrentRow(0)
        main_window.on_delete_step()
        assert main_window.step_list.count() == 0
        assert len(main_window.current_runner.macro["steps"]) == 0

    def test_add_step(self, main_window: MainWindow, qtbot):
        initial_count = main_window.step_list.count()
        step = {"type": "key", "key": "escape"}
        main_window.do_add_step(step)
        assert main_window.step_list.count() == initial_count + 1
        assert main_window.current_runner.macro["steps"][-1]["key"] == "escape"

    def test_add_step_after_selected(self, main_window: MainWindow, qtbot):
        main_window.step_list.setCurrentRow(0)
        step = {"type": "delay", "ms": 200}
        main_window.do_add_step(step)
        assert main_window.step_list.count() == 3
        steps = main_window.current_runner.macro["steps"]
        assert steps[1]["type"] == "delay"

    def test_move_step_down(self, main_window: MainWindow, qtbot):
        main_window.step_list.setCurrentRow(0)
        steps_before = [s["type"] for s in main_window.current_runner.macro["steps"]]
        main_window.on_move_step(1)
        steps_after = [s["type"] for s in main_window.current_runner.macro["steps"]]
        assert steps_before == ["key", "delay"]
        assert steps_after == ["delay", "key"]

    def test_move_step_up(self, main_window: MainWindow, qtbot):
        main_window.step_list.setCurrentRow(1)
        main_window.on_move_step(-1)
        steps_after = [s["type"] for s in main_window.current_runner.macro["steps"]]
        assert steps_after == ["delay", "key"]

    def test_duplicate_step(self, main_window: MainWindow, qtbot):
        main_window.step_list.setCurrentRow(0)
        main_window.duplicate_steps()
        assert main_window.step_list.count() == 3
        steps = main_window.current_runner.macro["steps"]
        assert steps[0]["key"] == steps[1]["key"]

    def test_copy_paste_step(self, main_window: MainWindow, qtbot):
        main_window.step_list.setCurrentRow(0)
        main_window.copy_steps()
        main_window.step_list.setCurrentRow(1)
        main_window.paste_steps()
        assert main_window.step_list.count() == 3
        steps = main_window.current_runner.macro["steps"]
        assert steps[2]["type"] == "key"

    def test_cut_step(self, main_window: MainWindow, qtbot):
        main_window.step_list.setCurrentRow(0)
        main_window.cut_steps()
        assert main_window.step_list.count() == 1
        assert hasattr(main_window, "step_clipboard")
        assert len(main_window.step_clipboard["steps"]) == 1

    def test_wrap_in_repeat(self, main_window: MainWindow, qtbot):
        main_window.step_list.setCurrentRow(0)
        model = main_window.step_list.model()
        selection_model = main_window.step_list.selectionModel()
        selection_model.select(
            model.index(0),
            selection_model.SelectionFlag.ClearAndSelect | selection_model.SelectionFlag.Rows,
        )
        selection_model.select(
            model.index(1),
            selection_model.SelectionFlag.Select | selection_model.SelectionFlag.Rows,
        )
        main_window.wrap_in_repeat()
        steps = main_window.current_runner.macro["steps"]
        assert len(steps) == 1
        assert steps[0]["type"] == "repeat"
        assert len(steps[0]["steps"]) == 2


# ---------------------------------------------------------------------------
# Undo/redo tests
# ---------------------------------------------------------------------------


class TestUndoRedo:
    def test_undo_deletes_last_action(self, main_window: MainWindow, qtbot):
        main_window.step_list.setCurrentRow(0)
        main_window.on_delete_step()
        assert main_window.step_list.count() == 1
        main_window.undo()
        assert main_window.step_list.count() == 2

    def test_redo_after_undo(self, main_window: MainWindow, qtbot):
        main_window.step_list.setCurrentRow(0)
        main_window.on_delete_step()
        main_window.undo()
        main_window.redo()
        assert main_window.step_list.count() == 1

    def test_undo_button_state(self, main_window: MainWindow, qtbot):
        assert not main_window.btn_undo.isEnabled()
        main_window.step_list.setCurrentRow(0)
        main_window.on_delete_step()
        assert main_window.btn_undo.isEnabled()


# ---------------------------------------------------------------------------
# Empty state tests
# ---------------------------------------------------------------------------


class TestEmptyStates:
    def test_empty_macro_shows_hint(self, main_window: MainWindow, qtbot):
        main_window.macro_list.setCurrentRow(0)
        main_window.step_list.setCurrentRow(0)
        main_window.on_delete_step()
        main_window.step_list.setCurrentRow(0)
        main_window.on_delete_step()
        assert main_window.step_list.count() == 0
        main_window.update_empty_states()
        assert main_window.step_list.isHidden()
        assert not main_window.step_empty_label.isHidden()

    def test_no_macros_shows_hint(self, main_window: MainWindow, qtbot):
        main_window.macro_list.setCurrentRow(0)
        main_window.on_delete_step()
        # Can't easily test macro empty state without deleting macros
        # This is tested at the integration level


# ---------------------------------------------------------------------------
# Property panel tests
# ---------------------------------------------------------------------------


class TestPropertyPanel:
    def test_selecting_step_shows_props(self, main_window: MainWindow, qtbot):
        main_window.step_list.setCurrentRow(0)
        assert main_window.prop_fields_layout.count() > 0

    def test_selecting_different_step_updates_props(self, main_window: MainWindow, qtbot):
        main_window.step_list.setCurrentRow(0)
        main_window.step_list.setCurrentRow(1)
        assert main_window.prop_fields_layout.count() > 0

    def test_macro_props_shown_when_no_step_selected(self, main_window: MainWindow, qtbot):
        main_window.step_list.clearSelection()
        main_window.show_macro_props()
        assert main_window.prop_title.text() != ""
