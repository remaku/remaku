"""Tests for the region selector overlay.

Requires pytest-qt and a display server.
"""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from PySide6.QtCore import QPoint, QRect, Qt

from region_selector import RegionSelector


@pytest.fixture
def selector(qtbot):
    with patch("region_selector.QApplication.primaryScreen") as mock_screen:
        mock_image = MagicMock()
        mock_image.width.return_value = 1920
        mock_image.height.return_value = 1080
        mock_image.bits.return_value = bytes(1920 * 1080 * 3)

        mock_pixmap = MagicMock()
        mock_pixmap.toImage.return_value.convertToFormat.return_value = mock_image
        mock_screen.return_value.grabWindow.return_value = mock_pixmap
        sel = RegionSelector("test_macro")
        qtbot.addWidget(sel)
        yield sel


class TestCreation:
    def test_macro_name(self, selector):
        assert selector.macro_name == "test_macro"

    def test_window_flags(self, selector):
        flags = selector.windowFlags()
        assert flags & Qt.WindowType.FramelessWindowHint
        assert flags & Qt.WindowType.WindowStaysOnTopHint

    def test_cursor(self, selector):
        assert selector.cursor().shape() == Qt.CursorShape.CrossCursor

    def test_initial_state(self, selector):
        assert selector.selecting is False
        assert selector.origin == QPoint()
        assert selector.current == QPoint()

    def test_screenshot_array(self, selector):
        assert selector.screenshot is not None
        assert selector.frame_width == 1920
        assert selector.frame_height == 1080

    def test_bg_pixmap(self, selector):
        assert selector.bg_pixmap is not None


class TestStart:
    def test_calls_show_full_screen(self, selector):
        with patch.object(selector, "showFullScreen") as mock_show:
            selector.start()
            mock_show.assert_called_once()


class TestPaintEvent:
    def test_paint_when_not_selecting(self, selector):
        with patch("region_selector.QPainter") as mock_painter:
            event = MagicMock()
            selector.paintEvent(event)
            mock_painter.assert_called_once_with(selector)

    def test_paint_when_selecting(self, selector):
        selector.selecting = True
        selector.origin = QPoint(100, 100)
        selector.current = QPoint(300, 300)
        with patch("region_selector.QPainter") as mock_painter:
            event = MagicMock()
            selector.paintEvent(event)
            mock_painter.assert_called_once_with(selector)


class TestToFrameRect:
    def test_identity(self, selector):
        selector.resize(1920, 1080)
        rect = QRect(100, 100, 200, 200)
        result = selector.to_frame_rect(rect)
        assert result == rect

    def test_scale_down(self, selector):
        selector.resize(960, 540)
        rect = QRect(100, 100, 200, 200)
        result = selector.to_frame_rect(rect)
        assert result.x() == 200
        assert result.y() == 200
        assert result.width() == 400
        assert result.height() == 400

    def test_zero_size_widget(self, selector):
        selector.resize(0, 0)
        rect = QRect(0, 0, 0, 0)
        result = selector.to_frame_rect(rect)
        assert result == rect


class TestMousePressEvent:
    def test_left_button_starts_selection(self, selector):
        event = MagicMock()
        event.button.return_value = Qt.MouseButton.LeftButton
        event.pos.return_value = QPoint(100, 100)
        selector.mousePressEvent(event)
        assert selector.selecting is True
        assert selector.origin == QPoint(100, 100)
        assert selector.current == QPoint(100, 100)

    def test_right_button_ignored(self, selector):
        event = MagicMock()
        event.button.return_value = Qt.MouseButton.RightButton
        event.pos.return_value = QPoint(100, 100)
        selector.mousePressEvent(event)
        assert selector.selecting is False


class TestMouseMoveEvent:
    def test_updates_current_when_selecting(self, selector):
        selector.selecting = True
        selector.origin = QPoint(100, 100)
        selector.current = QPoint(100, 100)
        event = MagicMock()
        event.pos.return_value = QPoint(200, 200)
        with patch.object(selector, "update") as mock_update:
            selector.mouseMoveEvent(event)
            assert selector.current == QPoint(200, 200)
            mock_update.assert_called_once()

    def test_ignored_when_not_selecting(self, selector):
        selector.selecting = False
        event = MagicMock()
        event.pos.return_value = QPoint(200, 200)
        with patch.object(selector, "update") as mock_update:
            selector.mouseMoveEvent(event)
            mock_update.assert_not_called()


class TestMouseReleaseEvent:
    def test_large_selection_saves(self, selector):
        selector.selecting = True
        selector.origin = QPoint(100, 100)
        selector.current = QPoint(300, 300)
        selector.screenshot = np.zeros((1080, 1920, 3), dtype=np.uint8)
        event = MagicMock()
        event.button.return_value = Qt.MouseButton.LeftButton
        with patch.object(selector, "save_region") as mock_save, patch.object(selector, "close") as mock_close:
            selector.mouseReleaseEvent(event)
            mock_save.assert_called_once()
            mock_close.assert_called_once()

    def test_small_selection_cancels(self, selector):
        selector.selecting = True
        selector.origin = QPoint(100, 100)
        selector.current = QPoint(102, 102)
        event = MagicMock()
        event.button.return_value = Qt.MouseButton.LeftButton
        with patch.object(selector, "cancelled") as mock_cancel, patch.object(selector, "close") as mock_close:
            selector.mouseReleaseEvent(event)
            mock_cancel.emit.assert_called_once()
            mock_close.assert_called_once()

    def test_right_button_ignored(self, selector):
        selector.selecting = True
        event = MagicMock()
        event.button.return_value = Qt.MouseButton.RightButton
        with patch.object(selector, "close") as mock_close:
            selector.mouseReleaseEvent(event)
            mock_close.assert_not_called()


class TestKeyPressEvent:
    def test_escape_cancels(self, selector):
        selector.selecting = True
        event = MagicMock()
        event.key.return_value = Qt.Key.Key_Escape
        with patch.object(selector, "cancelled") as mock_cancel, patch.object(selector, "close") as mock_close:
            selector.keyPressEvent(event)
            assert selector.selecting is False
            mock_cancel.emit.assert_called_once()
            mock_close.assert_called_once()

    def test_other_key_ignored(self, selector):
        event = MagicMock()
        event.key.return_value = Qt.Key.Key_A
        with patch.object(selector, "close") as mock_close:
            selector.keyPressEvent(event)
            mock_close.assert_not_called()


class TestSaveRegion:
    def test_emits_region_selected(self, selector, tmp_path):
        selector.screenshot = np.zeros((1080, 1920, 3), dtype=np.uint8)
        rect = QRect(100, 100, 200, 200)
        with (
            patch.object(selector, "region_selected") as mock_signal,
            patch("region_selector.cv2.imencode", return_value=(True, np.array([1, 2, 3]))),
            patch("region_selector.config.templates_dir", return_value=tmp_path),
            patch("region_selector.time.time", return_value=1234567890),
        ):
            selector.save_region(rect)
            mock_signal.emit.assert_called_once()
            assert (tmp_path / "1234567890.png").exists()

    def test_creates_template_dir(self, selector, tmp_path):
        selector.screenshot = np.zeros((1080, 1920, 3), dtype=np.uint8)
        rect = QRect(100, 100, 200, 200)
        with (
            patch("region_selector.cv2.imencode", return_value=(True, np.array([1, 2, 3]))),
            patch("region_selector.config.templates_dir", return_value=tmp_path) as mock_dir,
            patch("region_selector.time.time", return_value=1234567890),
        ):
            selector.save_region(rect)
            mock_dir.assert_called_once_with("test_macro")

    def test_converts_to_gray(self, selector, tmp_path):
        selector.screenshot = np.zeros((1080, 1920, 3), dtype=np.uint8)
        rect = QRect(100, 100, 200, 200)
        with (
            patch("region_selector.cv2.imencode", return_value=(True, np.array([1, 2, 3]))) as mock_encode,
            patch("region_selector.config.templates_dir", return_value=tmp_path),
            patch("region_selector.time.time", return_value=1234567890),
        ):
            selector.save_region(rect)
            mock_encode.assert_called_once()
            args = mock_encode.call_args[0]
            assert args[0] == ".png"

    def test_uses_to_frame_rect(self, selector, tmp_path):
        selector.screenshot = np.zeros((1080, 1920, 3), dtype=np.uint8)
        selector.resize(960, 540)
        rect = QRect(100, 100, 200, 200)
        with (
            patch("region_selector.cv2.imencode", return_value=(True, np.array([1, 2, 3]))),
            patch("region_selector.config.templates_dir", return_value=tmp_path),
            patch("region_selector.time.time", return_value=1234567890),
        ):
            selector.save_region(rect)
            assert (tmp_path / "1234567890.png").exists()
