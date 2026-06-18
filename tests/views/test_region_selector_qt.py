from typing import Any, cast

import numpy as np
import pytest
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QImage, QKeyEvent, QMouseEvent, QPixmap

from remaku.views import region_selector
from remaku.views.region_selector import RegionSelector


class FakeScreen:
    def __init__(self, pixmap: QPixmap, geometry: QRect | None = None) -> None:
        self.pixmap = pixmap
        self.screen_geometry = geometry or QRect(0, 0, pixmap.width(), pixmap.height())

    def geometry(self) -> QRect:
        return self.screen_geometry

    def availableGeometry(self) -> QRect:
        return self.screen_geometry

    def name(self) -> str:
        return "DISPLAY1"

    def devicePixelRatio(self) -> float:
        return 1.0

    def logicalDotsPerInch(self) -> float:
        return 96.0

    def physicalDotsPerInch(self) -> float:
        return 96.0


def make_pixmap(width: int = 8, height: int = 6) -> QPixmap:
    image = QImage(width, height, QImage.Format.Format_BGR888)
    image.fill(1)
    return QPixmap.fromImage(image)


def make_selector(monkeypatch, qtbot) -> RegionSelector:
    screen = FakeScreen(make_pixmap())
    target = region_selector.display.DisplayTarget(
        screen=cast(Any, screen),
        physical_rect=region_selector.display.window.Rect(0, 0, 8, 6),
    )
    monkeypatch.setattr(region_selector.display, "display_target_at_cursor", lambda: target)
    monkeypatch.setattr(region_selector, "grab_screen", lambda target_display: (screen.pixmap, np.ones((6, 8, 3))))
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
    screens = []

    class FakeHandle:
        def setScreen(self, screen) -> None:
            screens.append(screen)

    monkeypatch.setattr(selector, "windowHandle", lambda: FakeHandle())
    monkeypatch.setattr(selector, "showFullScreen", lambda: shown.append(True))

    selector.start()

    assert shown == [True]
    assert screens == [selector.target_screen]


def test_region_selector_raises_when_screen_missing(monkeypatch) -> None:
    monkeypatch.setattr(region_selector.display, "display_target_at_cursor", lambda: None)

    with pytest.raises(RuntimeError, match="No screen"):
        RegionSelector("macro")


def test_region_selector_uses_target_screen_over_cursor_screen(monkeypatch, qtbot) -> None:
    cursor_screen = FakeScreen(make_pixmap(8, 6))
    target_screen = FakeScreen(make_pixmap(12, 9), QRect(1920, 0, 1280, 720))
    target_display = region_selector.display.DisplayTarget(
        screen=cast(Any, target_screen),
        physical_rect=region_selector.display.window.Rect(1920, 1080, 1280, 720),
    )
    grabbed_targets = []
    monkeypatch.setattr(
        region_selector.display,
        "display_target_at_cursor",
        lambda: region_selector.display.DisplayTarget(
            screen=cast(Any, cursor_screen),
            physical_rect=region_selector.display.window.Rect(0, 0, 8, 6),
        ),
    )
    monkeypatch.setattr(
        region_selector,
        "grab_screen",
        lambda target: grabbed_targets.append(target) or (target_screen.pixmap, np.ones((9, 12, 3))),
    )

    selector = RegionSelector("macro", target_display=target_display)
    qtbot.addWidget(selector)

    assert selector.target_screen is target_screen
    assert selector.target_display is target_display
    assert selector.frame_width == 12
    assert selector.frame_height == 9
    assert grabbed_targets == [target_display]


def test_region_selector_emits_physical_capture_size_for_mixed_dpi(monkeypatch, tmp_path, qtbot) -> None:
    screen = FakeScreen(make_pixmap(12, 8))
    target_display = region_selector.display.DisplayTarget(
        screen=cast(Any, screen),
        physical_rect=region_selector.display.window.Rect(0, 1080, 12, 8),
    )
    monkeypatch.setattr(region_selector, "grab_screen", lambda target: (screen.pixmap, np.ones((8, 12, 3))))
    selector = RegionSelector("macro", target_display=target_display)
    selector.resize(6, 4)
    qtbot.addWidget(selector)
    encoded = np.array([1, 2, 3], dtype=np.uint8)

    monkeypatch.setattr(region_selector.time, "time", lambda: 123.0)
    monkeypatch.setattr(region_selector, "templates_dir", lambda macro_id: tmp_path / "templates" / macro_id)
    monkeypatch.setattr(region_selector.cv2, "imencode", lambda extension, image: (True, encoded))

    with qtbot.waitSignal(selector.region_selected, timeout=100) as blocker:
        selector.save_region(QRect(0, 0, 3, 2))

    assert blocker.args == ["123", 12, 8]


def test_grab_screen_uses_physical_screen_rect(monkeypatch, qtbot) -> None:
    del qtbot
    screen = FakeScreen(make_pixmap(4, 3))
    target_display = region_selector.display.DisplayTarget(
        screen=cast(Any, screen),
        physical_rect=region_selector.display.window.Rect(1920, 1080, 4, 3),
    )
    calls = []

    class FakeMss:
        def __init__(self) -> None:
            self.monitors = [{"left": 0, "top": 0, "width": 8, "height": 6}]

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback) -> None:
            pass

        def grab(self, region):
            calls.append(region)
            return np.zeros((region["height"], region["width"], 4), dtype=np.uint8)

    monkeypatch.setattr(region_selector.mss, "mss", FakeMss)

    pixmap, frame = region_selector.grab_screen(target_display)

    assert calls == [{"left": 1920, "top": 1080, "width": 4, "height": 3}]
    assert pixmap.width() == 4
    assert pixmap.height() == 3
    assert frame.shape == (3, 4, 3)


def test_grab_screen_writes_debug_images_when_enabled(monkeypatch, tmp_path, qtbot) -> None:
    del qtbot
    screen = FakeScreen(make_pixmap(4, 3), QRect(0, 720, 4, 3))
    target_display = region_selector.display.DisplayTarget(
        screen=cast(Any, screen),
        physical_rect=region_selector.display.window.Rect(0, 1080, 4, 3),
    )

    class FakeMss:
        def __init__(self) -> None:
            self.monitors = [{"left": 0, "top": 0, "width": 8, "height": 6}]

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback) -> None:
            pass

        def grab(self, region):
            value = 10 if region["top"] == 1080 else 20
            return np.full((region["height"], region["width"], 4), value, dtype=np.uint8)

    monkeypatch.setenv(region_selector.CAPTURE_DEBUG_ENV, "1")
    monkeypatch.setattr(region_selector, "log_dir", lambda: tmp_path)
    monkeypatch.setattr(region_selector.QApplication, "screens", lambda: [screen])
    monkeypatch.setattr(region_selector.display.win32api, "EnumDisplayMonitors", lambda: [])
    monkeypatch.setattr(region_selector.mss, "mss", FakeMss)

    _pixmap, frame = region_selector.grab_screen(target_display)

    debug_dirs = list((tmp_path / "capture-debug").iterdir())
    assert len(debug_dirs) == 1
    assert (debug_dirs[0] / "selected-screen.png").exists()
    assert (debug_dirs[0] / "merged-screen.png").exists()
    assert (debug_dirs[0] / "metadata.json").exists()
    assert frame.shape == (3, 4, 3)
    assert '"top": 1080' in (debug_dirs[0] / "metadata.json").read_text(encoding="utf-8")


def test_region_selector_target_screen_keeps_existing_compatibility(monkeypatch, qtbot) -> None:
    screen = FakeScreen(make_pixmap(5, 4), QRect(0, 720, 5, 4))
    physical_rect = region_selector.display.window.Rect(0, 1080, 5, 4)
    grabbed_targets = []
    monkeypatch.setattr(region_selector.display, "physical_rect_for_screen", lambda target_screen: physical_rect)
    monkeypatch.setattr(
        region_selector,
        "grab_screen",
        lambda target: grabbed_targets.append(target) or (screen.pixmap, np.ones((4, 5, 3))),
    )

    selector = RegionSelector("macro", target_screen=cast(Any, screen))
    qtbot.addWidget(selector)

    assert selector.target_screen is screen
    assert selector.target_display.physical_rect == physical_rect
    assert grabbed_targets == [selector.target_display]


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
    encoded_inputs = []
    monkeypatch.setattr(region_selector.time, "time", lambda: 123.0)
    monkeypatch.setattr(region_selector, "templates_dir", lambda macro_id: tmp_path / "templates" / macro_id)
    monkeypatch.setattr(
        region_selector.cv2,
        "imencode",
        lambda extension, image: encoded_inputs.append((extension, image.copy())) or (True, encoded),
    )

    with qtbot.waitSignal(selector.region_selected, timeout=100) as blocker:
        selector.save_region(QRect(0, 0, 2, 2))

    assert blocker.args == ["123", 8, 6]
    assert (tmp_path / "templates" / "macro" / "123.png").read_bytes() == encoded.tobytes()
    assert encoded_inputs[0][0] == ".png"
    assert encoded_inputs[0][1].shape == (4, 4, 3)


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
