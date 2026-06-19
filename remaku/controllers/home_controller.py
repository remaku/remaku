import copy
import json
import logging
import os
import shutil
import time
import webbrowser
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QApplication, QFileDialog

from remaku.core import display, window
from remaku.core.dialogs import show_confirm_dialog, show_message_dialog
from remaku.core.event_bus import event_bus
from remaku.models.config_model import config_model
from remaku.models.macro_model import (
    TEMPLATE_MATCH_MODES,
    DelayStep,
    GridNavStep,
    HoldKeyUntilGoneStep,
    IfAnyImageStep,
    IfImageStep,
    KeyStep,
    Macro,
    MacroMeta,
    MacroModel,
    MacroSummary,
    MouseClickStep,
    MouseMoveStep,
    MouseScrollStep,
    RepeatStep,
    Step,
    TextInputStep,
    WaitImageStep,
    parse_step,
    step_to_dict,
)
from remaku.models.step_node import StepNode
from remaku.models.step_tree import StepTree
from remaku.paths import log_dir, macro_path, macros_dir, template_path, templates_dir
from remaku.services.clipboard_service import ClipboardService
from remaku.services.hotkey_service import HotkeyService
from remaku.services.macro_import_service import (
    ImportMacroOptions,
    MacroImportError,
    inspect_macro_archive,
    install_macro_archive,
    resolve_import_macro_id,
)
from remaku.services.macro_recorder import MacroRecorder
from remaku.services.macro_runner import MacroRunner
from remaku.services.template_service import TemplateService
from remaku.version import __version__
from remaku.views.components.about_dialog import AboutDialog
from remaku.views.components.hotkey_edit import KEY_CAPTURE_PROPERTY
from remaku.views.components.new_macro_dialog import NewMacroDialog
from remaku.views.components.recording_overlay import RecordingOverlay
from remaku.views.components.rename_macro_dialog import RenameMacroDialog
from remaku.views.home_view import HomeView
from remaku.views.region_selector import RegionSelector

logger = logging.getLogger(__name__)
TEMPLATE_FILE_SNAPSHOT_KEY = "__template_files__"


class HomeController(QObject):
    def __init__(
        self,
        view: HomeView,
        macro_model: MacroModel,
    ):
        super().__init__()

        self.view = view
        self.macro_model = macro_model
        self.selected_macro_id = ""
        self.selected_step: dict | None = None
        self.selected_branch_parent: dict | None = None
        self.selected_branch_key = ""
        self.current_macro: Macro | None = None
        self.current_runner: MacroRunner | None = None
        self.current_recorder: MacroRecorder | None = None
        self.recording_overlay: RecordingOverlay | None = None
        self.step_tree: StepTree | None = None
        self.undo_stacks: dict[str, list[dict]] = {}
        self.redo_stacks: dict[str, list[dict]] = {}
        self.undo_selection_indexes: dict[str, list[int | None]] = {}
        self.redo_selection_indexes: dict[str, list[int | None]] = {}
        self.step_clipboard: dict | None = None
        self.clipboard_service = ClipboardService()
        self.template_service = TemplateService(
            self.generate_template_id,
            self.default_template_label,
            screen_size_provider=window.screen_resolution,
        )
        self.editing_locked = False
        self.hotkey_service = HotkeyService(
            self.macro_model,
            lambda: int(self.view.window().winId()),
        )
        self.hotkey_runners: dict[str, MacroRunner] = {}
        self.actions: dict[str, Callable[[], object]] = {
            "about": self.show_about_dialog,
            "support_author": lambda: webbrowser.open("https://github.com/sponsors/nelsonlaidev"),
            "run": self.run_current_macro,
            "record": self.start_macro_recording,
            "record_pause": self.toggle_macro_recording_pause,
            "record_stop": self.stop_macro_recording,
            "record_cancel": self.cancel_macro_recording,
            "open_macro_folder": self.open_macro_folder,
            "open_logs": self.open_logs_folder,
            "new_macro": self.handle_new_macro,
            "settings": self.open_settings,
            "pack_explorer": self.open_pack_explorer,
            "quit": self.quit_application,
            "add_step": lambda: event_bus.show_toolbar_step_menu_requested.emit(),
            "duplicate_step": self.duplicate_selected_step,
            "delete_step": self.delete_selected_step,
            "move_up": lambda: self.move_selected_step(-1),
            "move_down": lambda: self.move_selected_step(1),
            "wrap_in_repeat": self.wrap_selected_step_in_repeat,
            "undo": self.undo,
            "redo": self.redo,
            "cut": self.cut_selected_steps,
            "copy": self.copy_selected_steps,
            "paste": self.paste_steps,
            "duplicate_macro": self.duplicate_current_macro,
            "import_macro": self.import_macro,
            "export_macro": self.export_current_macro,
            "check_updates": lambda: event_bus.check_updates_requested.emit(),
        }

        event_bus.overlay_toggled.connect(self.run_current_macro)
        event_bus.overlay_pause_toggled.connect(self.toggle_current_macro_pause)
        event_bus.action_triggered.connect(self.handle_action)
        event_bus.new_macro_requested.connect(self.handle_new_macro)
        event_bus.macro_selected.connect(self.handle_macro_selected)
        event_bus.macro_rename_requested.connect(self.handle_macro_rename)
        event_bus.macro_delete_requested.connect(self.handle_macro_delete)
        event_bus.macro_duplicate_requested.connect(self.handle_macro_duplicate)
        event_bus.macro_running_changed.connect(self.handle_macro_running_changed)
        event_bus.step_selected.connect(self.handle_step_selected)
        event_bus.branch_selected.connect(self.handle_branch_selected)
        event_bus.template_capture_requested.connect(self.handle_template_capture)
        event_bus.template_pick_requested.connect(self.handle_template_pick)
        event_bus.template_delete_requested.connect(self.handle_template_delete)
        event_bus.template_add_requested.connect(self.handle_template_add)
        event_bus.step_add_requested.connect(self.add_step)
        event_bus.macro_meta_changed.connect(self.handle_macro_meta_changed)
        event_bus.step_property_changed.connect(self.handle_step_property_changed)
        event_bus.template_meta_changed.connect(self.handle_template_meta_changed)
        event_bus.hotkey_triggered.connect(self.handle_hotkey_triggered)
        event_bus.macro_order_changed.connect(self.handle_macro_order_changed)
        event_bus.macros_changed.connect(self.refresh_macro_list)
        event_bus.macro_paused_changed.connect(self.handle_macro_paused_changed)
        event_bus.macro_recording_paused_changed.connect(self.handle_macro_recording_paused_changed)
        event_bus.settings_changed.connect(self.register_hotkeys)

        self.view.center_panel.step_list.itemSelectionChanged.connect(self.update_step_action_state)

        self.register_shortcuts()
        self.update_undo_redo_state()
        self.refresh_macro_list()
        self.register_hotkeys()

    def register_shortcuts(self) -> None:
        shortcut_map = {
            "Ctrl+Z": self.undo,
            "Ctrl+Y": self.redo,
            "Ctrl+C": self.copy_selected_steps,
            "Ctrl+X": self.cut_selected_steps,
            "Ctrl+V": self.paste_steps,
            "Ctrl+,": self.open_settings,
            "Ctrl+D": self.duplicate_selected_step,
            "Ctrl+Shift+N": lambda: event_bus.show_toolbar_step_menu_requested.emit(),
            "Del": self.delete_selected_step,
            "Alt+Up": lambda: self.move_selected_step(-1),
            "Alt+Down": lambda: self.move_selected_step(1),
            "Ctrl+N": self.handle_new_macro,
        }

        editing_keys = set(shortcut_map.keys())

        self.shortcuts: list[QShortcut] = []
        self.editing_shortcuts: list[QShortcut] = []

        for key, handler in shortcut_map.items():
            shortcut = QShortcut(QKeySequence(key), self.view)
            shortcut.activated.connect(lambda handler=handler: self.handle_shortcut(handler))
            self.shortcuts.append(shortcut)

            if key in editing_keys:
                self.editing_shortcuts.append(shortcut)

    def handle_shortcut(self, handler: Callable[[], None]) -> None:
        if self.is_hotkey_input_focused():
            return

        handler()

    def is_hotkey_input_focused(self) -> bool:
        widget = QApplication.focusWidget()

        while widget is not None:
            if widget.property(KEY_CAPTURE_PROPERTY):
                return True

            widget = widget.parentWidget()

        return False

    def set_current_macro(self, macro: Macro | None) -> None:
        self.current_macro = macro
        self.update_undo_redo_state()

    @property
    def undo_stack(self) -> list[dict]:
        return self.undo_stacks.setdefault(self.selected_macro_id, [])

    @property
    def redo_stack(self) -> list[dict]:
        return self.redo_stacks.setdefault(self.selected_macro_id, [])

    @property
    def undo_selection_index_stack(self) -> list[int | None]:
        return self.undo_selection_indexes.setdefault(self.selected_macro_id, [])

    @property
    def redo_selection_index_stack(self) -> list[int | None]:
        return self.redo_selection_indexes.setdefault(self.selected_macro_id, [])

    def current_macro_dict(self) -> dict | None:
        if self.current_runner is None:
            return None

        return self.current_runner.macro

    def current_macro_snapshot(self) -> dict | None:
        macro_dict = self.current_macro_dict()
        if macro_dict is None:
            return None

        snapshot = copy.deepcopy(macro_dict)
        self.add_template_files_to_snapshot(snapshot)

        return snapshot

    def add_template_files_to_snapshot(self, snapshot: dict) -> None:
        if self.current_macro is None:
            return

        template_ids = set(snapshot.get("templates", {}))
        template_ids.update(StepTree(copy.deepcopy(snapshot.get("steps", []))).collect_template_refs())

        template_files: dict[str, bytes] = {}

        for template_id in sorted(template_ids):
            png_path = template_path(self.current_macro.meta.id, template_id)

            try:
                if png_path.exists():
                    template_files[template_id] = png_path.read_bytes()
            except OSError:
                logger.warning("Failed to snapshot template file: %s", png_path, exc_info=True)

        if template_files:
            snapshot[TEMPLATE_FILE_SNAPSHOT_KEY] = template_files

    def sync_runner_macro_from_current(self) -> None:
        if self.current_runner is None or self.current_macro is None:
            return

        self.current_runner = MacroRunner(
            self.current_macro,
            macro_path=self.current_runner.macro_path,
        )

    def push_undo(self, restore_selection_index: int | None = None) -> None:
        snapshot = self.current_macro_snapshot()
        if self.current_runner is None or snapshot is None:
            return

        self.undo_stack.append(snapshot)
        self.undo_selection_index_stack.append(restore_selection_index)

        if len(self.undo_stack) > 50:
            self.undo_stack.pop(0)
            self.undo_selection_index_stack.pop(0)

        self.redo_stack.clear()
        self.redo_selection_index_stack.clear()
        self.update_undo_redo_state()

    def update_undo_redo_state(self) -> None:
        if self.editing_locked:
            self.view.toolbar.undo_button.setEnabled(False)
            self.view.toolbar.redo_button.setEnabled(False)
            return

        has_undo = bool(self.current_runner and self.undo_stack)
        has_redo = bool(self.current_runner and self.redo_stack)
        self.view.toolbar.undo_button.setEnabled(has_undo)
        self.view.toolbar.redo_button.setEnabled(has_redo)

    def update_step_action_state(self) -> None:
        if self.editing_locked:
            return

        selected = self.selected_step_nodes()
        has_selection = bool(selected)
        is_single = len(selected) == 1

        self.view.toolbar.delete_button.setEnabled(has_selection)

        if is_single and self.step_tree is not None:
            node = selected[0]
            self.view.toolbar.move_up_button.setEnabled(self.step_tree.can_move(node, -1))
            self.view.toolbar.move_down_button.setEnabled(self.step_tree.can_move(node, 1))
        else:
            self.view.toolbar.move_up_button.setEnabled(False)
            self.view.toolbar.move_down_button.setEnabled(False)

    def save_current_macro(self) -> None:
        if self.current_macro is None or self.current_runner is None:
            return

        self.sync_runner_macro_from_current()
        self.macro_model.save(self.current_macro)
        self.update_undo_redo_state()

    def mutate_current_macro(self) -> None:
        self.sync_macro_steps_from_tree()
        self.refresh_step_tree()
        self.refresh_selected_step()
        self.save_current_macro()

    def restore_macro_state(self, macro_dict: dict, selection_index: int | None = None) -> None:
        if self.current_runner is None:
            return

        old_steps = list(self.current_macro.steps) if self.current_macro else []

        restored_macro = Macro.from_dict(copy.deepcopy(macro_dict))
        self.delete_templates_missing_from_restored_state(restored_macro)
        self.restore_template_files_from_snapshot(restored_macro, macro_dict)
        source_path = self.current_runner.macro_path

        restored_runner = MacroRunner(
            restored_macro,
            macro_path=source_path,
        )

        step_tree = StepTree([step_to_dict(step) for step in restored_macro.steps])

        self.show_loaded_macro(
            restored_macro,
            restored_runner,
            step_tree,
        )

        self.select_after_undo_redo(old_steps, list(restored_macro.steps), selection_index)

        self.macro_model.save(restored_macro)

    def delete_templates_missing_from_restored_state(self, restored_macro: Macro) -> None:
        if self.current_macro is None:
            return

        current_template_ids = set(self.current_macro.templates)
        restored_template_ids = set(restored_macro.templates)

        for template_id in sorted(current_template_ids - restored_template_ids):
            png_path = template_path(self.current_macro.meta.id, template_id)

            try:
                if png_path.exists():
                    png_path.unlink()
            except OSError:
                logger.warning("Failed to delete restored template file: %s", png_path, exc_info=True)

    def restore_template_files_from_snapshot(self, restored_macro: Macro, macro_dict: dict) -> None:
        template_files = macro_dict.get(TEMPLATE_FILE_SNAPSHOT_KEY, {})
        if not isinstance(template_files, dict):
            return

        for template_id, file_data in template_files.items():
            if template_id not in restored_macro.templates or not isinstance(file_data, bytes):
                continue

            png_path = template_path(restored_macro.meta.id, template_id)

            try:
                png_path.parent.mkdir(parents=True, exist_ok=True)
                png_path.write_bytes(file_data)
            except OSError:
                logger.warning("Failed to restore template file: %s", png_path, exc_info=True)

    def select_after_undo_redo(self, old_steps: list, new_steps: list, selection_index: int | None = None) -> None:
        if self.step_tree is None or not self.step_tree.steps:
            self.selected_step = None
            self.show_macro_properties(self.current_macro)
            return

        if selection_index is not None:
            target_node = self.step_tree.node_at(selection_index)
            if target_node is not None:
                self.selected_step = target_node.step
                self.refresh_step_tree()
                self.show_step_selection(self.selected_step)
                return

        old_tree = StepTree([step_to_dict(s) for s in old_steps])
        old_flat = old_tree.flatten()
        new_flat = self.step_tree.flatten()

        diff_index = 0

        while diff_index < len(old_flat) and diff_index < len(new_flat):
            if old_flat[diff_index].step != new_flat[diff_index].step:
                break
            diff_index += 1

        if diff_index < len(new_flat):
            target_node = new_flat[diff_index]
        elif len(new_flat) > 0:
            prev_index = diff_index - 1 if diff_index > 0 else 0
            target_node = new_flat[prev_index]
        else:
            self.selected_step = None
            self.show_macro_properties(self.current_macro)
            return

        self.selected_step = target_node.step
        self.refresh_step_tree()
        self.show_step_selection(self.selected_step)

    def undo_redo_change_description(self, before_state: dict, after_state: dict) -> str:
        before_steps = self.flatten_snapshot_steps(before_state)
        after_steps = self.flatten_snapshot_steps(after_state)

        if len(after_steps) > len(before_steps):
            added_step = self.first_added_step(before_steps, after_steps)
            return self.tr("Added {step}").format(step=self.describe_step_from_snapshot(added_step))

        if len(after_steps) < len(before_steps):
            deleted_step = self.first_added_step(after_steps, before_steps)
            return self.tr("Deleted {step}").format(step=self.describe_step_from_snapshot(deleted_step))

        for before_step, after_step in zip(before_steps, after_steps, strict=False):
            if before_step != after_step:
                return self.tr("Changed {before} to {after}").format(
                    before=self.describe_step_from_snapshot(before_step),
                    after=self.describe_step_from_snapshot(after_step),
                )

        return self.tr("Updated macro")

    def flatten_snapshot_steps(self, snapshot: dict) -> list[dict]:
        steps = snapshot.get("steps", [])

        if not isinstance(steps, list):
            return []

        return [copy.deepcopy(node.step) for node in StepTree(copy.deepcopy(steps)).flatten()]

    def first_added_step(self, before_steps: list[dict], after_steps: list[dict]) -> dict:
        for index, after_step in enumerate(after_steps):
            if index >= len(before_steps) or before_steps[index] != after_step:
                return after_step

        return after_steps[-1] if after_steps else {}

    def describe_step_from_snapshot(self, step: dict) -> str:
        if not step:
            return self.tr("step")

        return self.describe_step(step)

    def undo(self) -> None:
        if self.current_runner is None or not self.undo_stack:
            return

        current_macro_snapshot = self.current_macro_snapshot()
        if current_macro_snapshot is not None:
            self.redo_stack.append(current_macro_snapshot)
            self.redo_selection_index_stack.append(self.selected_step_flat_index())

        restored_state = self.undo_stack.pop()
        selection_index = self.undo_selection_index_stack.pop() if self.undo_selection_index_stack else None
        change_description = (
            self.undo_redo_change_description(restored_state, current_macro_snapshot)
            if current_macro_snapshot is not None
            else self.tr("Updated macro")
        )
        self.restore_macro_state(restored_state, selection_index)
        self.update_undo_redo_state()
        self.view.set_status_text(self.tr("Undo: {change}").format(change=change_description))

    def redo(self) -> None:
        if self.current_runner is None or not self.redo_stack:
            return

        current_macro_snapshot = self.current_macro_snapshot()
        if current_macro_snapshot is not None:
            self.undo_stack.append(current_macro_snapshot)
            self.undo_selection_index_stack.append(self.selected_step_flat_index())

        restored_state = self.redo_stack.pop()
        selection_index = self.redo_selection_index_stack.pop() if self.redo_selection_index_stack else None
        change_description = (
            self.undo_redo_change_description(current_macro_snapshot, restored_state)
            if current_macro_snapshot is not None
            else self.tr("Updated macro")
        )
        self.restore_macro_state(restored_state, selection_index)
        self.update_undo_redo_state()
        self.view.set_status_text(self.tr("Redo: {change}").format(change=change_description))

    def copy_selected_steps(self) -> None:
        if self.step_tree is None or self.current_macro is None:
            return

        selected = self.selected_step_nodes()
        if not selected:
            return

        clipboard = self.clipboard_service.copy_selected_steps(self.current_macro, self.step_tree, selected)
        if clipboard is None:
            return

        self.step_clipboard = clipboard
        event_bus.clipboard_changed.emit(True)

    def cut_selected_steps(self) -> None:
        self.copy_selected_steps()
        if self.step_clipboard:
            self.delete_selected_step()

    def paste_steps(self) -> None:
        if self.step_tree is None or not self.step_clipboard or self.current_macro is None:
            return

        self.push_undo()
        result = self.clipboard_service.paste_steps(
            self.current_macro,
            self.step_tree,
            self.step_clipboard,
            self.selected_step_node(),
            self.selected_step,
        )
        if not result.changed:
            return

        self.selected_step = result.selected_step
        self.mutate_current_macro()

    def refresh_macro_list(self) -> None:
        macro_items = self.macro_model.list_macros()
        ordered_macro_items = self.sort_macro_items(macro_items)
        list_items = [(item.id, item.label) for item in ordered_macro_items]

        if self.selected_macro_id not in {item.id for item in ordered_macro_items}:
            self.selected_macro_id = ""

        if not self.selected_macro_id and ordered_macro_items:
            self.selected_macro_id = ordered_macro_items[0].id

        self.view.left_panel.set_macro_list(list_items, self.selected_macro_id)

        if self.selected_macro_id:
            self.load_selected_macro(self.selected_macro_id)
        else:
            self.show_empty_macro_state()

        self.register_hotkeys()

    def sort_macro_items(self, macro_items: list[MacroSummary]) -> list[MacroSummary]:
        order_index = {macro_id: index for index, macro_id in enumerate(config_model.config.general.macro_order)}

        return sorted(
            macro_items,
            key=lambda item: (
                order_index.get(item.id, len(order_index)),
                item.label.lower(),
                item.id.lower(),
            ),
        )

    def handle_new_macro(self) -> None:
        while True:
            dialog = NewMacroDialog(self.view.window())
            accepted = bool(dialog.exec())

            if not accepted:
                return

            new_macro_label = dialog.value()

            if not new_macro_label:
                show_message_dialog(self.view.window(), self.tr("New Macro"), self.tr("Macro name cannot be empty."))
                continue

            new_macro_id = str(int(time.time()))

            macro = Macro(meta=MacroMeta(id=new_macro_id, label=new_macro_label))
            self.macro_model.save(macro)

            self.selected_macro_id = new_macro_id
            self.refresh_macro_list()
            self.view.set_status_text(self.tr("Created macro: {name}").format(name=new_macro_label))

            return

    def handle_macro_selected(self, macro_id: str) -> None:
        if self.selected_macro_id == macro_id and self.current_macro is not None:
            self.selected_step = None
            self.selected_branch_parent = None
            self.selected_branch_key = ""
            self.refresh_step_tree()
            self.show_macro_properties(self.current_macro)
            self.update_step_action_state()
            return

        self.selected_macro_id = macro_id
        self.load_selected_macro(macro_id)

    def handle_macro_rename(self, macro_id: str) -> None:
        if self.editing_locked:
            return

        macro = self.macro_model.load(macro_id)

        if macro is None:
            self.view.set_status_text(self.tr("Failed to load macro: {name}").format(name=macro_id))
            return

        current_label = macro.meta.label or macro_id

        while True:
            dialog = RenameMacroDialog(self.view.window(), current_label)
            accepted = bool(dialog.exec())

            if not accepted:
                return

            new_label = dialog.value()

            if not new_label:
                show_message_dialog(self.view.window(), self.tr("Rename Macro"), self.tr("Macro name cannot be empty."))
                continue

            if new_label == current_label:
                return

            macro.meta.label = new_label
            self.macro_model.save(macro)

            self.refresh_macro_list()
            self.view.set_status_text(self.tr("Renamed macro: {name}").format(name=new_label))

            return

    def handle_macro_delete(self, macro_id: str) -> None:
        if self.editing_locked:
            return

        macro = self.macro_model.load(macro_id)
        macro_label = macro.meta.label if macro is not None and macro.meta.label else macro_id

        confirmed = show_confirm_dialog(
            self.view.window(),
            self.tr("Delete Macro"),
            self.tr('Are you sure you want to delete "{name}"?').format(name=macro_label),
            self.tr("Delete"),
        )

        if not confirmed:
            return

        if not self.macro_model.delete(macro_id):
            show_message_dialog(self.view.window(), self.tr("Delete Macro"), self.tr("Unable to delete the macro."))
            return

        template_dir = templates_dir(macro_id)
        if template_dir.exists():
            shutil.rmtree(template_dir)

        config_model.config.general.macro_order = [
            ordered_macro_id
            for ordered_macro_id in config_model.config.general.macro_order
            if ordered_macro_id != macro_id
        ]
        config_model.save()

        if self.selected_macro_id == macro_id:
            self.selected_macro_id = ""

        self.refresh_macro_list()
        self.view.set_status_text(self.tr("Deleted macro: {name}").format(name=macro_label))

    def handle_macro_duplicate(self, macro_id: str) -> None:
        if self.editing_locked:
            return

        if self.selected_macro_id != macro_id:
            self.selected_macro_id = macro_id
            self.load_selected_macro(macro_id)

        self.duplicate_current_macro()

    def handle_macro_order_changed(self) -> None:
        items = [self.view.left_panel.macro_list.item(i) for i in range(self.view.left_panel.macro_list.count())]

        new_order: list[str] = []

        for item in items:
            if item is not None:
                macro_id = item.data(Qt.ItemDataRole.UserRole)
                if isinstance(macro_id, str):
                    new_order.append(macro_id)

        config_model.config.general.macro_order = new_order
        config_model.save()

    def handle_step_selected(self, step: dict | None) -> None:
        self.selected_branch_parent = None
        self.selected_branch_key = ""
        self.selected_step = step
        self.show_step_selection(step)
        QTimer.singleShot(0, self.update_step_action_state)

    def handle_branch_selected(self, parent_step: dict | None, branch_key: str) -> None:
        self.selected_step = None
        self.selected_branch_parent = parent_step
        self.selected_branch_key = branch_key
        self.show_step_selection(None)
        self.update_step_action_state()

    def handle_macro_meta_changed(self, field: str, value: str) -> None:
        if self.current_macro is None:
            return

        if field == "enabled":
            setattr(self.current_macro.meta, field, value.lower() == "true")
        elif field in ("gaming_mode", "background_input", "keep_target_focused"):
            setattr(self.current_macro, field, value.lower() == "true")
        else:
            setattr(self.current_macro.meta, field, value)

        self.macro_model.save(self.current_macro)

        self.sync_runner_macro_from_current()

        if field in ("hotkey", "enabled"):
            self.register_hotkeys()

    def handle_step_property_changed(self, key: str, value: str) -> None:
        if self.selected_step is None:
            return

        parsed_value = self.parse_step_property(key, value)
        if self.selected_step.get(key) == parsed_value:
            return

        self.push_undo(self.selected_step_flat_index())
        self.selected_step[key] = parsed_value

        if key == "skip" and self.selected_step.get("type") == "repeat":
            self.set_descendant_skip(self.selected_step, bool(parsed_value))

        self.sync_macro_steps_from_tree()
        self.save_current_macro()
        self.refresh_step_tree()
        self.refresh_selected_step()

    def parse_step_property(self, key: str, value: str) -> int | float | bool | str:
        if key in ("skip", "relative"):
            return value.lower() == "true"

        if key in (
            "ms",
            "hold_ms",
            "timeout_ms",
            "load_delay_ms",
            "find_timeout_ms",
            "gone_grace_ms",
            "hard_timeout_ms",
            "count",
            "rows",
            "start",
            "interval_ms",
            "clicks",
            "x",
            "y",
        ):
            return int(value)

        if key == "threshold":
            return int(value) / 100

        return value

    def selected_step_node(self) -> StepNode | None:
        if self.step_tree is None or self.selected_step is None:
            return None

        return self.step_tree.find_node(self.selected_step)

    def selected_step_flat_index(self) -> int | None:
        selected_node = self.selected_step_node()
        if self.step_tree is None or selected_node is None:
            return None

        try:
            return self.step_tree.flatten().index(selected_node)
        except ValueError:
            return None

    def selected_step_nodes(self) -> list[StepNode]:
        if self.step_tree is None:
            return []

        center = self.view.center_panel
        nodes: list[StepNode] = []

        for item in center.step_list.selectedItems():
            step_dict = center.item_to_step.get(item)
            if isinstance(step_dict, dict):
                node = self.step_tree.find_node(step_dict)
                if node is not None:
                    nodes.append(node)

        return nodes

    def load_selected_macro(self, macro_id: str) -> None:
        macro = self.macro_model.load(macro_id)

        if macro is None:
            self.show_macro_load_error(macro_id)
            return

        runner = MacroRunner(macro, macro_path(macro_id))
        step_tree = StepTree([step_to_dict(step) for step in macro.steps])
        self.show_loaded_macro(macro, runner, step_tree)

    def show_empty_macro_state(self) -> None:
        self.set_current_macro(None)
        self.current_runner = None
        self.step_tree = None
        self.selected_step = None
        self.selected_branch_parent = None
        self.selected_branch_key = ""
        self.show_macro_properties(None)
        self.refresh_step_tree()

    def show_macro_load_error(self, macro_id: str) -> None:
        self.set_current_macro(None)
        self.current_runner = None
        self.step_tree = None
        self.selected_step = None
        self.selected_branch_parent = None
        self.selected_branch_key = ""
        self.show_macro_properties(None)
        self.refresh_step_tree()
        self.view.set_status_text(self.tr("Failed to load macro: {name}").format(name=macro_id))

    def show_loaded_macro(
        self,
        macro: Macro,
        runner: MacroRunner,
        step_tree: StepTree,
    ) -> None:
        self.set_current_macro(macro)
        self.current_runner = runner
        self.step_tree = step_tree
        self.selected_step = None
        self.selected_branch_parent = None
        self.selected_branch_key = ""
        self.show_macro_properties(macro)
        self.refresh_step_tree()

    def show_step_selection(self, step: dict | None) -> None:
        if self.current_macro is None:
            return

        if self.selected_branch_parent is not None and self.selected_branch_key:
            parent_description = self.describe_step(self.selected_branch_parent)
            self.view.right_panel.show_branch_properties(
                self.current_macro,
                parent_description,
                self.branch_label(self.selected_branch_key, self.selected_branch_parent),
                self.branch_steps(self.selected_branch_parent, self.selected_branch_key),
            )
            return

        if step is None:
            self.show_macro_properties(self.current_macro)
            return

        parsed_step = parse_step(step)
        skip_enabled = not self.is_child_of_skipped_repeat(step)

        self.view.right_panel.show_step_properties(
            self.current_macro, self.describe_step(step), parsed_step, skip_enabled
        )

    def set_selected_step(self, step: dict | None) -> None:
        self.selected_branch_parent = None
        self.selected_branch_key = ""
        self.selected_step = step
        self.sync_macro_steps_from_tree()
        self.refresh_step_tree()
        self.show_step_selection(step)

    def refresh_selected_step(self) -> None:
        self.show_step_selection(self.selected_step)

    def sync_macro_steps_from_tree(self) -> None:
        if self.step_tree is None or self.current_macro is None:
            return

        self.current_macro.steps = [parse_step(step) for step in self.step_tree.steps]

    def build_step_items(self) -> list[dict]:
        if self.step_tree is None:
            return []

        return [self.build_step_item(node, (("steps", index),)) for index, node in enumerate(self.step_tree.root_nodes)]

    def refresh_step_tree(self) -> None:
        selected_branch = None
        if self.selected_branch_parent is not None and self.selected_branch_key:
            selected_branch = (self.selected_branch_parent, self.selected_branch_key)

        self.view.center_panel.set_step_tree(self.build_step_items(), self.selected_step, selected_branch)

    def show_macro_properties(self, macro: Macro | None) -> None:
        self.view.right_panel.show_macro_properties(macro)

    def build_step_item(self, node: StepNode, path: tuple[tuple[str, int], ...]) -> dict:
        children: list[dict[str, Any]] = []

        if node.step_type == "repeat":
            child_list = node.get_child_list("steps")
            children = [
                self.build_step_item(child, (*path, ("steps", index))) for index, child in enumerate(child_list)
            ]
        else:
            for branch_key, child_list in node.child_lists():
                branch_children = [
                    self.build_step_item(child, (*path, (branch_key, index))) for index, child in enumerate(child_list)
                ]
                children.append(
                    {
                        "label": self.branch_label(branch_key, node.step),
                        "branch": (node.step, branch_key),
                        "state_key": ("branch", path, branch_key),
                        "children": branch_children,
                    }
                )
        return {
            "label": self.describe_step(node.step),
            "step": node.step,
            "state_key": ("step", path),
            "children": children,
        }

    def branch_label(self, branch_key: str, step: dict | None = None) -> str:
        if step is not None and step.get("type") == "if_any_image":
            return self.get_template_label(branch_key)

        labels = {
            "steps": self.tr("Steps"),
            "then": self.tr("Then"),
            "else": self.tr("Else"),
            "on_next_row": self.tr("On Next Row"),
            "on_next_col": self.tr("On Next Column"),
        }

        return labels.get(branch_key, branch_key.replace("_", " ").title())

    def branch_steps(self, parent_step: dict, branch_key: str) -> list[Step]:
        parent_node = self.step_tree.find_node(parent_step) if self.step_tree is not None else None
        if parent_node is None:
            return []

        return [parse_step(child.step) for child in parent_node.get_child_list(branch_key)]

    def is_child_of_skipped_repeat(self, step: dict) -> bool:
        node = self.step_tree.find_node(step) if self.step_tree is not None else None
        if node is None:
            return False

        parent = node.parent
        while parent is not None:
            if parent.step_type == "repeat" and parent.step.get("skip", False):
                return True

            parent = parent.parent

        return False

    def set_descendant_skip(self, step: dict, skip: bool) -> None:
        node = self.step_tree.find_node(step) if self.step_tree is not None else None
        if node is None:
            return

        for descendant in node.all_descendants():
            descendant.step["skip"] = skip

    def describe_step(self, step: dict) -> str:
        step_type = step.get("type", "unknown")
        note = step.get("note", "")

        label = ""

        match step_type:
            case "key":
                label = self.tr("Press {key}").format(key=step.get("key", ""))
            case "delay":
                label = self.tr("Wait {ms} ms").format(ms=step.get("ms", 0))
            case "wait_image":
                label = self.tr("Wait for {template}").format(
                    template=self.get_template_label(step.get("template", ""))
                )
            case "hold_key_until_gone":
                label = self.tr("Hold {key} until {template} gone").format(
                    key=step.get("key", ""),
                    template=self.get_template_label(step.get("template", "")),
                )
            case "text_input":
                text = str(step.get("text", ""))
                preview = text.replace("\r", " ").replace("\n", " ")
                if len(preview) > 20:
                    preview = f"{preview[:20]}..."
                label = self.tr("Type text: {text}").format(text=preview) if preview else self.tr("Type text")
            case "repeat":
                label = self.tr("Repeat {count} times").format(count=step.get("count", 1))
            case "if_image":
                label = self.tr("If image {template}").format(
                    template=self.get_template_label(step.get("template", ""))
                )
            case "if_any_image":
                templates = ", ".join([self.get_template_label(t) for t in step.get("templates", [])])
                label = self.tr("If any image {templates}").format(templates=templates)
            case "grid_nav":
                label = self.tr("Grid navigation ({rows} rows)").format(rows=step.get("rows", 1))
            case "mouse_click":
                button = step.get("button", "left")
                button_labels = {"left": self.tr("Left"), "right": self.tr("Right"), "middle": self.tr("Middle")}
                button_display = button_labels.get(button, button)
                target = step.get("target", "coordinate")

                if target == "template":
                    label = self.tr("{button} click at {template}").format(
                        button=button_display,
                        template=self.get_template_label(step.get("template", "")),
                    )
                else:
                    label = self.tr("{button} click at ({x}, {y})").format(
                        button=button_display,
                        x=step.get("x", 0),
                        y=step.get("y", 0),
                    )
            case "mouse_move":
                target = step.get("target", "coordinate")

                if target == "template":
                    label = self.tr("Move to {template}").format(
                        template=self.get_template_label(step.get("template", "")),
                    )
                else:
                    label = self.tr("Move to ({x}, {y})").format(
                        x=step.get("x", 0),
                        y=step.get("y", 0),
                    )
            case "mouse_scroll":
                label = self.tr("Scroll {clicks}").format(clicks=step.get("clicks", 3))
            case _:
                label = step_type

        if note:
            label = f"{label} ({note})"

        return label

    def get_template_label(self, template_id: str) -> str:
        if self.current_macro is None:
            return template_id

        template_meta = self.current_macro.templates.get(template_id)

        if template_meta and template_meta.label:
            return template_meta.label

        return template_id

    def handle_action(self, action_id: str) -> None:
        if self.is_recording() and action_id not in ("record_pause", "record_stop", "record_cancel"):
            return

        if self.editing_locked and action_id in (
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
            "wrap_in_repeat",
            "new_macro",
            "duplicate_macro",
            "record",
            "import_macro",
            "export_macro",
            "open_macro_folder",
            "pack_explorer",
            "settings",
        ):
            return

        action = self.actions.get(action_id)

        if action is None:
            return

        action()

    def duplicate_current_macro(self) -> None:
        if self.current_macro is None:
            self.view.set_status_text(self.tr("Select a macro first"))
            return

        new_macro_id = str(int(time.time()))
        new_macro_label = (
            f"{self.current_macro.meta.label} Copy" if self.current_macro.meta.label else f"{new_macro_id} Copy"
        )

        path = macro_path(new_macro_id)

        if path.exists():
            self.view.set_status_text(self.tr("Unable to duplicate macro. Please try again."))
            return

        new_macro = copy.deepcopy(self.current_macro)
        new_macro.meta.id = new_macro_id
        new_macro.meta.label = new_macro_label
        self.macro_model.save(new_macro)

        source_templates = templates_dir(self.current_macro.meta.id)
        destination_templates = templates_dir(new_macro_id)

        if source_templates.exists():
            shutil.copytree(source_templates, destination_templates, dirs_exist_ok=True)

        self.selected_macro_id = new_macro_id
        self.refresh_macro_list()
        self.view.set_status_text(self.tr("Duplicated macro: {name}").format(name=new_macro_label))

    def import_failed(self, content: str) -> None:
        show_message_dialog(self.view.window(), self.tr("Import failed"), content)

    def import_macro(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self.view,
            self.tr("Import Macro"),
            "",
            self.tr("Macro ZIP (*.zip)"),
        )

        if not file_path:
            return

        archive_path = Path(file_path)

        try:
            parsed = inspect_macro_archive(archive_path)
            imported_macro_id = resolve_import_macro_id()

            conflicts = self.find_template_conflicts(imported_macro_id, parsed.template_refs)
            overwrite = False
            if conflicts:
                overwrite = show_confirm_dialog(
                    self.view.window(),
                    self.tr("Template conflict"),
                    self.tr("Overwrite existing templates: {names}").format(names=", ".join(conflicts)),
                )

            result = install_macro_archive(
                archive_path,
                self.macro_model,
                ImportMacroOptions(overwrite_template_conflicts=overwrite),
            )
        except MacroImportError as error:
            self.import_failed(self.tr(str(error)))
            return

        if result.macro_id not in config_model.config.general.macro_order:
            config_model.config.general.macro_order.append(result.macro_id)
            config_model.save()

        self.selected_macro_id = result.macro_id
        self.refresh_macro_list()
        self.view.set_status_text(self.tr("Imported macro: {name}").format(name=result.label))

    def find_template_conflicts(self, macro_id: str, refs: set[str]) -> list[str]:
        return sorted(template_id for template_id in refs if (template_path(macro_id, template_id)).exists())

    def step_tree_refs_from_macro(self, macro: Macro) -> set[str]:
        step_tree = StepTree([step_to_dict(step) for step in macro.steps])
        return step_tree.collect_template_refs()

    def export_current_macro(self) -> None:
        if self.current_macro is None:
            self.view.set_status_text(self.tr("Select a macro first"))
            return

        suggested_path = macro_path(self.current_macro.meta.id).with_suffix(".zip")
        file_path, _ = QFileDialog.getSaveFileName(
            self.view,
            self.tr("Export Macro"),
            str(suggested_path),
            self.tr("Macro ZIP (*.zip)"),
        )

        if not file_path:
            return

        self.sync_macro_steps_from_tree()
        template_refs = self.step_tree_refs_from_macro(self.current_macro)
        template_root = templates_dir(self.current_macro.meta.id)

        try:
            with zipfile.ZipFile(file_path, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr(
                    "macro.json",
                    json.dumps(self.current_macro.to_dict(), indent=2, ensure_ascii=False),
                )

                for template_id in sorted(template_refs):
                    png_path = template_root / f"{template_id}.png"
                    if png_path.exists():
                        archive.write(png_path, f"templates/{template_id}.png")
        except OSError:
            self.view.set_status_text(self.tr("Failed to export macro"))
            return

        macro_label = self.current_macro.meta.label or self.current_macro.meta.id
        self.view.set_status_text(self.tr("Exported macro: {name}").format(name=macro_label))

    def open_settings(self) -> None:
        event_bus.switch_page_requested.emit("settings")

    def open_pack_explorer(self) -> None:
        event_bus.switch_page_requested.emit("packs")

    def quit_application(self) -> None:
        self.view.window().close()

    def add_step_factory(self, step_type: str) -> Step | None:
        factories: dict[str, Callable[[], Step]] = {
            "key": KeyStep,
            "delay": DelayStep,
            "wait_image": WaitImageStep,
            "hold_key_until_gone": HoldKeyUntilGoneStep,
            "text_input": TextInputStep,
            "repeat": RepeatStep,
            "if_image": IfImageStep,
            "if_any_image": IfAnyImageStep,
            "grid_nav": GridNavStep,
            "mouse_click": MouseClickStep,
            "mouse_move": MouseMoveStep,
            "mouse_scroll": MouseScrollStep,
        }

        factory = factories.get(step_type)

        if factory is None:
            return None

        return factory()

    def add_step(self, step_type: str) -> None:
        if self.step_tree is None:
            self.view.set_status_text(self.tr("Select a macro first"))
            return

        new_step = self.add_step_factory(step_type)

        if new_step is None:
            self.view.set_status_text(self.tr("Unknown step type"))
            return

        self.push_undo()

        if self.selected_branch_parent is not None and self.selected_branch_key:
            parent_node = self.step_tree.find_node(self.selected_branch_parent)

            if parent_node is None:
                self.view.set_status_text(self.tr("Select a valid branch first"))
                return

            new_node = self.step_tree.add_step_to_branch(parent_node, self.selected_branch_key, step_to_dict(new_step))
            self.set_selected_step(new_node.step)
            self.save_current_macro()
            return

        target_node = self.selected_step_node()

        if target_node is not None and target_node.step_type == "repeat":
            new_node = self.step_tree.add_step_to_branch(target_node, "steps", step_to_dict(new_step))
            self.set_selected_step(new_node.step)
            self.save_current_macro()
            return

        new_node = self.step_tree.add_step(target_node, step_to_dict(new_step))
        self.set_selected_step(new_node.step)
        self.save_current_macro()

    def duplicate_selected_step(self) -> None:
        if self.step_tree is None:
            self.view.set_status_text(self.tr("Select a macro first"))
            return

        selected = self.selected_step_nodes()
        if not selected:
            self.view.set_status_text(self.tr("Select a step first"))
            return

        self.push_undo()

        duplicated = self.step_tree.duplicate_nodes(selected)
        if not duplicated:
            return

        self.mutate_current_macro()
        self.set_selected_step(duplicated[-1].step)
        self.view.set_status_text(self.tr("Duplicated step"))

    def delete_selected_step(self) -> None:
        if self.step_tree is None:
            self.view.set_status_text(self.tr("Select a macro first"))
            return

        selected = self.selected_step_nodes()
        if not selected:
            self.view.set_status_text(self.tr("Select a step first"))
            return

        selection_index = self.selected_step_flat_index()
        self.push_undo(selection_index)
        template_refs_before = self.step_tree.collect_template_refs()

        for node in reversed(selected):
            self.step_tree.delete_node(node)

        if self.current_macro is not None:
            template_refs_after = self.step_tree.collect_template_refs()
            unused_template_refs = template_refs_before - template_refs_after

            for template_id in sorted(unused_template_refs):
                self.template_service.delete_template(self.current_macro, self.step_tree, template_id)

        self.sync_macro_steps_from_tree()
        self.refresh_step_tree()
        self.save_current_macro()

        if selection_index is not None:
            next_node = self.step_tree.node_at(selection_index) or self.step_tree.node_at(selection_index - 1)
            self.set_selected_step(next_node.step if next_node is not None else None)
        else:
            self.set_selected_step(None)

        self.view.set_status_text(self.tr("Deleted step"))

    def wrap_selected_step_in_repeat(self) -> None:
        if self.step_tree is None:
            self.view.set_status_text(self.tr("Select a macro first"))
            return

        selected = self.selected_step_nodes()
        if not selected:
            self.view.set_status_text(self.tr("Select a step first"))
            return

        top_level = self.step_tree.get_top_level(selected)
        if not top_level:
            return

        self.push_undo()
        wrapped_node = self.step_tree.wrap_in_repeat(top_level)
        self.set_selected_step(wrapped_node.step)
        self.save_current_macro()
        self.view.set_status_text(self.tr("Wrapped step in repeat"))

    def move_selected_step(self, direction: int) -> None:
        if self.step_tree is None:
            self.view.set_status_text(self.tr("Select a macro first"))
            return

        target_node = self.selected_step_node()
        if target_node is None:
            self.view.set_status_text(self.tr("Select a step first"))
            return

        self.push_undo()
        if not self.step_tree.move_step(target_node, direction):
            if self.current_runner is not None and self.undo_stack:
                self.undo_stack.pop()
            self.update_undo_redo_state()
            self.view.set_status_text(self.tr("Cannot move selected step"))
            return

        self.set_selected_step(target_node.step)
        self.save_current_macro()
        self.view.set_status_text(self.tr("Moved step"))

    def run_current_macro(self) -> None:
        if self.is_recording():
            return

        if self.current_runner is None:
            self.view.set_status_text(self.tr("Select a macro first"))
            return

        if self.current_runner.is_running():
            self.current_runner.stop()
            event_bus.macro_running_changed.emit(False)
            self.view.set_status_text(self.tr("Stopping macro: {name}").format(name=self.current_runner.label))
            return

        self.current_runner.start()
        event_bus.macro_running_changed.emit(True)
        self.view.set_status_text(self.tr("Running macro: {name}").format(name=self.current_runner.label))

    def is_recording(self) -> bool:
        recorder = self.current_recorder
        return recorder is not None and recorder.is_running()

    def start_macro_recording(self) -> None:
        if self.current_macro is None or self.step_tree is None:
            self.view.set_status_text(self.tr("Select a macro first"))
            return

        if self.current_runner is not None and self.current_runner.is_running():
            return

        if self.is_recording():
            return

        recorder = MacroRecorder(self.recording_target_rect())

        try:
            recorder.start()
        except RuntimeError as error:
            self.view.set_status_text(self.tr("Failed to start recorder: {error}").format(error=error))
            return

        self.current_recorder = recorder
        self.set_editing_locked(True)
        self.set_recording_controls_locked(True)
        self.show_recording_overlay()
        event_bus.macro_recording_changed.emit(True)
        label = self.current_macro.meta.label or self.current_macro.meta.id
        self.view.set_status_text(self.tr("Recording macro: {name}").format(name=label))

    def recording_target_rect(self):
        if self.current_macro is None or not self.current_macro.meta.target_window:
            return None

        try:
            target_window = window.find_target_window(self.current_macro.meta.target_window)

            if target_window is None:
                return None

            return window.client_rect(target_window)
        except Exception:
            logger.warning("Failed to resolve recording target rect", exc_info=True)
            return None

    def show_recording_overlay(self) -> None:
        if self.recording_overlay is None:
            self.recording_overlay = RecordingOverlay(self.recording_stats, self.view.window())

        self.recording_overlay.move(*config_model.config.general.overlay_position)
        self.recording_overlay.set_paused(False)
        self.recording_overlay.start()

    def hide_recording_overlay(self) -> None:
        if self.recording_overlay is None:
            return

        self.recording_overlay.stop()

    def recording_stats(self) -> tuple[float, int]:
        recorder = self.current_recorder

        if recorder is None:
            return 0.0, 0

        return recorder.elapsed_s(), recorder.event_count()

    def toggle_macro_recording_pause(self) -> None:
        recorder = self.current_recorder

        if recorder is None or not recorder.is_running():
            return

        if recorder.is_paused():
            recorder.resume()
            event_bus.macro_recording_paused_changed.emit(False)
            self.handle_macro_recording_paused_changed(False)
            self.view.set_status_text(self.tr("Recording resumed"))
            return

        recorder.pause()
        event_bus.macro_recording_paused_changed.emit(True)
        self.handle_macro_recording_paused_changed(True)
        self.view.set_status_text(self.tr("Recording paused"))

    def stop_macro_recording(self) -> None:
        recorder = self.current_recorder

        if recorder is None:
            return

        steps = recorder.stop()
        self.current_recorder = None
        self.hide_recording_overlay()
        self.set_editing_locked(False)
        self.set_recording_controls_locked(False)
        event_bus.macro_recording_changed.emit(False)
        event_bus.macro_recording_paused_changed.emit(False)

        if not steps:
            self.view.set_status_text(self.tr("No steps recorded"))
            return

        inserted = self.insert_recorded_steps(steps)

        if not inserted:
            self.view.set_status_text(self.tr("Failed to insert recorded steps"))
            return

        self.view.set_status_text(self.tr("Recorded {count} steps").format(count=len(steps)))

    def cancel_macro_recording(self) -> None:
        recorder = self.current_recorder

        if recorder is not None:
            recorder.cancel()

        self.current_recorder = None
        self.hide_recording_overlay()
        self.set_editing_locked(False)
        self.set_recording_controls_locked(False)
        event_bus.macro_recording_changed.emit(False)
        event_bus.macro_recording_paused_changed.emit(False)
        self.view.set_status_text(self.tr("Recording cancelled"))

    def insert_recorded_steps(self, steps: list[dict]) -> bool:
        if self.step_tree is None:
            return False

        self.push_undo()
        inserted_nodes = []

        if self.selected_branch_parent is not None and self.selected_branch_key:
            parent_node = self.step_tree.find_node(self.selected_branch_parent)

            if parent_node is None:
                return False

            for step in steps:
                inserted_nodes.append(self.step_tree.add_step_to_branch(parent_node, self.selected_branch_key, step))
        else:
            inserted_nodes = self.step_tree.insert_steps_after(self.selected_step_node(), steps)

        if not inserted_nodes:
            return False

        last_step = inserted_nodes[-1].step
        self.set_selected_step(last_step)
        self.save_current_macro()
        return True

    def set_recording_controls_locked(self, locked: bool) -> None:
        toolbar = self.view.toolbar
        toolbar.run_button.setDisabled(locked)
        toolbar.record_button.setDisabled(locked)

    def handle_macro_recording_paused_changed(self, is_paused: bool) -> None:
        if self.recording_overlay is not None:
            self.recording_overlay.set_paused(is_paused)

    def toggle_current_macro_pause(self) -> None:
        if self.current_runner is None or not self.current_runner.is_running():
            return

        if self.current_runner.is_paused():
            self.current_runner.resume()
            return

        self.current_runner.pause()

    def handle_macro_running_changed(self, is_running: bool) -> None:
        self.set_editing_locked(is_running)

        if is_running:
            if self.current_runner is not None:
                self.view.set_status_text(self.tr("Running macro: {name}").format(name=self.current_runner.label))
            return

        if self.current_runner is not None:
            status = self.current_runner.get_status()
            elapsed = self.format_elapsed(status.elapsed_s)

            if status.last_reason == "user_stopped":
                self.view.set_status_text(
                    self.tr("Stopped macro: {name} ({elapsed})").format(name=self.current_runner.label, elapsed=elapsed)
                )
            elif status.last_reason == "done":
                self.view.set_status_text(
                    self.tr("Done: {name} ({elapsed})").format(name=self.current_runner.label, elapsed=elapsed)
                )
            elif status.message:
                translated = self.translate_status_message(status.message)
                self.view.set_status_text(
                    self.tr("{name}: {message} ({elapsed})").format(
                        name=self.current_runner.label,
                        message=translated,
                        elapsed=elapsed,
                    )
                )

    def handle_macro_paused_changed(self, is_paused: bool) -> None:
        if self.current_runner is None:
            return

        if is_paused:
            self.view.set_status_text(self.tr("Paused"))
            return

        if self.current_runner.is_running():
            self.view.set_status_text(self.tr("Running macro: {name}").format(name=self.current_runner.label))

    def translate_status_message(self, message: str) -> str:
        if ": " in message:
            key, value = message.split(": ", 1)
            key_map: dict[str, str] = {
                "missing_templates": self.tr("Missing templates: {names}").format(names=value),
                "Error": self.tr("Error: {detail}").format(detail=value),
                "macro_format": self.tr("Macro format error: {errors}").format(errors=value),
                "wait_timeout": self.tr("Wait timeout: {template}").format(template=value),
                "wait_any_timeout": self.tr("Wait any timeout: {templates}").format(templates=value),
                "mouse_click": self.tr("Mouse click: empty template"),
                "mouse_click_timeout": self.tr("Mouse click timeout: {template}").format(template=value),
                "mouse_move": self.tr("Mouse move: empty template"),
                "mouse_move_timeout": self.tr("Mouse move timeout: {template}").format(template=value),
            }
            if key in key_map:
                return key_map[key]

        simple_map: dict[str, str] = {
            "window_not_found": self.tr("Window not found"),
            "elevation_mismatch": self.tr("Elevation mismatch, do not run target app as admin"),
        }
        if message in simple_map:
            return simple_map[message]

        return message

    def format_elapsed(self, elapsed_s: float) -> str:
        elapsed = int(elapsed_s)
        return f"{elapsed // 60:02d}:{elapsed % 60:02d}"

    def open_logs_folder(self) -> None:
        target = log_dir()
        target.mkdir(parents=True, exist_ok=True)
        os.startfile(target)

    def open_macro_folder(self) -> None:
        target = macros_dir()
        target.mkdir(parents=True, exist_ok=True)
        os.startfile(target)

    def generate_template_id(self) -> str:
        return str(int(time.time()))

    def default_template_label(self, template_id: str) -> str:
        return self.tr("Template {id}").format(id=template_id)

    def launch_region_selector(
        self,
        template_id: str,
        target_display: display.DisplayTarget | None = None,
    ) -> None:
        if self.current_macro is None:
            return

        if target_display is None:
            target_display = display.target_display_for_macro(self.current_macro.meta.target_window)

        selector = RegionSelector(self.current_macro.meta.id, parent=self.view, target_display=target_display)
        selector.region_selected.connect(
            lambda new_template_id, width, height: self.handle_region_captured(
                template_id, new_template_id, width, height
            )
        )
        selector.cancelled.connect(self.view.window().showNormal)
        selector.start()

    def handle_region_captured(self, old_template_id: str, new_template_id: str, width: int, height: int) -> None:
        self.view.window().showNormal()

        if self.selected_step is None or self.current_macro is None:
            return

        self.push_undo()

        self.template_service.apply_captured_template(
            self.current_macro,
            self.selected_step,
            old_template_id,
            new_template_id,
            width,
            height,
        )
        self.mutate_current_macro()

    def handle_template_capture(self, template_id: str) -> None:
        if self.current_macro is None:
            return

        target_display = display.target_display_for_macro(self.current_macro.meta.target_window)

        self.view.window().showMinimized()

        QTimer.singleShot(200, lambda: self.launch_region_selector(template_id, target_display))

    def handle_template_pick(self, template_id: str) -> None:
        if self.selected_step is None or self.current_macro is None:
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self.view, self.tr("Select Template Image"), "", self.tr("PNG Images (*.png)")
        )

        if not file_path:
            return

        self.push_undo()

        self.template_service.pick_template(
            self.current_macro,
            self.selected_step,
            template_id,
            file_path,
        )
        self.mutate_current_macro()

    def handle_template_delete(self, template_id: str) -> None:
        if self.current_macro is None or self.step_tree is None:
            return

        self.template_service.delete_template(self.current_macro, self.step_tree, template_id)
        self.mutate_current_macro()

    def handle_template_add(self) -> None:
        if self.current_macro is None or self.selected_step is None:
            return

        if self.selected_step.get("type") != "if_any_image":
            return

        self.push_undo()

        if not self.template_service.add_template(self.current_macro, self.selected_step):
            return

        self.mutate_current_macro()

    def handle_template_meta_changed(self, template_id: str, field: str, value: str) -> None:
        if self.current_macro is None:
            return

        template_info = self.current_macro.templates.get(template_id)
        if template_info is None or not hasattr(template_info, field):
            return

        old_value = getattr(template_info, field)
        if field == "label":
            new_value: object = value
        elif field in ("capture_width", "capture_height"):
            try:
                new_value = int(value)
            except ValueError:
                return
        elif field == "match_mode":
            if value not in TEMPLATE_MATCH_MODES:
                return

            new_value = value
        else:
            return

        if old_value == new_value:
            return

        self.push_undo(self.selected_step_flat_index())
        if not self.template_service.update_template_meta(self.current_macro, template_id, field, value):
            return

        self.sync_macro_steps_from_tree()
        self.save_current_macro()
        self.refresh_step_tree()

    def register_hotkeys(self) -> None:
        self.hotkey_service.macro_model = self.macro_model
        self.hotkey_service.register_hotkeys()

    def handle_hotkey_triggered(self, hid: int) -> None:
        if self.hotkey_service.is_pause_hotkey(hid):
            self.toggle_current_macro_pause()
            return

        macro_id = self.hotkey_service.macro_id_for_hotkey(hid)
        if macro_id is None:
            return

        macro = self.macro_model.load(macro_id)
        if macro is None or not macro.meta.enabled:
            return

        if self.selected_macro_id == macro_id and self.current_runner is not None and self.current_runner.is_running():
            self.current_runner.stop()
            event_bus.macro_running_changed.emit(False)
            return

        runner = MacroRunner(macro, macro_path=macro_path(macro_id))
        step_tree = StepTree([step_to_dict(step) for step in macro.steps])

        self.selected_macro_id = macro_id
        self.show_loaded_macro(macro, runner, step_tree)
        self.select_macro_list_item(macro_id)

        runner.start()
        event_bus.macro_running_changed.emit(True)

    def select_macro_list_item(self, macro_id: str) -> None:
        macro_list = self.view.left_panel.macro_list
        macro_list.blockSignals(True)

        for index in range(macro_list.count()):
            item = macro_list.item(index)

            if item is None:
                continue

            if item.data(Qt.ItemDataRole.UserRole) == macro_id:
                macro_list.setCurrentItem(item)
                break

        macro_list.blockSignals(False)

    def set_editing_locked(self, locked: bool) -> None:
        self.editing_locked = locked

        for shortcut in self.editing_shortcuts:
            shortcut.setEnabled(not locked)

        toolbar = self.view.toolbar
        toolbar.add_button.setDisabled(locked)
        toolbar.delete_button.setDisabled(locked)
        toolbar.move_up_button.setDisabled(locked)
        toolbar.move_down_button.setDisabled(locked)
        toolbar.undo_button.setDisabled(locked)
        toolbar.redo_button.setDisabled(locked)

        toolbar.record_button.setDisabled(locked)

        left_panel = self.view.left_panel
        left_panel.macro_list.setDisabled(locked)
        left_panel.new_macro_button.setDisabled(locked)

        self.view.center_panel.step_list.setDisabled(locked)

        self.view.right_panel.setDisabled(locked)

        self.view.toolbar.file_menu_button.setDisabled(locked)
        self.view.toolbar.edit_menu_button.setDisabled(locked)

    def highlight_current_step(self) -> None:
        if self.current_runner is None or not self.current_runner.is_running():
            return

        current_path = self.current_runner.current_step_path
        if current_path is None or self.step_tree is None:
            return

        target_node = self.step_tree.find_node_by_path(current_path)
        if target_node is None:
            return

        center_panel = self.view.center_panel

        target_item = None

        for tree_item, step_dict in center_panel.item_to_step.items():
            if step_dict is target_node.step:
                target_item = tree_item
                break

        if target_item is None:
            return

        step_list = center_panel.step_list
        step_list.blockSignals(True)
        step_list.setCurrentItem(target_item)
        step_list.expandItem(target_item)
        step_list.scrollToItem(target_item)
        step_list.blockSignals(False)

    def show_about_dialog(self) -> None:
        dialog = AboutDialog(self.view.window(), __version__)
        dialog.exec()
