from PySide6.QtWidgets import QVBoxLayout
from qfluentwidgets import CardWidget, TreeWidget


class CenterPanel(CardWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(0)

        step_list = TreeWidget()
        layout.addWidget(step_list)
