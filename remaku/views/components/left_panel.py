from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout
from qfluentwidgets import CardWidget, ListWidget, PushButton, SubtitleLabel

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

        new_macro_button = PushButton(RemakuIcon.PLUS, self.tr("Add"), self)
        header.addWidget(new_macro_button)

        layout.addLayout(header)

        macro_list = ListWidget(self)
        layout.addWidget(macro_list)
