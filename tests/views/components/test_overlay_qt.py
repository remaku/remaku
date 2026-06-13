import win32con
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent, QPaintEvent

from remaku.core.event_bus import event_bus
from remaku.views.components import overlay
from remaku.views.components.overlay import OverlayWidget, white_icon


def test_overlay_widget_sets_text(qtbot) -> None:
    overlay = OverlayWidget()
    qtbot.addWidget(overlay)

    overlay.set_text("Running")

    assert overlay.label.text() == "Running"


def test_overlay_button_emits_toggle(qtbot) -> None:
    overlay = OverlayWidget()
    qtbot.addWidget(overlay)

    with qtbot.waitSignal(event_bus.overlay_toggled, timeout=100):
        qtbot.mouseClick(overlay.button, Qt.MouseButton.LeftButton)


def test_overlay_mouse_release_emits_position(qtbot) -> None:
    overlay = OverlayWidget()
    qtbot.addWidget(overlay)
    overlay.move(12, 34)
    event = QMouseEvent(
        QMouseEvent.Type.MouseButtonRelease,
        QPointF(1, 1),
        QPointF(13, 35),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )

    with qtbot.waitSignal(event_bus.overlay_position_changed, timeout=100) as blocker:
        overlay.mouseReleaseEvent(event)

    assert overlay.drag_pos is None
    assert blocker.args == [12, 34]


def test_overlay_left_drag_moves_widget(qtbot) -> None:
    overlay = OverlayWidget()
    qtbot.addWidget(overlay)
    overlay.move(10, 20)
    press_event = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        QPointF(2, 3),
        QPointF(12, 23),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    move_event = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        QPointF(5, 8),
        QPointF(30, 45),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )

    overlay.mousePressEvent(press_event)
    overlay.mouseMoveEvent(move_event)

    assert overlay.drag_pos == QPoint(2, 3)
    assert overlay.pos() == QPoint(28, 42)


def test_overlay_ignores_move_without_drag(qtbot) -> None:
    overlay = OverlayWidget()
    qtbot.addWidget(overlay)
    overlay.move(10, 20)
    event = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        QPointF(5, 8),
        QPointF(30, 45),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )

    overlay.mouseMoveEvent(event)

    assert overlay.pos() == QPoint(10, 20)


def test_white_icon_uses_white_svg_resource_path(monkeypatch) -> None:
    paths = []

    class FakeIcon:
        def __init__(self, path: str) -> None:
            paths.append(path)

    monkeypatch.setattr("remaku.views.components.overlay.QIcon", FakeIcon)

    white_icon("pause")

    assert paths == [":/remaku/icons/pause-white.svg"]


def test_overlay_show_clamps_to_screen_and_sets_no_activate(monkeypatch, qtbot) -> None:
    widget = OverlayWidget()
    qtbot.addWidget(widget)
    widget.resize(80, 36)
    widget.move(1000, -5)
    calls = []

    class FakeGeometry:
        def width(self) -> int:
            return 120

        def height(self) -> int:
            return 90

    class FakeScreen:
        def availableGeometry(self) -> FakeGeometry:
            return FakeGeometry()

    def fake_get_long(hwnd: int, index: int) -> int:
        calls.append(("get", hwnd, index))
        return 4

    def fake_set_long(hwnd: int, index: int, style: int) -> None:
        calls.append(("set", hwnd, index, style))

    monkeypatch.setattr(overlay.QApplication, "primaryScreen", lambda: FakeScreen())
    monkeypatch.setattr(overlay.win32gui, "GetWindowLong", fake_get_long)
    monkeypatch.setattr(overlay.win32gui, "SetWindowLong", fake_set_long)

    widget.show()

    hwnd = int(widget.winId())
    assert 0 <= widget.x() <= 40
    assert widget.y() == 0
    assert calls == [
        ("get", hwnd, win32con.GWL_EXSTYLE),
        ("set", hwnd, win32con.GWL_EXSTYLE, 4 | win32con.WS_EX_NOACTIVATE),
    ]


def test_overlay_paint_event_draws_rounded_background(monkeypatch, qtbot) -> None:
    widget = OverlayWidget()
    qtbot.addWidget(widget)
    calls = []

    class FakeRenderHint:
        Antialiasing = object()

    class FakePainter:
        RenderHint = FakeRenderHint

        def __init__(self, target) -> None:
            calls.append(("init", target))

        def setRenderHint(self, hint) -> None:
            calls.append(("hint", hint))

        def setBrush(self, color) -> None:
            calls.append(("brush", color.getRgb()))

        def setPen(self, pen) -> None:
            calls.append(("pen", pen))

        def drawRoundedRect(self, rect, x_radius: int, y_radius: int) -> None:
            calls.append(("rounded", rect, x_radius, y_radius))

    monkeypatch.setattr(overlay, "QPainter", FakePainter)

    widget.paintEvent(QPaintEvent(widget.rect()))

    assert calls[0] == ("init", widget)
    assert ("brush", (0, 0, 0, 180)) in calls
    assert ("pen", Qt.PenStyle.NoPen) in calls
    assert calls[-1] == ("rounded", widget.rect(), 8, 8)
