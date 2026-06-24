import json
import os
import time
from datetime import datetime
from typing import cast

import cv2
import mss
import numpy as np
from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QImage, QMouseEvent, QPainter, QPaintEvent, QPen, QPixmap, QScreen
from PySide6.QtWidgets import QApplication, QWidget

from remaku.core import display
from remaku.paths import log_dir, templates_dir

CAPTURE_DEBUG_ENV = "REMAKU_CAPTURE_DEBUG"


def pixmap_from_bgr_frame(frame: np.ndarray) -> QPixmap:
    height, width = frame.shape[:2]
    image = QImage(
        frame.data,
        width,
        height,
        frame.strides[0],
        QImage.Format.Format_BGR888,
    ).copy()
    return QPixmap.fromImage(image)


def capture_debug_enabled() -> bool:
    return os.environ.get(CAPTURE_DEBUG_ENV, "").lower() in {"1", "true", "yes", "on"}


def write_png(path, frame: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imencode(".png", frame)[1].tofile(str(path))


def rect_to_dict(rect) -> dict[str, int]:
    return {
        "left": int(rect.left),
        "top": int(rect.top),
        "width": int(rect.width),
        "height": int(rect.height),
        "right": int(rect.right),
        "bottom": int(rect.bottom),
    }


def qt_rect_to_dict(rect: QRect) -> dict[str, int]:
    return {
        "x": rect.x(),
        "y": rect.y(),
        "width": rect.width(),
        "height": rect.height(),
        "right": rect.right(),
        "bottom": rect.bottom(),
    }


def screen_to_dict(screen: QScreen) -> dict[str, object]:
    return {
        "name": screen.name(),
        "geometry": qt_rect_to_dict(screen.geometry()),
        "available_geometry": qt_rect_to_dict(screen.availableGeometry()),
        "device_pixel_ratio": screen.devicePixelRatio(),
        "logical_dpi": screen.logicalDotsPerInch(),
        "physical_dpi": screen.physicalDotsPerInch(),
    }


def win32_monitors_to_list() -> list[dict[str, object]]:
    try:
        monitors = display.win32api.EnumDisplayMonitors()
    except Exception as error:
        return [{"error": str(error)}]

    result = []

    for monitor, device_context, monitor_rect in monitors:
        del device_context

        try:
            info = display.win32api.GetMonitorInfo(cast(int, monitor))
        except Exception as error:
            result.append({"monitor_rect": list(monitor_rect), "error": str(error)})
            continue

        result.append(
            {
                "device": str(info.get("Device", "")),
                "monitor": list(info.get("Monitor", ())),
                "work": list(info.get("Work", ())),
                "flags": int(info.get("Flags", 0)),
                "enum_rect": list(monitor_rect),
            }
        )

    return result


def dump_capture_debug(target: display.DisplayTarget, selected_frame: np.ndarray, merged_frame: np.ndarray) -> None:
    if not capture_debug_enabled():
        return

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    debug_dir = log_dir() / "capture-debug" / stamp
    write_png(debug_dir / "selected-screen.png", selected_frame)
    write_png(debug_dir / "merged-screen.png", merged_frame)

    metadata = {
        "target": {
            "screen": screen_to_dict(target.screen),
            "physical_rect": rect_to_dict(target.physical_rect),
        },
        "qt_screens": [screen_to_dict(screen) for screen in QApplication.screens()],
        "win32_monitors": win32_monitors_to_list(),
    }

    with (debug_dir / "metadata.json").open("w", encoding="utf-8") as file:
        json.dump(metadata, file, indent=2, ensure_ascii=False)
        file.write("\n")


def grab_screen(target: display.DisplayTarget) -> tuple[QPixmap, np.ndarray]:
    with mss.MSS() as screen_capture:
        screenshot = screen_capture.grab(
            {
                "left": target.physical_rect.left,
                "top": target.physical_rect.top,
                "width": target.physical_rect.width,
                "height": target.physical_rect.height,
            }
        )
        merged_screenshot = screen_capture.grab(screen_capture.monitors[0]) if capture_debug_enabled() else None

    frame = np.asarray(screenshot)[:, :, :3].copy()

    if merged_screenshot is not None:
        merged_frame = np.asarray(merged_screenshot)[:, :, :3].copy()
        dump_capture_debug(target, frame, merged_frame)

    return pixmap_from_bgr_frame(frame), frame


class RegionSelector(QWidget):
    region_selected = Signal(str, int, int)
    area_selected = Signal(int, int, int, int, int, int)
    cancelled = Signal()

    def __init__(
        self,
        macro_id: str = "",
        parent=None,
        target_screen: QScreen | None = None,
        target_display: display.DisplayTarget | None = None,
        save_template: bool = True,
    ) -> None:
        super().__init__(parent)

        self.macro_id = macro_id
        self.save_template = save_template
        self.setWindowFlags(
            Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setCursor(Qt.CursorShape.CrossCursor)

        self.origin = QPoint()
        self.current = QPoint()
        self.selecting = False

        selected_display = target_display

        if selected_display is None and target_screen is not None:
            selected_display = display.DisplayTarget(
                screen=target_screen,
                physical_rect=display.physical_rect_for_screen(target_screen),
            )

        if selected_display is None:
            selected_display = display.display_target_at_cursor()

        if selected_display is None:
            raise RuntimeError("No screen is available")

        self.target_display = selected_display
        self.target_screen = selected_display.screen
        self.background_pixmap, self.screenshot = grab_screen(self.target_display)
        self.frame_height, self.frame_width = self.screenshot.shape[:2]

    def start(self) -> None:
        handle = self.windowHandle()

        if handle is None:
            self.createWinId()
            handle = self.windowHandle()

        if handle is not None:
            handle.setScreen(self.target_screen)

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

        if not self.save_template:
            self.area_selected.emit(x, y, width, height, self.frame_width, self.frame_height)
            return

        template_id = str(int(time.time()))
        template_dir = templates_dir(self.macro_id)
        template_dir.mkdir(parents=True, exist_ok=True)
        path = template_dir / f"{template_id}.png"
        cv2.imencode(".png", cropped)[1].tofile(str(path))

        self.region_selected.emit(template_id, self.frame_width, self.frame_height)
