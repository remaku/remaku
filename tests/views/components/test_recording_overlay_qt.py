from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QMouseEvent

from remaku.core.event_bus import event_bus
from remaku.views.components.recording_overlay import RecordingOverlay


def test_recording_overlay_updates_stats_and_pause_state(qtbot) -> None:
    overlay = RecordingOverlay(lambda: (65.0, 3))
    qtbot.addWidget(overlay)

    overlay.refresh_stats()
    overlay.set_paused(True)

    assert "01:05" in overlay.stats_label.text()
    assert "3 events" in overlay.stats_label.text()
    assert overlay.status_label.text() == "Paused"

    overlay.set_paused(False)

    assert overlay.status_label.text() == "Recording"


def test_recording_overlay_start_and_stop(qtbot) -> None:
    overlay = RecordingOverlay(lambda: (1.0, 1))
    qtbot.addWidget(overlay)

    overlay.start()
    assert overlay.timer.isActive()
    assert overlay.isVisible()

    overlay.stop()
    assert not overlay.timer.isActive()
    assert not overlay.isVisible()


def test_recording_overlay_buttons_emit_actions(qtbot) -> None:
    overlay = RecordingOverlay(lambda: (0.0, 0))
    qtbot.addWidget(overlay)

    buttons = [
        (overlay.pause_button, "record_pause"),
        (overlay.stop_button, "record_stop"),
        (overlay.cancel_button, "record_cancel"),
    ]

    for button, action in buttons:
        with qtbot.waitSignal(event_bus.action_triggered, timeout=100) as blocker:
            qtbot.mouseClick(button, Qt.MouseButton.LeftButton)

        assert blocker.args == [action]


def test_recording_overlay_mouse_release_emits_shared_position(qtbot) -> None:
    overlay = RecordingOverlay(lambda: (0.0, 0))
    qtbot.addWidget(overlay)
    overlay.move(22, 44)
    event = QMouseEvent(
        QMouseEvent.Type.MouseButtonRelease,
        QPointF(1, 1),
        QPointF(23, 45),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )

    with qtbot.waitSignal(event_bus.overlay_position_changed, timeout=100) as blocker:
        overlay.mouseReleaseEvent(event)

    assert blocker.args == [22, 44]
