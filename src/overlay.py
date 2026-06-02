"""Overlay status widget.

A frameless, always-on-top, semi-transparent floating window that displays macro execution status.
"""

import ctypes
from pathlib import Path

from PySide6.QtCore import QByteArray, QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QMouseEvent, QPainter, QPaintEvent, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QPushButton, QWidget

GWL_EXSTYLE = -20
WS_EX_NOACTIVATE = 0x08000000
ICONS_DIR = Path(__file__).parent / "icons"


def white_icon(name: str, size: int = 16) -> QIcon:
    """Load a Lucide SVG icon forced to white color."""
    svg = (ICONS_DIR / f"{name}.svg").read_bytes().replace(b"currentColor", b"#ffffff")
    pixmap = QPixmap(QSize(size, size))
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    QSvgRenderer(QByteArray(svg)).render(painter, QRect(0, 0, size, size).toRectF())
    painter.end()

    return QIcon(pixmap)


class OverlayWidget(QWidget):
    """Floating overlay that shows macro run status above fullscreen apps."""

    toggle_run = Signal()

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

        self.icon_play = white_icon("play")
        self.icon_pause = white_icon("pause")

        self.btn = QPushButton()
        self.btn.setFixedSize(24, 24)
        self.btn.setIconSize(QSize(16, 16))
        self.btn.setIcon(self.icon_pause)
        self.btn.setStyleSheet(
            "QPushButton { background: rgba(255,255,255,40); border: none; border-radius: 4px; }"
            "QPushButton:hover { background: rgba(255,255,255,80); }"
        )
        self.btn.clicked.connect(self.toggle_run.emit)
        layout.addWidget(self.btn)

        self.label = QLabel()
        self.label.setStyleSheet("color: white; font-size: 13px;")
        layout.addWidget(self.label, 1)

        self.drag_pos: QPoint | None = None

    def set_text(self, text: str) -> None:
        """Update overlay display text and resize to fit."""
        self.label.setText(text)
        self.adjustSize()

    def set_running(self, running: bool) -> None:
        """Update button icon based on running state."""
        self.btn.setIcon(self.icon_pause if running else self.icon_play)

    def show(self) -> None:
        """Show overlay and apply WS_EX_NOACTIVATE so clicking it won't steal focus from games."""
        super().show()

        screen = QApplication.primaryScreen().availableGeometry()
        pos = self.pos()
        x = max(0, min(pos.x(), screen.width() - self.width()))
        y = max(0, min(pos.y(), screen.height() - self.height()))
        self.move(x, y)

        hwnd = int(self.winId())
        style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_NOACTIVATE)

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
