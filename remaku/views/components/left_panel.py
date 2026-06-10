from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QHBoxLayout, QListWidgetItem, QVBoxLayout
from qfluentwidgets import BodyLabel, CardWidget, ListWidget, PushButton, RoundMenu, SubtitleLabel

from remaku.core.event_bus import event_bus
from remaku.resources.icon import RemakuIcon


class LeftPanel(CardWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.init_ui()

    def init_ui(self):
        self.setMinimumWidth(200)
        self.setMaximumWidth(300)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        header = QHBoxLayout()

        title = SubtitleLabel(self.tr("Macros"), self)
        header.addWidget(title)
        header.addStretch()

        self.new_macro_button = PushButton(RemakuIcon.PLUS, self.tr("Add"), self)
        self.new_macro_button.clicked.connect(lambda: event_bus.new_macro_requested.emit())
        header.addWidget(self.new_macro_button)

        layout.addLayout(header)

        self.macro_list = ListWidget(self)
        self.macro_list.setDragDropMode(ListWidget.DragDropMode.InternalMove)
        self.macro_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.macro_list.model().rowsMoved.connect(self.handle_order_changed)
        self.macro_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.macro_list.customContextMenuRequested.connect(self.handle_context_menu)
        self.macro_list.itemSelectionChanged.connect(self.handle_selection_changed)
        layout.addWidget(self.macro_list, 1)

        self.empty_label = BodyLabel(self.tr("No macros yet"), self)
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setWordWrap(True)
        layout.addWidget(self.empty_label, 1)

    def set_macro_list(self, items: list[tuple[str, str]], selected_name: str = "") -> None:
        self.macro_list.clear()

        selected_item: QListWidgetItem | None = None

        for name, label in items:
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, name)
            self.macro_list.addItem(item)

            if name == selected_name:
                selected_item = item

        if selected_item is not None:
            self.macro_list.setCurrentItem(selected_item)
        elif self.macro_list.count() > 0:
            self.macro_list.setCurrentRow(0)

        self.update_empty_state()

    def update_empty_state(self) -> None:
        has_macros = self.macro_list.count() > 0
        self.macro_list.setVisible(has_macros)
        self.empty_label.setVisible(not has_macros)

    def handle_selection_changed(self) -> None:
        item = self.macro_list.currentItem()

        if item is None:
            return

        name = item.data(Qt.ItemDataRole.UserRole)

        if isinstance(name, str):
            event_bus.macro_selected.emit(name)

    def handle_context_menu(self, pos) -> None:
        item = self.macro_list.itemAt(pos)

        if item is None:
            return

        self.macro_list.setCurrentItem(item)

        menu = RoundMenu(parent=self.macro_list)

        rename_action = QAction(self.tr("Rename"), self.macro_list)
        rename_action.triggered.connect(self.handle_macro_rename)
        menu.addAction(rename_action)

        duplicate_action = QAction(self.tr("Duplicate"), self.macro_list)
        duplicate_action.triggered.connect(self.handle_macro_duplicate)
        menu.addAction(duplicate_action)

        delete_action = QAction(self.tr("Delete"), self.macro_list)
        delete_action.triggered.connect(self.handle_macro_delete)
        menu.addAction(delete_action)

        menu.exec(self.macro_list.mapToGlobal(pos))

    def handle_macro_rename(self) -> None:
        item = self.macro_list.currentItem()

        if item is None:
            return

        name = item.data(Qt.ItemDataRole.UserRole)

        if isinstance(name, str):
            event_bus.macro_rename_requested.emit(name)

    def handle_macro_duplicate(self) -> None:
        item = self.macro_list.currentItem()

        if item is None:
            return

        name = item.data(Qt.ItemDataRole.UserRole)

        if isinstance(name, str):
            event_bus.macro_duplicate_requested.emit(name)

    def handle_macro_delete(self) -> None:
        item = self.macro_list.currentItem()

        if item is None:
            return

        name = item.data(Qt.ItemDataRole.UserRole)

        if isinstance(name, str):
            event_bus.macro_delete_requested.emit(name)

    def handle_order_changed(self) -> None:
        event_bus.macro_order_changed.emit()
        current = self.macro_list.currentItem()
        self.macro_list.blockSignals(True)
        self.macro_list.clearSelection()
        if current is not None:
            self.macro_list.setCurrentItem(current)
        self.macro_list.blockSignals(False)
