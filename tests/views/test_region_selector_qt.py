from typing import Any, cast

import numpy as np
import pytest
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QImage, QKeyEvent, QMouseEvent, QPixmap

from remaku.views import region_selector
from remaku.views.region_selector import RegionSelector


class FakeScreen:
    def __init__(self, pixmap: QPixmap) -> None:
        self.pixmap = pixmap

    def grabWindow(self, window_id: int) -> QPixmap:
        assert window_id == 0
        return self.pixmap


def make_pixmap(width: int = 8, height: int = 6) -> QPixmap:
    image = QImage(width, height, QImage.Format.Format_BGR888)
    image.fill(1)
    return QPixmap.fromImage(image)


def make_selector(monkeypatch, qtbot) -> RegionSelector:
    monkeypatch.setattr(region_selector.QApplication, "primaryScreen", lambda: FakeScreen(make_pixmap()))
    selector = RegionSelector("macro")
    selector.resize(4, 3)
    qtbot.addWidget(selector)
    return selector


def test_region_selector_maps_widget_rect_to_frame_rect(monkeypatch, qtbot) -> None:
    selector = make_selector(monkeypatch, qtbot)

    frame_rect = selector.to_frame_rect(QRect(1, 1, 2, 1))

    assert frame_rect == QRect(2, 2, 4, 2)


def test_region_selector_start_shows_full_screen(monkeypatch, qtbot) -> None:
    selector = make_selector(monkeypatch, qtbot)
    shown = []
    monkeypatch.setattr(selector, "showFullScreen", lambda: shown.append(True))

    selector.start()

    assert shown == [True]


def test_region_selector_raises_when_primary_screen_missing(monkeypatch) -> None:
    monkeypatch.setattr(region_selector.QApplication, "primaryScreen", lambda: None)

    with pytest.raises(RuntimeError, match="No primary screen"):
        RegionSelector("macro")


def test_region_selector_zero_size_uses_safe_scale(monkeypatch, qtbot) -> None:
    selector = make_selector(monkeypatch, qtbot)
    selector.resize(0, 0)

    frame_rect = selector.to_frame_rect(QRect(1, 1, 2, 2))

    assert frame_rect == QRect(8, 6, 16, 12)


def test_region_selector_paint_event_draws_background_and_selection(monkeypatch, qtbot) -> None:
    selector = make_selector(monkeypatch, qtbot)
    selector.origin = QPoint(0, 0)
    selector.current = QPoint(2, 2)
    selector.selecting = True
    calls = []

    class FakePainter:
        def __init__(self, target) -> None:
            self.target = target

        def drawPixmap(self, *args) -> None:
            calls.append(("pixmap", args))

        def fillRect(self, rect, color) -> None:
            calls.append(("fill", rect, color.getRgb()))

        def setPen(self, pen) -> None:
            calls.append(("pen", pen.width()))

        def drawRect(self, rect) -> None:
            calls.append(("rect", rect))

    monkeypatch.setattr(region_selector, "QPainter", FakePainter)

    selector.paintEvent(cast(Any, None))

    assert calls[0][0] == "pixmap"
    assert calls[1][0] == "fill"
    assert calls[2][0] == "pixmap"
    assert calls[-1] == ("rect", QRect(0, 0, 3, 3))


def test_region_selector_paint_event_skips_selection_when_not_selecting(monkeypatch, qtbot) -> None:
    selector = make_selector(monkeypatch, qtbot)
    selector.selecting = False
    calls = []

    class FakePainter:
        def __init__(self, target) -> None:
            self.target = target

        def drawPixmap(self, *args) -> None:
            calls.append(("pixmap", args))

        def fillRect(self, rect, color) -> None:
            calls.append(("fill", rect, color.getRgb()))

    monkeypatch.setattr(region_selector, "QPainter", FakePainter)

    selector.paintEvent(cast(Any, None))

    assert [call[0] for call in calls] == ["pixmap", "fill"]


def test_region_selector_save_region_writes_template_and_emits_signal(tmp_path, monkeypatch, qtbot) -> None:
    selector = make_selector(monkeypatch, qtbot)
    encoded = np.array([1, 2, 3], dtype=np.uint8)
    monkeypatch.setattr(region_selector.time, "time", lambda: 123.0)
    monkeypatch.setattr(region_selector, "templates_dir", lambda macro_id: tmp_path / "templates" / macro_id)
    monkeypatch.setattr(region_selector.cv2, "cvtColor", lambda image, code: image[:, :, 0])
    monkeypatch.setattr(region_selector.cv2, "imencode", lambda extension, image: (True, encoded))

    with qtbot.waitSignal(selector.region_selected, timeout=100) as blocker:
        selector.save_region(QRect(0, 0, 2, 2))

    assert blocker.args == ["123", 8, 6]
    assert (tmp_path / "templates" / "macro" / "123.png").read_bytes() == encoded.tobytes()


def test_region_selector_escape_emits_cancelled(monkeypatch, qtbot) -> None:
    selector = make_selector(monkeypatch, qtbot)
    event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)

    with qtbot.waitSignal(selector.cancelled, timeout=100):
        selector.keyPressEvent(event)

    assert selector.selecting is False


def make_mouse_event(
    event_type: QMouseEvent.Type,
    point: QPoint,
    button: Qt.MouseButton = Qt.MouseButton.LeftButton,
    buttons: Qt.MouseButton = Qt.MouseButton.LeftButton,
) -> QMouseEvent:
    return QMouseEvent(
        event_type,
        point,
        point,
        button,
        buttons,
        Qt.KeyboardModifier.NoModifier,
    )


def test_region_selector_mouse_drag_saves_large_region(monkeypatch, qtbot) -> None:
    selector = make_selector(monkeypatch, qtbot)
    saved_rects = []
    selector.save_region = lambda rect: saved_rects.append(rect)

    selector.mousePressEvent(make_mouse_event(QMouseEvent.Type.MouseButtonPress, QPoint(0, 0)))
    selector.mouseMoveEvent(make_mouse_event(QMouseEvent.Type.MouseMove, QPoint(6, 6)))
    selector.mouseReleaseEvent(make_mouse_event(QMouseEvent.Type.MouseButtonRelease, QPoint(6, 6)))

    assert selector.selecting is False
    assert saved_rects == [QRect(0, 0, 7, 7)]


def test_region_selector_mouse_drag_cancels_small_region(monkeypatch, qtbot) -> None:
    selector = make_selector(monkeypatch, qtbot)
    selector.save_region = lambda rect: None

    selector.mousePressEvent(make_mouse_event(QMouseEvent.Type.MouseButtonPress, QPoint(0, 0)))

    with qtbot.waitSignal(selector.cancelled, timeout=100):
        selector.mouseReleaseEvent(make_mouse_event(QMouseEvent.Type.MouseButtonRelease, QPoint(5, 5)))

    assert selector.selecting is False


def test_region_selector_ignores_non_left_mouse_press(monkeypatch, qtbot) -> None:
    selector = make_selector(monkeypatch, qtbot)

    selector.mousePressEvent(
        make_mouse_event(
            QMouseEvent.Type.MouseButtonPress,
            QPoint(1, 1),
            button=Qt.MouseButton.RightButton,
            buttons=Qt.MouseButton.RightButton,
        )
    )

    assert selector.selecting is False


def test_region_selector_mouse_move_ignored_when_not_selecting(monkeypatch, qtbot) -> None:
    selector = make_selector(monkeypatch, qtbot)
    selector.current = QPoint(1, 1)

    selector.mouseMoveEvent(make_mouse_event(QMouseEvent.Type.MouseMove, QPoint(4, 4)))

    assert selector.current == QPoint(1, 1)


def test_region_selector_mouse_release_ignored_when_not_selecting(monkeypatch, qtbot) -> None:
    selector = make_selector(monkeypatch, qtbot)
    saved_rects = []
    selector.save_region = lambda rect: saved_rects.append(rect)

    selector.mouseReleaseEvent(make_mouse_event(QMouseEvent.Type.MouseButtonRelease, QPoint(6, 6)))

    assert saved_rects == []
    assert selector.selecting is False


def test_region_selector_ignores_non_escape_key(monkeypatch, qtbot) -> None:
    selector = make_selector(monkeypatch, qtbot)
    selector.selecting = True
    event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)

    selector.keyPressEvent(event)

    assert selector.selecting is True
