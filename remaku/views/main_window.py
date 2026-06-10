import ctypes
import ctypes.wintypes

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from qfluentwidgets import FluentWindow, TransparentToolButton, qrouter

from remaku.core.event_bus import event_bus
from remaku.resources.icon import RemakuIcon
from remaku.views.home_view import HomeView
from remaku.views.settings_view import SettingsView


class MainWindow(FluentWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Remaku")
        self.setWindowIcon(QIcon(":/remaku/images/logo.png"))
        self.setMinimumSize(900, 600)
        self.resize(900, 600)
        self.customize_navigation_interface()

        self.home_view = HomeView(self)
        self.settings_view = SettingsView(self)

        self.addSubInterface(self.home_view, "", "", isTransparent=True)
        self.addSubInterface(self.settings_view, "", "", isTransparent=True)

    def customize_navigation_interface(self):
        self.navigationInterface.setVisible(False)
        self.titleBar.hBoxLayout.setContentsMargins(11, 0, 0, 0)
        self.widgetLayout.setContentsMargins(0, 48, 0, 0)

        return_button = TransparentToolButton(RemakuIcon.ARROW_LEFT, self)
        return_button.setToolTip(self.tr("Back"))
        return_button.setFixedSize(24, 24)
        return_button.clicked.connect(qrouter.pop)
        return_button.setVisible(False)
        self.titleBar.hBoxLayout.insertWidget(0, return_button)
        self.titleBar.hBoxLayout.insertSpacing(1, 8)
        self.stackedWidget.currentChanged.connect(lambda index: return_button.setVisible(index != 0))
        self.stackedWidget.setAnimationEnabled(False)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.titleBar.move(0, 0)
        self.titleBar.resize(self.width(), self.titleBar.height())

    def nativeEvent(self, eventType: bytes | bytearray, message: int) -> object:
        WM_HOTKEY = 0x0312

        if eventType == b"windows_generic_MSG":
            msg = ctypes.wintypes.MSG.from_address(int(message))
            if msg.message == WM_HOTKEY:
                event_bus.hotkey_triggered.emit(msg.wParam)

        return super().nativeEvent(eventType, message)

    def set_always_on_top(self, always_on_top: bool):
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, always_on_top)
        self.show()
