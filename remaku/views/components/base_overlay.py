import win32con
import win32gui
from PySide6.QtCore import QPoint, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QMouseEvent, QPainter, QPaintEvent
from PySide6.QtWidgets import QApplication, QHBoxLayout, QPushButton, QWidget

from remaku.core.event_bus import event_bus


def white_icon(name: str) -> QIcon:
    return QIcon(f":/remaku/icons/{name}-white.svg")


class BaseOverlayWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self.drag_pos: QPoint | None = None

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedHeight(36)
        self.setMinimumWidth(200)

        self.content_layout = QHBoxLayout(self)
        self.content_layout.setContentsMargins(8, 6, 12, 6)
        self.content_layout.setSpacing(6)

    def make_icon_button(self, icon_name: str, tooltip: str) -> QPushButton:
        button = QPushButton(self)
        button.setFixedSize(24, 24)
        button.setIconSize(QSize(16, 16))
        button.setIcon(white_icon(icon_name))
        button.setToolTip(tooltip)
        button.setStyleSheet(
            "QPushButton { background: rgba(255, 255, 255, 40); border: none; border-radius: 4px; }"
            "QPushButton:hover { background: rgba(255, 255, 255, 80); }"
        )
        return button

    def show(self) -> None:
        super().show()
        self.clamp_to_screen()
        self.apply_no_activate_style()

    def clamp_to_screen(self) -> None:
        target_screen = (
            QApplication.screenAt(self.frameGeometry().center())
            or QApplication.screenAt(self.pos())
            or QApplication.primaryScreen()
        )

        if target_screen is None:
            return

        screen = target_screen.availableGeometry()
        pos = self.pos()
        x = max(screen.left(), min(pos.x(), screen.left() + screen.width() - self.width()))
        y = max(screen.top(), min(pos.y(), screen.top() + screen.height() - self.height()))
        self.move(x, y)

    def apply_no_activate_style(self) -> None:
        hwnd = int(self.winId())
        style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, style | win32con.WS_EX_NOACTIVATE)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor(0, 0, 0, 180))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(self.rect(), 8, 8)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self.drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_pos)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self.drag_pos = None
        event_bus.overlay_position_changed.emit(self.x(), self.y())
