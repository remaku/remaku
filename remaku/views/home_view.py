from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSplitter, QVBoxLayout, QWidget
from qfluentwidgets import CaptionLabel

from remaku.views.components.center_panel import CenterPanel
from remaku.views.components.left_panel import LeftPanel
from remaku.views.components.right_panel import RightPanel
from remaku.views.components.toolbar import Toolbar


class HomeView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.init_ui()

    def init_ui(self):
        self.setObjectName("home")

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(11, 0, 11, 11)

        self.toolbar = Toolbar(self)

        layout.addWidget(self.toolbar)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet("QSplitter::handle { background: transparent; }")

        self.left_panel = LeftPanel()
        self.center_panel = CenterPanel()
        self.right_panel = RightPanel()

        splitter.addWidget(self.left_panel)
        splitter.addWidget(self.center_panel)
        splitter.addWidget(self.right_panel)

        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)
        splitter.setCollapsible(2, False)
        splitter.setSizes([220, 550, 250])

        layout.addWidget(splitter, 1)

        self.status_label = CaptionLabel(self.tr("Ready"), self)
        layout.addWidget(self.status_label)

    def set_status_text(self, text: str) -> None:
        self.status_label.setText(text)
