from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from qfluentwidgets import FluentWindow

from remaku.views.home_view import HomeView


class MainWindow(FluentWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Remaku")
        self.setWindowIcon(QIcon(":/remaku/images/logo.png"))
        self.setMinimumSize(900, 600)
        self.resize(900, 600)
        self.reset_navigation_interface()

        self.home_view = HomeView(self)

        self.addSubInterface(self.home_view, "", "", isTransparent=True)

    def reset_navigation_interface(self):
        self.navigationInterface.setVisible(False)
        self.titleBar.hBoxLayout.setContentsMargins(11, 0, 0, 0)
        self.widgetLayout.setContentsMargins(0, 48, 0, 0)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.titleBar.move(0, 0)
        self.titleBar.resize(self.width(), self.titleBar.height())

    def set_always_on_top(self, always_on_top: bool):
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, always_on_top)
