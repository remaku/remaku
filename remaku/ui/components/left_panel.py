from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout
from qfluentwidgets import CardWidget, ListWidget, PushButton, SubtitleLabel


class LeftPanel(CardWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setMinimumWidth(200)
        self.setMaximumWidth(300)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        header = QHBoxLayout()

        title = SubtitleLabel("Macro")
        header.addWidget(title)
        header.addStretch()

        new_macro_button = PushButton("Add")
        header.addWidget(new_macro_button)

        layout.addLayout(header)

        macro_list = ListWidget()
        layout.addWidget(macro_list)

        layout.addWidget(macro_list)
