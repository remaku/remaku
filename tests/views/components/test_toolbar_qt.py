from PySide6.QtCore import Qt

from remaku.core.event_bus import event_bus
from remaku.views.components.toolbar import Toolbar


def test_toolbar_updates_run_button_for_running_state(qtbot) -> None:
    toolbar = Toolbar()
    qtbot.addWidget(toolbar)

    toolbar.handle_macro_running_changed(True)
    assert toolbar.run_button.text() == "Stop"

    toolbar.handle_macro_running_changed(False)
    assert toolbar.run_button.text() == "Run"


def test_toolbar_run_button_emits_action(qtbot) -> None:
    toolbar = Toolbar()
    qtbot.addWidget(toolbar)

    with qtbot.waitSignal(event_bus.action_triggered, timeout=100) as blocker:
        qtbot.mouseClick(toolbar.run_button, Qt.MouseButton.LeftButton)

    assert blocker.args == ["run"]
