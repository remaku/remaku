"""Region selector.

Provides a semi-transparent window for the user to select a screen region.
"""

import time

import cv2
import numpy as np
from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QImage, QMouseEvent, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QApplication, QWidget

import config


class RegionSelector(QWidget):
    """Full-screen semi-transparent overlay; user drags to select a rectangular region.

    Emits region_selected(str) with the template name (without extension) on completion.
    Emits cancelled() on cancel.
    """

    region_selected = Signal(str)
    cancelled = Signal()

    def __init__(self, macro_name: str = "", parent=None) -> None:
        super().__init__(parent)
        self.macro_name = macro_name
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setCursor(Qt.CursorShape.CrossCursor)

        self.origin = QPoint()
        self.current = QPoint()
        self.selecting = False

        screen = QApplication.primaryScreen()
        self.bg_pixmap = screen.grabWindow(0)

        # Convert to numpy for cropping when saving
        img = self.bg_pixmap.toImage().convertToFormat(QImage.Format.Format_BGR888)
        ptr = img.bits()
        self.frame_width = img.width()
        self.frame_height = img.height()
        self.screenshot = np.frombuffer(ptr, dtype=np.uint8).reshape(self.frame_height, self.frame_width, 3).copy()

    def start(self) -> None:
        """Show the full-screen selection overlay."""
        self.showFullScreen()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        widget_rect = self.rect()
        painter.drawPixmap(widget_rect, self.bg_pixmap)
        painter.fillRect(widget_rect, QColor(0, 0, 0, 80))

        if self.selecting:
            rect = QRect(self.origin, self.current).normalized()
            painter.drawPixmap(rect, self.bg_pixmap, self.to_frame_rect(rect))
            pen = QPen(QColor(37, 99, 235), 2)
            painter.setPen(pen)
            painter.drawRect(rect)

        painter.end()

    def to_frame_rect(self, rect: QRect) -> QRect:
        """Convert widget logical coordinates to frame pixel coordinates."""
        scale_x = self.frame_width / max(1, self.width())
        scale_y = self.frame_height / max(1, self.height())
        return QRect(
            int(rect.x() * scale_x),
            int(rect.y() * scale_y),
            int(rect.width() * scale_x),
            int(rect.height() * scale_y),
        )

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.origin = event.pos()
            self.current = event.pos()
            self.selecting = True

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self.selecting:
            self.current = event.pos()
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.selecting:
            self.selecting = False
            rect = QRect(self.origin, self.current).normalized()

            if rect.width() > 5 and rect.height() > 5:
                self.save_region(rect)
            else:
                self.cancelled.emit()

            self.close()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.selecting = False
            self.cancelled.emit()
            self.close()

    def save_region(self, rect: QRect) -> None:
        phys = self.to_frame_rect(rect)
        x, y, w, h = phys.x(), phys.y(), phys.width(), phys.height()
        cropped = self.screenshot[y : y + h, x : x + w]
        gray = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY)

        name = f"{int(time.time())}"
        template_dir = config.templates_dir(self.macro_name)
        path = template_dir / f"{name}.png"
        cv2.imencode(".png", gray)[1].tofile(str(path))

        self.region_selected.emit(name)
