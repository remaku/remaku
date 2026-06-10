import webbrowser
from remaku.core.event_bus import event_bus
from remaku.models.config_model import config_model
from remaku.services.macro_runner import MacroRunner
from remaku.version import __version__
from remaku.views.components.about_dialog import AboutDialog
from remaku.views.components.confirm_dialog import ConfirmDialog
from remaku.views.components.message_dialog import MessageDialog
from remaku.views.components.new_macro_dialog import NewMacroDialog
from remaku.views.components.rename_macro_dialog import RenameMacroDialog
from remaku.views.home_view import HomeView


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
        self.step_tree: StepTree | None = None
        self.undo_stacks: dict[str, list[dict]] = {}
        self.redo_stacks: dict[str, list[dict]] = {}
        self.step_clipboard: dict | None = None
        self.toolbar_actions: dict[str, Callable[[], object]] = {
            "about": self.show_about_dialog,
            "support_author": lambda: webbrowser.open("https://github.com/sponsors/nelsonlaidev"),
            "run": self.run_current_macro,
            "open_macro_folder": self.open_macro_folder,
            "open_logs": self.open_logs_folder,
            "new_macro": self.handle_new_macro,
            "settings": self.open_settings,
            "quit": self.quit_application,
            "add_step": lambda: event_bus.show_toolbar_step_menu_requested.emit(),
            "duplicate_step": self.duplicate_selected_step,
            "delete_step": self.delete_selected_step,
            "move_up": lambda: self.move_selected_step(-1),
            "move_down": lambda: self.move_selected_step(1),
            "undo": self.undo,
            "redo": self.redo,
            "cut": self.cut_selected_steps,
            "copy": self.copy_selected_steps,
            "paste": self.paste_steps,
            "duplicate_macro": self.duplicate_current_macro,

        event_bus.action_triggered.connect(self.handle_toolbar_action)
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

        self.register_shortcuts()
        self.update_undo_redo_state()
        self.refresh_macro_list()

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

        self.shortcuts: list[QShortcut] = []

        for key, handler in shortcut_map.items():
            shortcut = QShortcut(QKeySequence(key), self.view)
            shortcut.activated.connect(handler)
            self.shortcuts.append(shortcut)

    def set_current_macro(self, macro: Macro | None) -> None:
        self.current_macro = macro
        self.update_undo_redo_state()

    @property
    def undo_stack(self) -> list[dict]:
        return self.undo_stacks.setdefault(self.selected_macro_id, [])

    @property
    def redo_stack(self) -> list[dict]:
        return self.redo_stacks.setdefault(self.selected_macro_id, [])

    def current_macro_dict(self) -> dict | None:
        if self.current_runner is None:
            return None

        return self.current_runner.macro

    def sync_runner_macro_from_current(self) -> None:
        if self.current_runner is None or self.current_macro is None:
            return

        self.current_runner = MacroRunner(
            self.current_macro,
            macro_path=self.current_runner.macro_path,
        )

    def push_undo(self) -> None:
        macro_dict = self.current_macro_dict()
        if self.current_runner is None or macro_dict is None:
            return

        snapshot = copy.deepcopy(macro_dict)
        self.undo_stack.append(snapshot)

        if len(self.undo_stack) > 50:
            self.undo_stack.pop(0)

        self.redo_stack.clear()
        self.update_undo_redo_state()

    def update_undo_redo_state(self) -> None:
        has_undo = bool(self.current_runner and self.undo_stack)
        has_redo = bool(self.current_runner and self.redo_stack)
        self.view.toolbar.undo_button.setEnabled(has_undo)
        self.view.toolbar.redo_button.setEnabled(has_redo)

    def update_step_action_state(self) -> None:
        node = self.selected_step_node()

        if node is None:
            self.view.toolbar.delete_button.setEnabled(False)
            self.view.toolbar.move_up_button.setEnabled(False)
            self.view.toolbar.move_down_button.setEnabled(False)
            return

        self.view.toolbar.delete_button.setEnabled(True)
        assert self.step_tree is not None
        self.view.toolbar.move_up_button.setEnabled(self.step_tree.can_move(node, -1))
        self.view.toolbar.move_down_button.setEnabled(self.step_tree.can_move(node, 1))

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

    def restore_macro_state(self, macro_dict: dict) -> None:
        if self.current_runner is None:
            return

        old_steps = list(self.current_macro.steps) if self.current_macro else []

        restored_macro = Macro.from_dict(copy.deepcopy(macro_dict))
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

        self.select_after_undo_redo(old_steps, list(restored_macro.steps))

        self.macro_model.save(restored_macro)


    def undo(self) -> None:
        if self.current_runner is None or not self.undo_stack:
            return

        current_macro_dict = self.current_macro_dict()
        if current_macro_dict is not None:
            self.redo_stack.append(copy.deepcopy(current_macro_dict))

        restored_state = self.undo_stack.pop()
        self.restore_macro_state(restored_state)
        self.update_undo_redo_state()

    def redo(self) -> None:
        if self.current_runner is None or not self.redo_stack:
            return

        current_macro_dict = self.current_macro_dict()
        if current_macro_dict is not None:
            self.undo_stack.append(copy.deepcopy(current_macro_dict))

        restored_state = self.redo_stack.pop()
        self.restore_macro_state(restored_state)
        self.update_undo_redo_state()

    def collect_template_refs_from_steps(self, steps: list[dict]) -> set[str]:
        return StepTree(copy.deepcopy(steps)).collect_template_refs()

    def copy_selected_steps(self) -> None:
        if self.step_tree is None:
            return

        target_node = self.selected_step_node()
        if target_node is None:
            return

        top_level = self.step_tree.get_top_level([target_node])
        steps = [copy.deepcopy(node.step) for node in top_level]
        if not steps or self.current_macro is None:
            return

        refs = self.collect_template_refs_from_steps(steps)

        template_data = {
            name: template_path(self.current_macro.meta.name, name).read_bytes()
            for name in refs
            if (template_path(self.current_macro.meta.name, name)).exists()
        }
        template_meta = {
            name: copy.deepcopy(self.current_macro.to_dict().get("templates", {}).get(name, {}))
            for name in refs
            if name in self.current_macro.to_dict().get("templates", {})
        }
        self.step_clipboard = {
            "steps": steps,
            "templates": template_data,
            "template_meta": template_meta,
        }

    def cut_selected_steps(self) -> None:
        self.copy_selected_steps()
        if self.step_clipboard:
            self.delete_selected_step()

    def paste_steps(self) -> None:
        if self.step_tree is None or not self.step_clipboard or self.current_macro is None:
            return

        self.push_undo()

        clipboard_steps = copy.deepcopy(self.step_clipboard.get("steps", []))
        if not clipboard_steps:
            return

        target_node = self.selected_step_node()
        inserted_nodes = self.step_tree.insert_steps_after(target_node, clipboard_steps)

        templates_dir(self.current_macro.meta.name).mkdir(parents=True, exist_ok=True)

        for name, data in self.step_clipboard.get("templates", {}).items():
            destination = template_path(self.current_macro.meta.name, name)
            if not destination.exists():
                destination.write_bytes(data)

        for name, meta in self.step_clipboard.get("template_meta", {}).items():
            if name not in self.current_macro.templates:
                self.current_macro.templates[name] = (
                    self.current_macro.templates.get(name)
                    or Macro.from_dict({"meta": {}, "templates": {name: meta}, "steps": []}).templates[name]
                )
                continue

            current_meta = self.current_macro.templates[name]
            if not current_meta.label and "label" in meta:
                current_meta.label = str(meta["label"])
            if not current_meta.capture_width and "capture_width" in meta:
                current_meta.capture_width = int(meta["capture_width"])
            if not current_meta.capture_height and "capture_height" in meta:
                current_meta.capture_height = int(meta["capture_height"])

        self.selected_step = inserted_nodes[0].step if inserted_nodes else self.selected_step
        self.mutate_current_macro()

    def refresh_macro_list(self) -> None:
        macro_items = self.macro_model.list_macros()
        ordered_macro_items = self.sort_macro_items(macro_items)
        list_items = [(item.name, item.label) for item in ordered_macro_items]

        if self.selected_macro_id not in {item.name for item in ordered_macro_items}:
            self.selected_macro_id = ""

        if not self.selected_macro_id and ordered_macro_items:
            self.selected_macro_id = ordered_macro_items[0].name

        self.view.left_panel.set_macro_list(list_items, self.selected_macro_id)

        if self.selected_macro_id:
            self.load_selected_macro(self.selected_macro_id)
            return

        self.show_empty_macro_state()

    def sort_macro_items(self, macro_items: list[MacroSummary]) -> list[MacroSummary]:
        order_index = {name: index for index, name in enumerate(config_model.config.general.macro_order)}

        return sorted(
            macro_items,
            key=lambda item: (
                order_index.get(item.name, len(order_index)),
                item.label.lower(),
                item.name.lower(),
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
                self.show_message_dialog(self.view.tr("New Macro"), self.view.tr("Macro name cannot be empty."))
                continue

            new_macro_id = str(int(time.time()))

            macro = Macro(meta=MacroMeta(name=new_macro_id, label=new_macro_label))
            self.macro_model.save(macro)

            self.selected_macro_id = new_macro_id
            self.refresh_macro_list()
            self.view.set_status_text(self.view.tr("Created macro: {name}").format(name=new_macro_label))

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
        macro = self.macro_model.load(macro_id)

        if macro is None:
            self.view.set_status_text(self.view.tr("Failed to load macro: {name}").format(name=macro_id))
            return

        current_label = macro.meta.label or macro_id

        while True:
            dialog = RenameMacroDialog(self.view.window(), current_label)
            accepted = bool(dialog.exec())

            if not accepted:
                return

            new_label = dialog.value()

            if not new_label:
                self.show_message_dialog(self.view.tr("Rename Macro"), self.view.tr("Macro name cannot be empty."))
                continue

            if new_label == current_label:
                return

            macro.meta.label = new_label
            self.macro_model.save(macro)

            self.refresh_macro_list()
            self.view.set_status_text(self.view.tr("Renamed macro: {name}").format(name=new_label))

            return

    def handle_macro_delete(self, macro_id: str) -> None:
        macro = self.macro_model.load(macro_id)
        macro_label = macro.meta.label if macro is not None and macro.meta.label else macro_id

        confirmed = self.show_confirm_dialog(
            self.view.tr("Delete Macro"),
            self.view.tr('Are you sure you want to delete "{name}"?').format(name=macro_label),
            self.view.tr("Delete"),
        )

        if not confirmed:
            return

        if not self.macro_model.delete(macro_id):
            self.show_message_dialog(self.view.tr("Delete Macro"), self.view.tr("Unable to delete the macro."))
            return

        template_dir = templates_dir(macro_id)
        if template_dir.exists():
            shutil.rmtree(template_dir)

        config_model.config.general.macro_order = [
            name for name in config_model.config.general.macro_order if name != macro_id
        ]
        config_model.save()

        if self.selected_macro_id == macro_id:
            self.selected_macro_id = ""

        self.refresh_macro_list()
        self.view.set_status_text(self.view.tr("Deleted macro: {name}").format(name=macro_label))

    def handle_macro_duplicate(self, macro_id: str) -> None:
        if self.selected_macro_id != macro_id:
            self.selected_macro_id = macro_id
            self.load_selected_macro(macro_id)

        self.duplicate_current_macro()

    def handle_step_selected(self, step: dict | None) -> None:
        self.selected_branch_parent = None
        self.selected_branch_key = ""
        self.selected_step = step
        self.show_step_selection(step)
        self.update_step_action_state()

    def handle_branch_selected(self, parent_step: dict | None, branch_key: str) -> None:
        self.selected_step = None
        self.selected_branch_parent = parent_step
        self.selected_branch_key = branch_key
        self.show_step_selection(None)
        self.update_step_action_state()

    def selected_step_node(self) -> StepNode | None:
        if self.step_tree is None or self.selected_step is None:
            return None

        return self.step_tree.find_node(self.selected_step)

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
        self.view.set_status_text(self.view.tr("Failed to load macro: {name}").format(name=macro_id))

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

        self.view.right_panel.show_step_properties(self.current_macro, self.describe_step(step), parsed_step)

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

        self.step_tree.sync_from_tree()
        self.current_macro.steps = [parse_step(step) for step in self.step_tree.steps]

    def build_step_items(self) -> list[dict]:
        if self.step_tree is None:
            return []

        return [self.build_step_item(node) for node in self.step_tree.root_nodes]

    def refresh_step_tree(self) -> None:
        selected_branch = None
        if self.selected_branch_parent is not None and self.selected_branch_key:
            selected_branch = (self.selected_branch_parent, self.selected_branch_key)

        self.view.center_panel.set_step_tree(self.build_step_items(), self.selected_step, selected_branch)

    def show_macro_properties(self, macro: Macro | None) -> None:
        self.view.right_panel.show_macro_properties(macro)

    def build_step_item(self, node: StepNode) -> dict:
        children: list[dict[str, Any]] = []

        if node.step_type == "repeat":
            child_list = node.get_child_list("steps")
            children = [self.build_step_item(child) for child in child_list]
        else:
            for branch_key, child_list in node.child_lists():
                branch_children = [self.build_step_item(child) for child in child_list]
                children.append(
                    {
                        "label": self.branch_label(branch_key, node.step),
                        "branch": (node.step, branch_key),
                        "children": branch_children,
                    }
                )
        return {
            "label": self.describe_step(node.step),
            "step": node.step,
            "children": children,
        }

    def branch_label(self, branch_key: str, step: dict | None = None) -> str:
        if step is not None and step.get("type") == "if_any_image":
            return self.get_template_label(branch_key)

        labels = {
            "steps": self.view.tr("Steps"),
            "then": self.view.tr("Then"),
            "else": self.view.tr("Else"),
            "on_next_row": self.view.tr("On Next Row"),
            "on_next_col": self.view.tr("On Next Column"),
        }

        return labels.get(branch_key, branch_key.replace("_", " ").title())

    def branch_steps(self, parent_step: dict, branch_key: str) -> list[Step]:
        parent_node = self.step_tree.find_node(parent_step) if self.step_tree is not None else None
        if parent_node is None:
            return []

        return [parse_step(child.step) for child in parent_node.get_child_list(branch_key)]

    def describe_step(self, step: dict) -> str:
        step_type = step.get("type", "unknown")

        match step_type:
            case "key":
                return self.view.tr("Press {key}").format(key=step.get("key", ""))
            case "delay":
                return self.view.tr("Wait {ms} ms").format(ms=step.get("ms", 0))
            case "wait_image":
                return self.view.tr("Wait for {template}").format(
                    template=self.get_template_label(step.get("template", ""))
                )
            case "hold_key_until_gone":
                return self.view.tr("Hold {key} until {template} gone").format(
                    key=step.get("key", ""),
                    template=self.get_template_label(step.get("template", "")),
                )
            case "repeat":
                return self.view.tr("Repeat {count} times").format(count=step.get("count", 1))
            case "if_image":
                return self.view.tr("If image {template}").format(
                    template=self.get_template_label(step.get("template", ""))
                )
            case "if_any_image":
                templates = ", ".join([self.get_template_label(t) for t in step.get("templates", [])])
                return self.view.tr("If any image {templates}").format(templates=templates)
            case "grid_nav":
                return self.view.tr("Grid navigation ({rows} rows)").format(rows=step.get("rows", 1))
            case _:
                return step_type

    def get_template_label(self, template_id: str) -> str:
        if self.current_macro is None:
            return template_id

        template_meta = self.current_macro.templates.get(template_id)

        if template_meta and template_meta.label:
            return template_meta.label

        return template_id

    def handle_toolbar_action(self, action_id: str) -> None:
        action = self.toolbar_actions.get(action_id)

        if action is None:
            return

        action()

    def duplicate_current_macro(self) -> None:
        if self.current_macro is None:
            self.view.set_status_text(self.view.tr("Select a macro first"))
            return

        new_macro_id = str(int(time.time()))
        new_marco_label = (
            f"{self.current_macro.meta.label} Copy" if self.current_macro.meta.label else f"{new_macro_id} Copy"
        )

        path = macro_path(new_macro_id)

        if path.exists():
            self.view.set_status_text(self.view.tr("Unable to duplicate macro. Please try again."))
            return

        new_macro = copy.deepcopy(self.current_macro)
        new_macro.meta.name = new_macro_id
        new_macro.meta.label = new_marco_label
        self.macro_model.save(new_macro)

        source_templates = templates_dir(self.current_macro.meta.name)
        destination_templates = templates_dir(new_macro_id)

        if source_templates.exists():
            shutil.copytree(source_templates, destination_templates, dirs_exist_ok=True)

        self.selected_macro_id = new_macro_id
        self.refresh_macro_list()
        self.view.set_status_text(self.view.tr("Duplicated macro: {name}").format(name=new_marco_label))

    def show_message_dialog(self, title: str, content: str) -> None:
        dialog = MessageDialog(title, content, self.view.window())
        dialog.exec()

    def show_confirm_dialog(self, title: str, content: str, yes_text: str = "OK") -> bool:
        dialog = ConfirmDialog(title, content, self.view.window())
        dialog.yesButton.setText(yes_text)
        return bool(dialog.exec())

    def import_failed(self, content: str) -> None:
        self.show_message_dialog(self.view.tr("Import failed"), content)

    def import_macro(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self.view,
            self.view.tr("Import Macro"),
            "",
            self.view.tr("Macro ZIP (*.zip)"),
        )

        if not file_path:
            return

        try:
            with zipfile.ZipFile(file_path, "r") as archive:
                archive_names = set(archive.namelist())
                if "macro.json" not in archive_names:
                    self.import_failed(self.view.tr("macro.json is missing from the archive"))
                    return

                raw_macro = json.loads(archive.read("macro.json"))
                if not isinstance(raw_macro, dict):
                    self.import_failed(self.view.tr("Invalid macro data"))
                    return

                meta_data = raw_macro.get("meta")
                if not isinstance(meta_data, dict) or not meta_data.get("name"):
                    self.import_failed(self.view.tr("Macro metadata is invalid"))
                    return

                if not isinstance(raw_macro.get("steps"), list):
                    self.import_failed(self.view.tr("Macro steps are invalid"))
                    return

                refs = StepTree(raw_macro["steps"]).collect_template_refs()
                missing_templates = sorted(name for name in refs if f"templates/{name}.png" not in archive_names)
                if missing_templates:
                    self.import_failed(
                        self.view.tr("Missing templates: {names}").format(names=", ".join(missing_templates))
                    )
                    return

                imported_macro_id = str(meta_data["name"])
                destination = macro_path(imported_macro_id)
                if destination.exists():
                    imported_macro_id = self.resolve_timestamp_macro_name()
                    destination = macro_path(imported_macro_id)
                    meta_data["name"] = imported_macro_id

                conflicts = self.find_template_conflicts(imported_macro_id, refs)
                overwrite = False
                if conflicts:
                    overwrite = self.show_confirm_dialog(
                        self.view.tr("Template conflict"),
                        self.view.tr("Overwrite existing templates: {names}").format(names=", ".join(conflicts)),
                    )

                raw_templates = raw_macro.setdefault("templates", {})
                if not isinstance(raw_templates, dict):
                    raw_templates = {}
                    raw_macro["templates"] = raw_templates

                template_dir = templates_dir(imported_macro_id)
                template_dir.mkdir(parents=True, exist_ok=True)

                for name in refs:
                    png_destination = template_dir / f"{name}.png"
                    if not png_destination.exists() or (overwrite and name in conflicts):
                        png_destination.write_bytes(archive.read(f"templates/{name}.png"))

                    legacy_meta_path = f"templates/{name}.json"
                    if legacy_meta_path not in archive_names:
                        continue

                    try:
                        legacy_meta = json.loads(archive.read(legacy_meta_path))
                    except (OSError, ValueError):
                        continue

                    if not isinstance(legacy_meta, dict):
                        continue

                    entry = raw_templates.get(name, {"label": name})
                    if not isinstance(entry, dict):
                        entry = {"label": name}

                    for key in ("capture_width", "capture_height"):
                        if key in legacy_meta and key not in entry:
                            entry[key] = legacy_meta[key]

                    raw_templates[name] = entry
        except zipfile.BadZipFile:
            self.import_failed(self.view.tr("Invalid zip file"))
            return
        except (OSError, json.JSONDecodeError, ValueError):
            self.import_failed(self.view.tr("Failed to import macro"))
            return

        imported_macro = Macro.from_dict(raw_macro)
        imported_macro.meta.name = imported_macro_id
        if not imported_macro.meta.label:
            imported_macro.meta.label = imported_macro_id

        self.macro_model.save(imported_macro)

        if imported_macro_id not in config_model.config.general.macro_order:
            config_model.config.general.macro_order.append(imported_macro_id)
            config_model.save()

        self.selected_macro_id = imported_macro_id
        self.refresh_macro_list()
        self.view.set_status_text(self.view.tr("Imported macro: {name}").format(name=imported_macro.meta.label))

    def find_template_conflicts(self, macro_name: str, refs: set[str]) -> list[str]:
        return sorted(name for name in refs if (template_path(macro_name, name)).exists())

    def resolve_timestamp_macro_name(self) -> str:
        existing_names = {item.name for item in self.macro_model.list_macros()}
        base = int(time.time())

        offset = 0
        while True:
            candidate = str(base + offset)
            if candidate not in existing_names:
                return candidate
            offset += 1

    def step_tree_refs_from_macro(self, macro: Macro) -> set[str]:
        step_tree = StepTree([step_to_dict(step) for step in macro.steps])
        return step_tree.collect_template_refs()

    def export_current_macro(self) -> None:
        if self.current_macro is None:
            self.view.set_status_text(self.view.tr("Select a macro first"))
            return

        suggested_path = macro_path(self.current_macro.meta.name).with_suffix(".zip")
        file_path, _ = QFileDialog.getSaveFileName(
            self.view,
            self.view.tr("Export Macro"),
            str(suggested_path),
            self.view.tr("Macro ZIP (*.zip)"),
        )

        if not file_path:
            return

        self.sync_macro_steps_from_tree()
        template_refs = self.step_tree_refs_from_macro(self.current_macro)
        template_root = templates_dir(self.current_macro.meta.name)

        try:
            with zipfile.ZipFile(file_path, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr(
                    "macro.json",
                    json.dumps(self.current_macro.to_dict(), indent=2, ensure_ascii=False),
                )

                for name in sorted(template_refs):
                    png_path = template_root / f"{name}.png"
                    if png_path.exists():
                        archive.write(png_path, f"templates/{name}.png")
        except OSError:
            self.view.set_status_text(self.view.tr("Failed to export macro"))
            return

        self.view.set_status_text(self.view.tr("Exported macro: {name}").format(name=self.current_macro.meta.name))

    def quit_application(self) -> None:
        self.view.window().close()

    def add_step_factory(self, step_type: str) -> Step | None:
        factories: dict[str, Callable[[], Step]] = {
            "key": KeyStep,
            "delay": DelayStep,
            "wait_image": WaitImageStep,
            "hold_key_until_gone": HoldKeyUntilGoneStep,
            "repeat": RepeatStep,
            "if_image": IfImageStep,
            "if_any_image": IfAnyImageStep,
            "grid_nav": GridNavStep,
        }

        factory = factories.get(step_type)

        if factory is None:
            return None

        return factory()

    def add_step(self, step_type: str) -> None:
        if self.step_tree is None:
            self.view.set_status_text(self.view.tr("Select a macro first"))
            return

        new_step = self.add_step_factory(step_type)

        if new_step is None:
            self.view.set_status_text(self.view.tr("Unknown step type"))
            return

        self.push_undo()

        if self.selected_branch_parent is not None and self.selected_branch_key:
            parent_node = self.step_tree.find_node(self.selected_branch_parent)

            if parent_node is None:
                self.view.set_status_text(self.view.tr("Select a valid branch first"))
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
            self.view.set_status_text(self.view.tr("Select a macro first"))
            return

        target_node = self.selected_step_node()
        if target_node is None:
            self.view.set_status_text(self.view.tr("Select a step first"))
            return

        self.push_undo()

        duplicated = self.step_tree.duplicate_nodes([target_node])
        if not duplicated:
            return

        self.set_selected_step(duplicated[0].step)
        self.save_current_macro()
        self.view.set_status_text(self.view.tr("Duplicated step"))

    def delete_selected_step(self) -> None:
        if self.step_tree is None:
            self.view.set_status_text(self.view.tr("Select a macro first"))
            return

        target_node = self.selected_step_node()
        if target_node is None:
            self.view.set_status_text(self.view.tr("Select a step first"))
            return

        self.push_undo()

        if target_node.parent is not None:
            next_selection = target_node.next_sibling() or target_node.prev_sibling() or target_node.parent
        else:
            root_nodes = self.step_tree.root_nodes
            idx = next((i for i, n in enumerate(root_nodes) if n is target_node), -1)
            if idx >= 0:
                next_selection = (
                    root_nodes[idx + 1] if idx + 1 < len(root_nodes) else (root_nodes[idx - 1] if idx > 0 else None)
                )
            else:
                next_selection = None

        self.step_tree.delete_node(target_node)
        self.set_selected_step(next_selection.step if next_selection is not None else None)
        self.save_current_macro()
        self.view.set_status_text(self.view.tr("Deleted step"))

    def move_selected_step(self, direction: int) -> None:
        if self.step_tree is None:
            self.view.set_status_text(self.view.tr("Select a macro first"))
            return

        target_node = self.selected_step_node()
        if target_node is None:
            self.view.set_status_text(self.view.tr("Select a step first"))
            return

        self.push_undo()
        if not self.step_tree.move_step(target_node, direction):
            if self.current_runner is not None and self.undo_stack:
                self.undo_stack.pop()
            self.update_undo_redo_state()
            self.view.set_status_text(self.view.tr("Cannot move selected step"))
            return

        self.set_selected_step(target_node.step)
        self.save_current_macro()
        self.view.set_status_text(self.view.tr("Moved step"))

    def run_current_macro(self) -> None:
        if self.current_runner is None:
            self.view.set_status_text(self.view.tr("Select a macro first"))
            return

        if self.current_runner.is_running():
            self.current_runner.stop()
            event_bus.macro_running_changed.emit(False)
            self.view.set_status_text(self.view.tr("Stopping macro: {name}").format(name=self.current_runner.label))
            return

        self.current_runner.start()
        event_bus.macro_running_changed.emit(True)
        self.view.set_status_text(self.view.tr("Running macro: {name}").format(name=self.current_runner.label))

    def handle_macro_running_changed(self, is_running: bool) -> None:
        if is_running:
            if self.current_runner is not None:
                self.view.set_status_text(self.view.tr("Running macro: {name}").format(name=self.current_runner.label))
            return

        if self.current_runner is not None:
            status = self.current_runner.get_status()
            if status.last_reason == "user_stopped":
                self.view.set_status_text(self.view.tr("Stopped macro: {name}").format(name=self.current_runner.label))
            elif status.last_reason == "done":
                self.view.set_status_text(self.view.tr("Done: {name}").format(name=self.current_runner.label))
            elif status.message:
                self.view.set_status_text(f"{self.current_runner.label}: {status.message}")

    def open_logs_folder(self) -> None:
        target = log_dir()
        target.mkdir(parents=True, exist_ok=True)
        os.startfile(target)

    def open_macro_folder(self) -> None:
        target = macros_dir()
        target.mkdir(parents=True, exist_ok=True)
        os.startfile(target)

    def launch_region_selector(self, template_id: str) -> None:
        if self.current_macro is None:
            return

        selector = RegionSelector(self.current_macro.meta.name, parent=self.view)
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

        old_png = template_path(self.current_macro.meta.name, old_template_id)
        if old_png.exists():
            old_png.unlink()

        old_meta = self.current_macro.templates.pop(old_template_id, None)

        new_meta = self.current_macro.templates.get(new_template_id)
        if new_meta is None:
            new_meta = TemplateInfo()
            self.current_macro.templates[new_template_id] = new_meta

        new_meta.capture_width = width
        new_meta.capture_height = height

        if old_meta is not None and old_meta.label and not new_meta.label:
            new_meta.label = old_meta.label
        else:
            new_meta.label = self.view.tr("Template {id}").format(id=new_template_id)

        step_type = self.selected_step.get("type", "")

        if step_type == "if_any_image":
            branches = self.selected_step.setdefault("branches", {})
            if old_template_id in branches:
                branches[new_template_id] = branches.pop(old_template_id)
            self.selected_step["templates"] = [
                new_template_id if t == old_template_id else t for t in self.selected_step.get("templates", [])
            ]
        else:
            if self.selected_step.get("template") == old_template_id:
                self.selected_step["template"] = new_template_id

        self.mutate_current_macro()

    def handle_template_capture(self, template_id: str) -> None:
        if self.current_macro is None:
            return

        self.view.window().showMinimized()

        QTimer.singleShot(200, lambda: self.launch_region_selector(template_id))

    def handle_template_pick(self, template_id: str) -> None:
        if self.selected_step is None or self.current_macro is None:
            return

        new_template_id = str(int(time.time()))

        file_path, _ = QFileDialog.getOpenFileName(
            self.view, self.view.tr("Select Template Image"), "", self.view.tr("PNG Images (*.png)")
        )

        if not file_path:
            return

        destination = template_path(self.current_macro.meta.name, new_template_id)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(file_path, destination)

        screen = QApplication.primaryScreen()
        if screen is None:
            raise RuntimeError("No primary screen is available")

        pixmap = screen.grabWindow(0)
        capture_width = pixmap.width()
        capture_height = pixmap.height()

        old_png = template_path(self.current_macro.meta.name, template_id)
        if old_png.exists():
            old_png.unlink()

        old_meta = self.current_macro.templates.pop(template_id, None)

        new_meta = self.current_macro.templates.get(new_template_id)
        if new_meta is None:
            new_meta = TemplateInfo()
            self.current_macro.templates[new_template_id] = new_meta

        new_meta.capture_width = capture_width
        new_meta.capture_height = capture_height

        if old_meta is not None and old_meta.label and not new_meta.label:
            new_meta.label = old_meta.label
        else:
            new_meta.label = self.view.tr("Template {id}").format(id=new_template_id)

        step_type = self.selected_step.get("type", "")

        if step_type == "if_any_image":
            branches = self.selected_step.setdefault("branches", {})
            if template_id in branches:
                branches[new_template_id] = branches.pop(template_id)
            self.selected_step["templates"] = [
                new_template_id if t == template_id else t for t in self.selected_step.get("templates", [])
            ]
        else:
            if self.selected_step.get("template") == template_id:
                self.selected_step["template"] = new_template_id

        self.mutate_current_macro()

    def handle_template_delete(self, template_id: str) -> None:
        if self.current_macro is None or self.step_tree is None:
            return

        png_path = template_path(self.current_macro.meta.name, template_id)
        if png_path.exists():
            png_path.unlink()

        self.current_macro.templates.pop(template_id, None)

        for node in self.step_tree.flatten():
            step = node.step

            if step.get("template") == template_id:
                step["template"] = ""

            if "templates" in step:
                step["templates"] = [t for t in step["templates"] if t != template_id]
                step.setdefault("branches", {}).pop(template_id, None)

        self.mutate_current_macro()

    def handle_template_add(self) -> None:
        if self.current_macro is None or self.selected_step is None:
            return

        if self.selected_step.get("type") != "if_any_image":
            return

        new_template_id = str(int(time.time()))
        self.current_macro.templates[new_template_id] = TemplateInfo()
        self.selected_step.setdefault("templates", []).append(new_template_id)
        self.mutate_current_macro()

    def show_about_dialog(self) -> None:
        dialog = AboutDialog(self.view.window(), __version__)
        dialog.exec()
