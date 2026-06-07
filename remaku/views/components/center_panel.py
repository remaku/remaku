from PySide6.QtWidgets import QVBoxLayout
from qfluentwidgets import CardWidget, TreeWidget


class CenterPanel(CardWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(0)

        step_list = TreeWidget(self)
        layout.addWidget(step_list)
