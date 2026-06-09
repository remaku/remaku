from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTreeWidgetItem, QVBoxLayout
from qfluentwidgets import BodyLabel, CardWidget, TreeWidget

from remaku.core.event_bus import event_bus


class CenterPanel(CardWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.item_to_step: dict[QTreeWidgetItem, object] = {}
        self.item_to_branch: dict[QTreeWidgetItem, tuple[object, str]] = {}
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
        self.content_layout.addWidget(self.step_list, 1)

    def add_empty_label(self) -> None:
        self.empty_label = BodyLabel(self.tr("No steps yet"), self)
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setWordWrap(True)
        self.content_layout.addWidget(self.empty_label)
