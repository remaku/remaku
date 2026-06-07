from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from qfluentwidgets import FluentWindow

from remaku.config.models import AppConfig
from remaku.ui.pages.home import HomePage


class MainWindow(FluentWindow):
    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Remaku")
        self.setWindowIcon(QIcon(":/remaku/images/logo.png"))
        self.setMinimumSize(900, 600)
        self.resize(900, 600)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, self.config.general.always_on_top)
        self.resetNavigationInterface()

        self.home_page = HomePage(self)

        self.addSubInterface(self.home_page, "", "", isTransparent=True)

    def resetNavigationInterface(self):
        self.navigationInterface.setVisible(False)
        self.titleBar.hBoxLayout.setContentsMargins(11, 0, 0, 0)
        self.widgetLayout.setContentsMargins(0, 48, 0, 0)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.titleBar.move(0, 0)
        self.titleBar.resize(self.width(), self.titleBar.height())
