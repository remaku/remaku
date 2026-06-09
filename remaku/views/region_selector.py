import time

import cv2
import numpy as np
from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QImage, QMouseEvent, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QApplication, QWidget

from remaku.paths import templates_dir


class RegionSelector(QWidget):
    region_selected = Signal(str, int, int)
    cancelled = Signal()

    def __init__(self, macro_name: str = "", parent=None) -> None:
        super().__init__(parent)

        self.macro_name = macro_name
        self.setWindowFlags(
            Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setCursor(Qt.CursorShape.CrossCursor)

        self.origin = QPoint()
        self.current = QPoint()
        self.selecting = False

        screen = QApplication.primaryScreen()
        if screen is None:
            raise RuntimeError("No primary screen is available")

        self.background_pixmap = screen.grabWindow(0)
        image = self.background_pixmap.toImage().convertToFormat(QImage.Format.Format_BGR888)
        pointer = image.bits()
        self.frame_width = image.width()
        self.frame_height = image.height()
        self.screenshot = np.frombuffer(pointer, dtype=np.uint8).reshape(self.frame_height, self.frame_width, 3).copy()

    def start(self) -> None:
        self.showFullScreen()

    def paintEvent(self, event: QPaintEvent) -> None:
        del event
        painter = QPainter(self)
        widget_rect = self.rect()
        painter.drawPixmap(widget_rect, self.background_pixmap)
        painter.fillRect(widget_rect, QColor(0, 0, 0, 80))

        if self.selecting:
            rect = QRect(self.origin, self.current).normalized()
            painter.drawPixmap(rect, self.background_pixmap, self.to_frame_rect(rect))
            painter.setPen(QPen(QColor(37, 99, 235), 2))
            painter.drawRect(rect)

    def to_frame_rect(self, rect: QRect) -> QRect:
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
            self.origin = event.position().toPoint()
            self.current = event.position().toPoint()
            self.selecting = True
            self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self.selecting:
            self.current = event.position().toPoint()
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
        physical = self.to_frame_rect(rect)
        x, y, width, height = physical.x(), physical.y(), physical.width(), physical.height()
        cropped = self.screenshot[y : y + height, x : x + width]
        gray = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY)

        template_id = str(int(time.time()))
        template_dir = templates_dir(self.macro_name)
        template_dir.mkdir(parents=True, exist_ok=True)
        path = template_dir / f"{template_id}.png"
        cv2.imencode(".png", gray)[1].tofile(str(path))

        self.region_selected.emit(template_id, self.frame_width, self.frame_height)
