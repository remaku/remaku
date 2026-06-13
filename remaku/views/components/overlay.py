import win32con
import win32gui
from PySide6.QtCore import QPoint, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QMouseEvent, QPainter, QPaintEvent
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QPushButton, QWidget

from remaku.core.event_bus import event_bus


def white_icon(name: str) -> QIcon:
    return QIcon(f":/remaku/icons/{name}-white.svg")


class OverlayWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedHeight(36)
        self.setMinimumWidth(200)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 12, 6)
        layout.setSpacing(6)

        self.button = QPushButton(self)
        self.button.setFixedSize(24, 24)
        self.button.setIconSize(QSize(16, 16))
        self.button.setIcon(white_icon("pause"))
        self.button.setStyleSheet(
            "QPushButton { background: rgba(255, 255, 255, 40); border: none; border-radius: 4px; }"
            "QPushButton:hover { background: rgba(255, 255, 255, 80); }"
        )
        self.button.clicked.connect(event_bus.overlay_toggled.emit)
        layout.addWidget(self.button)

        self.label = QLabel(self)
        self.label.setStyleSheet("color: white; font-size: 13px;")
        layout.addWidget(self.label, 1)

        self.drag_pos: QPoint | None = None

    def set_text(self, text: str) -> None:
        self.label.setText(text)
        self.adjustSize()

    def show(self) -> None:
        super().show()
        screen = QApplication.primaryScreen().availableGeometry()
        pos = self.pos()
        x = max(0, min(pos.x(), screen.width() - self.width()))
        y = max(0, min(pos.y(), screen.height() - self.height()))
        self.move(x, y)

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
