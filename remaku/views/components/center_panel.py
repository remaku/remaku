from typing import Any

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QTreeWidgetItem, QVBoxLayout
from qfluentwidgets import Action, BodyLabel, CardWidget, RoundMenu, TreeWidget

from remaku.core.event_bus import event_bus


class CenterPanel(CardWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.item_to_step: dict[QTreeWidgetItem, object] = {}
        self.item_to_branch: dict[QTreeWidgetItem, tuple[object, str]] = {}
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
        self.step_list.blockSignals(True)
        self.step_list.clear()
        self.item_to_step = {}
        self.item_to_branch = {}
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

    def build_tree_item(self, item_data: dict[str, Any]) -> QTreeWidgetItem:
        item = QTreeWidgetItem([item_data["label"]])

        if "branch" in item_data:
            parent_step, branch_key = item_data["branch"]
            self.item_to_branch[item] = (parent_step, branch_key)
        else:
            step = item_data["step"]
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
        self.content_layout.addWidget(self.step_list, 1)

    def add_empty_label(self) -> None:
        self.empty_label = BodyLabel(self.tr("No steps yet"), self)
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setWordWrap(True)
        self.content_layout.addWidget(self.empty_label)

    def handle_context_menu(self, pos: QPoint) -> None:
        menu = RoundMenu(parent=self)

        has_selection = bool(self.step_list.selectedItems())
        has_clipboard = self.has_clipboard

        copy = Action(self.tr("Copy"), self)
        copy.setEnabled(has_selection)
        copy.setShortcut(QKeySequence("Ctrl+C"))
        menu.addAction(copy)

        cut = Action(self.tr("Cut"), self)
        cut.setEnabled(has_selection)
        cut.setShortcut(QKeySequence("Ctrl+X"))
        menu.addAction(cut)

        paste = Action(self.tr("Paste"), self)
        paste.setEnabled(has_clipboard)
        paste.setShortcut(QKeySequence("Ctrl+V"))
        menu.addAction(paste)

        menu.addSeparator()

        duplicate = Action(self.tr("Duplicate Step"), self)
        duplicate.setEnabled(has_selection)
        duplicate.setShortcut(QKeySequence("Ctrl+D"))
        menu.addAction(duplicate)

        delete = Action(self.tr("Delete Step"), self)
        delete.setEnabled(has_selection)
        delete.setShortcut(QKeySequence("Del"))
        menu.addAction(delete)

        menu.addSeparator()

        wrap = Action(self.tr("Wrap in Repeat"), self)
        wrap.setEnabled(has_selection)
        menu.addAction(wrap)

        target = self.step_list if self.step_list.isVisible() else self
        menu.exec(target.mapToGlobal(pos))

    def set_has_clipboard(self, value: bool) -> None:
        self.has_clipboard = value
