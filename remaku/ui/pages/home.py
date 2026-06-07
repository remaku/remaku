from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSplitter, QVBoxLayout, QWidget
from qfluentwidgets import CaptionLabel
from remaku.ui.components.center_panel import CenterPanel
from remaku.ui.components.left_panel import LeftPanel
from remaku.ui.components.right_panel import RightPanel
from remaku.ui.components.toolbar import Toolbar


class HomePage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setObjectName("HomePage")

        layout = QVBoxLayout(self)

        toolbar = Toolbar(self)

        layout.addWidget(toolbar)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet("QSplitter::handle { background: transparent; }")

        left_panel = LeftPanel()
        center_panel = CenterPanel()
        right_panel = RightPanel()

        splitter.addWidget(left_panel)
        splitter.addWidget(center_panel)
        splitter.addWidget(right_panel)

        layout.addWidget(splitter, 1)

        status_label = CaptionLabel("Ready", self)
        layout.addWidget(status_label)
