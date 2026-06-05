"""Tests for the overlay widget.

Requires pytest-qt and a display server.
"""

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QWidget

from overlay import WS_EX_NOACTIVATE, OverlayWidget, white_icon


@pytest.fixture
def overlay_widget(qtbot):
    with patch("overlay.white_icon") as mock_white_icon:
        mock_icon = QIcon()
        mock_white_icon.return_value = mock_icon
        widget = OverlayWidget()
        qtbot.addWidget(widget)
        yield widget


class TestWhiteIcon:
    def test_returns_qicon(self, qtbot, tmp_path):
        svg = b'<svg xmlns="http://www.w3.org/2000/svg"><rect fill="currentColor"/></svg>'
        icon_dir = tmp_path / "icons"
        icon_dir.mkdir()
        (icon_dir / "test.svg").write_bytes(svg)
        with (
            patch("overlay.ICONS_DIR", icon_dir),
            patch("overlay.QSvgRenderer"),
            patch("overlay.QPainter"),
            patch("overlay.QPixmap", side_effect=lambda size: QPixmap(size)),
        ):
            icon = white_icon("test", size=16)
        assert icon is not None

    def test_replaces_current_color(self, qtbot, tmp_path):
        svg = b'<svg xmlns="http://www.w3.org/2000/svg"><rect fill="currentColor"/></svg>'
        icon_dir = tmp_path / "icons"
        icon_dir.mkdir()
        (icon_dir / "test.svg").write_bytes(svg)
        with (
            patch("overlay.ICONS_DIR", icon_dir),
            patch("overlay.QSvgRenderer") as mock_renderer,
            patch("overlay.QPainter"),
            patch("overlay.QPixmap", side_effect=lambda size: QPixmap(size)),
        ):
            white_icon("test", size=16)
            mock_renderer.assert_called_once()
            call_args = mock_renderer.call_args[0][0]
            assert b"#ffffff" in bytes(call_args)
            assert b"currentColor" not in bytes(call_args)


class TestOverlayWidgetCreation:
    def test_window_flags(self, overlay_widget):
        flags = overlay_widget.windowFlags()
        assert flags & Qt.WindowType.FramelessWindowHint
        assert flags & Qt.WindowType.WindowStaysOnTopHint
        assert flags & Qt.WindowType.Tool

    def test_translucent_background(self, overlay_widget):
        assert overlay_widget.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def test_show_without_activating(self, overlay_widget):
        assert overlay_widget.testAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

    def test_fixed_height(self, overlay_widget):
        assert overlay_widget.height() == 36

    def test_minimum_width(self, overlay_widget):
        assert overlay_widget.minimumWidth() == 200

    def test_has_button(self, overlay_widget):
        assert overlay_widget.btn is not None

    def test_has_label(self, overlay_widget):
        assert overlay_widget.label is not None

    def test_initial_drag_pos(self, overlay_widget):
        assert overlay_widget.drag_pos is None


class TestSetText:
    def test_updates_label(self, overlay_widget):
        overlay_widget.set_text("Running: test")
        assert overlay_widget.label.text() == "Running: test"

    def test_adjusts_size(self, overlay_widget):
        with patch.object(overlay_widget, "adjustSize") as mock_adjust:
            overlay_widget.set_text("Running: test")
            mock_adjust.assert_called_once()


class TestSetRunning:
    def test_sets_pause_icon_when_running(self, overlay_widget):
        with patch.object(overlay_widget.btn, "setIcon") as mock_set_icon:
            overlay_widget.set_running(True)
            mock_set_icon.assert_called_once_with(overlay_widget.icon_pause)

    def test_sets_play_icon_when_not_running(self, overlay_widget):
        with patch.object(overlay_widget.btn, "setIcon") as mock_set_icon:
            overlay_widget.set_running(False)
            mock_set_icon.assert_called_once_with(overlay_widget.icon_play)


class TestShow:
    def test_calls_super_show(self, overlay_widget):
        with patch.object(QWidget, "show") as mock_super:
            overlay_widget.show()
            mock_super.assert_called_once()

    def test_clamps_position_to_screen(self, overlay_widget):
        overlay_widget.move(10000, 10000)
        mock_screen = MagicMock()
        mock_screen.availableGeometry.return_value = QRect(0, 0, 1920, 1080)
        with (
            patch("overlay.QApplication.primaryScreen", return_value=mock_screen),
            patch("overlay.ctypes.windll.user32.GetWindowLongW", return_value=0),
            patch("overlay.ctypes.windll.user32.SetWindowLongW"),
        ):
            overlay_widget.show()
        pos = overlay_widget.pos()
        assert pos.x() <= 1920 - overlay_widget.width()
        assert pos.y() <= 1080 - overlay_widget.height()

    def test_applies_no_activate_style(self, overlay_widget):
        mock_screen = MagicMock()
        mock_screen.availableGeometry.return_value = QRect(0, 0, 1920, 1080)
        with (
            patch("overlay.QApplication.primaryScreen", return_value=mock_screen),
            patch("overlay.ctypes.windll.user32.GetWindowLongW", return_value=0) as mock_get,
            patch("overlay.ctypes.windll.user32.SetWindowLongW") as mock_set,
        ):
            overlay_widget.show()
            mock_get.assert_called_once()
            mock_set.assert_called_once()
            style = mock_set.call_args[0][2]
            assert style & WS_EX_NOACTIVATE


class TestPaintEvent:
    def test_paints_rounded_rect(self, overlay_widget):
        with patch("overlay.QPainter") as mock_painter:
            event = MagicMock()
            overlay_widget.paintEvent(event)
            mock_painter.assert_called_once_with(overlay_widget)


class TestMouseEvents:
    def test_press_left_button_stores_drag_pos(self, overlay_widget):
        event = MagicMock()
        event.button.return_value = Qt.MouseButton.LeftButton
        event.globalPosition.return_value.toPoint.return_value = QPoint(200, 200)
        overlay_widget.frameGeometry().topLeft()
        overlay_widget.mousePressEvent(event)
        assert overlay_widget.drag_pos is not None

    def test_press_right_button_ignored(self, overlay_widget):
        event = MagicMock()
        event.button.return_value = Qt.MouseButton.RightButton
        overlay_widget.mousePressEvent(event)
        assert overlay_widget.drag_pos is None

    def test_move_with_left_button_updates_pos(self, overlay_widget):
        overlay_widget.drag_pos = QPoint(10, 10)
        event = MagicMock()
        event.buttons.return_value = Qt.MouseButton.LeftButton
        event.globalPosition.return_value.toPoint.return_value = QPoint(300, 300)
        with patch.object(overlay_widget, "move") as mock_move:
            overlay_widget.mouseMoveEvent(event)
            mock_move.assert_called_once()

    def test_move_without_drag_pos_ignored(self, overlay_widget):
        overlay_widget.drag_pos = None
        event = MagicMock()
        event.buttons.return_value = Qt.MouseButton.LeftButton
        with patch.object(overlay_widget, "move") as mock_move:
            overlay_widget.mouseMoveEvent(event)
            mock_move.assert_not_called()

    def test_release_clears_drag_pos(self, overlay_widget):
        overlay_widget.drag_pos = QPoint(10, 10)
        event = MagicMock()
        overlay_widget.mouseReleaseEvent(event)
        assert overlay_widget.drag_pos is None
