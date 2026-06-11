from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QMouseEvent

from remaku.core.event_bus import event_bus
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


def test_white_icon_uses_white_svg_resource_path(monkeypatch) -> None:
    paths = []

    class FakeIcon:
        def __init__(self, path: str) -> None:
            paths.append(path)

    monkeypatch.setattr("remaku.views.components.overlay.QIcon", FakeIcon)

    white_icon("pause")

    assert paths == [":/remaku/icons/pause-white.svg"]
