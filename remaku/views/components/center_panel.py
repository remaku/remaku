from typing import Any

from PySide6.QtCore import QModelIndex, QPoint, Qt
from PySide6.QtGui import QIcon, QKeySequence
from PySide6.QtWidgets import QTreeWidgetItem, QVBoxLayout
from qfluentwidgets import Action, BodyLabel, CardWidget, RoundMenu, TreeWidget

from remaku.core.event_bus import event_bus
from remaku.resources.icon import RemakuIcon

STEP_TYPE_ICONS = {
    "key": RemakuIcon.KEYBOARD,
    "delay": RemakuIcon.CLOCK,
    "text_input": RemakuIcon.KEYBOARD,
    "wait_image": RemakuIcon.IMAGE,
    "hold_key_until_gone": RemakuIcon.HAND,
    "repeat": RemakuIcon.REPEAT,
    "if_image": RemakuIcon.SCAN_SEARCH,
    "if_any_image": RemakuIcon.IMAGES,
    "grid_nav": RemakuIcon.GRID_3X3,
}


class CenterPanel(CardWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.item_to_step: dict[QTreeWidgetItem, object] = {}
        self.item_to_branch: dict[QTreeWidgetItem, tuple[object, str]] = {}
        self.item_to_state_key: dict[QTreeWidgetItem, object] = {}
        self.has_clipboard = False

        event_bus.clipboard_changed.connect(self.set_has_clipboard)

        self.init_ui()

    def init_ui(self):
        self.content_layout = QVBoxLayout(self)
        self.content_layout.setContentsMargins(8, 8, 8, 8)

        self.add_step_list()
        self.add_empty_label()

        self.update_empty_state()

    def set_step_tree(
        self,
        items: list[dict[str, Any]],
        selected_step: object | None = None,
        selected_branch: tuple[object, str] | None = None,
    ) -> None:
        collapsed_keys = self.capture_collapsed_state()

        self.step_list.blockSignals(True)
        self.step_list.clear()
        self.item_to_step = {}
        self.item_to_branch = {}
        self.item_to_state_key = {}
        selected_item: QTreeWidgetItem | None = None

        for item_data in items:
            item = self.build_tree_item(item_data)
            self.step_list.addTopLevelItem(item)

        if selected_step is not None:
            for tree_item, step in self.item_to_step.items():
                if step is selected_step:
                    selected_item = tree_item
                    break

        if selected_item is None and selected_branch is not None:
            selected_parent, selected_key = selected_branch
            for tree_item, branch in self.item_to_branch.items():
                parent_step, branch_key = branch
                if parent_step is selected_parent and branch_key == selected_key:
                    selected_item = tree_item
                    break

        self.step_list.expandAll()
        self.apply_collapsed_state(collapsed_keys)

        if selected_item is not None:
            self.expand_item_ancestors(selected_item)

        self.step_list.blockSignals(False)

        if selected_item is not None:
            self.step_list.setCurrentItem(selected_item)
        else:
            event_bus.step_selected.emit(None)

        self.update_empty_state()

    def clear_selection(self) -> None:
        self.step_list.clearSelection()
        event_bus.branch_selected.emit(None, "")
        event_bus.step_selected.emit(None)

    def capture_collapsed_state(self) -> set[object]:
        collapsed_keys: set[object] = set()

        for item, state_key in self.item_to_state_key.items():
            if item.childCount() > 0 and not item.isExpanded():
                collapsed_keys.add(state_key)

        return collapsed_keys

    def apply_collapsed_state(self, collapsed_keys: set[object]) -> None:
        for item, state_key in self.item_to_state_key.items():
            if item.childCount() > 0:
                item.setExpanded(state_key not in collapsed_keys)

    def expand_item_ancestors(self, item: QTreeWidgetItem) -> None:
        parent = item.parent()

        while parent is not None:
            parent.setExpanded(True)
            parent = parent.parent()

    def build_tree_item(self, item_data: dict[str, Any]) -> QTreeWidgetItem:
        item = QTreeWidgetItem([item_data["label"]])
        state_key = item_data.get("state_key")

        if state_key is not None:
            self.item_to_state_key[item] = state_key

        if "branch" in item_data:
            item.setIcon(0, QIcon(RemakuIcon.CORNER_DOWN_RIGHT.path()))
            parent_step, branch_key = item_data["branch"]
            self.item_to_branch[item] = (parent_step, branch_key)
        else:
            step = item_data["step"]
            step_type = str(step.get("type", "")) if isinstance(step, dict) else ""
            step_icon = STEP_TYPE_ICONS.get(step_type)

            if step_icon is not None:
                item.setIcon(0, QIcon(step_icon.path()))

            self.item_to_step[item] = step

        for child_data in item_data.get("children", []):
            item.addChild(self.build_tree_item(child_data))

        return item

    def handle_step_selected(self, current: QTreeWidgetItem | None) -> None:
        if current is not None and current in self.item_to_branch:
            parent_step, branch_key = self.item_to_branch[current]
            event_bus.step_selected.emit(None)
            event_bus.branch_selected.emit(parent_step, branch_key)
            return

        event_bus.branch_selected.emit(None, "")
        step = self.item_to_step.get(current) if current is not None else None
        event_bus.step_selected.emit(step)

    def update_empty_state(self) -> None:
        has_steps = self.step_list.topLevelItemCount() > 0
        self.step_list.setVisible(has_steps)
        self.empty_label.setVisible(not has_steps)

    def add_step_list(self) -> None:
        self.step_list = TreeWidget(self)
        self.step_list.setHeaderHidden(True)
        self.step_list.setSelectionMode(TreeWidget.SelectionMode.ExtendedSelection)
        self.step_list.currentItemChanged.connect(self.handle_step_selected)
        self.step_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.step_list.customContextMenuRequested.connect(self.handle_context_menu)

        original_mouse_press = self.step_list.mousePressEvent

        def custom_mouse_press(event):
            item = self.step_list.itemAt(event.position().toPoint())
            if item is None:
                self.step_list.clearSelection()
                self.step_list.setCurrentIndex(QModelIndex())
                self.handle_step_selected(None)
                return
            original_mouse_press(event)

        self.step_list.mousePressEvent = custom_mouse_press

        self.content_layout.addWidget(self.step_list, 1)

    def add_empty_label(self) -> None:
        self.empty_label = BodyLabel(self.tr("No steps yet"), self)
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setWordWrap(True)
        self.content_layout.addWidget(self.empty_label)

    def handle_context_menu(self, pos: QPoint) -> None:
        item = self.step_list.itemAt(pos)

        if item is None or item in self.item_to_branch or item not in self.item_to_step:
            return

        menu = RoundMenu(parent=self)

        has_selection = bool(self.step_list.selectedItems())
        has_clipboard = self.has_clipboard

        copy = Action(self.tr("Copy"), self)
        copy.setEnabled(has_selection)
        copy.setShortcut(QKeySequence("Ctrl+C"))
        copy.triggered.connect(lambda: event_bus.action_triggered.emit("copy"))
        menu.addAction(copy)

        cut = Action(self.tr("Cut"), self)
        cut.setEnabled(has_selection)
        cut.setShortcut(QKeySequence("Ctrl+X"))
        cut.triggered.connect(lambda: event_bus.action_triggered.emit("cut"))
        menu.addAction(cut)

        paste = Action(self.tr("Paste"), self)
        paste.setEnabled(has_clipboard)
        paste.setShortcut(QKeySequence("Ctrl+V"))
        paste.triggered.connect(lambda: event_bus.action_triggered.emit("paste"))
        menu.addAction(paste)

        menu.addSeparator()

        duplicate = Action(self.tr("Duplicate Step"), self)
        duplicate.setEnabled(has_selection)
        duplicate.setShortcut(QKeySequence("Ctrl+D"))
        duplicate.triggered.connect(lambda: event_bus.action_triggered.emit("duplicate_step"))
        menu.addAction(duplicate)

        delete = Action(self.tr("Delete Step"), self)
        delete.setEnabled(has_selection)
        delete.setShortcut(QKeySequence("Del"))
        delete.triggered.connect(lambda: event_bus.action_triggered.emit("delete_step"))
        menu.addAction(delete)

        menu.addSeparator()

        wrap = Action(self.tr("Wrap in Repeat"), self)
        wrap.setEnabled(has_selection)
        wrap.triggered.connect(lambda: event_bus.action_triggered.emit("wrap_in_repeat"))
        menu.addAction(wrap)

        target = self.step_list if self.step_list.isVisible() else self
        menu.exec(target.mapToGlobal(pos))

    def set_has_clipboard(self, value: bool) -> None:
        self.has_clipboard = value
