from PySide6.QtWidgets import QVBoxLayout
from qfluentwidgets import CardWidget, ScrollArea


class RightPanel(ScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setMinimumWidth(220)
        self.setMaximumWidth(350)
        self.setWidgetResizable(True)
        self.setFrameShape(ScrollArea.Shape.NoFrame)
        self.setStyleSheet("background: transparent;")

        content = CardWidget()

        layout = QVBoxLayout(content)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        self.setWidget(content)
