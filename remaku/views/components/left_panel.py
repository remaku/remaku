from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QListWidgetItem, QVBoxLayout
from qfluentwidgets import CardWidget, ListWidget, PushButton, SubtitleLabel

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
        header.addWidget(self.new_macro_button)

        layout.addLayout(header)

        self.macro_list = ListWidget(self)
        self.macro_list.itemSelectionChanged.connect(self.handle_selection_changed)
        layout.addWidget(self.macro_list)

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

    def handle_selection_changed(self) -> None:
        item = self.macro_list.currentItem()

        if item is None:
            return

        name = item.data(Qt.ItemDataRole.UserRole)

        if isinstance(name, str):
            event_bus.macro_selected.emit(name)
