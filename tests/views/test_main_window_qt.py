from PySide6.QtWidgets import QWidget

from remaku.views import main_window
from remaku.views.main_window import MainWindow


class FakeHomeView(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("home")


class FakeSettingsView(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("settings")


def test_main_window_creates_child_views(monkeypatch, qtbot) -> None:
    monkeypatch.setattr(main_window, "HomeView", FakeHomeView)
    monkeypatch.setattr(main_window, "SettingsView", FakeSettingsView)

    window = MainWindow()
    qtbot.addWidget(window)

    assert window.windowTitle() == "Remaku"
    assert window.home_view.objectName() == "home"
    assert window.settings_view.objectName() == "settings"
    assert window.minimumWidth() == 900
    assert window.minimumHeight() == 600


def test_main_window_always_on_top_flag(monkeypatch, qtbot) -> None:
    monkeypatch.setattr(main_window, "HomeView", FakeHomeView)
    monkeypatch.setattr(main_window, "SettingsView", FakeSettingsView)

    window = MainWindow()
    qtbot.addWidget(window)

    window.set_always_on_top(True)

    assert bool(window.windowFlags() & main_window.Qt.WindowType.WindowStaysOnTopHint)


def test_main_window_can_clear_always_on_top_flag(monkeypatch, qtbot) -> None:
    monkeypatch.setattr(main_window, "HomeView", FakeHomeView)
    monkeypatch.setattr(main_window, "SettingsView", FakeSettingsView)

    window = MainWindow()
    qtbot.addWidget(window)

    window.set_always_on_top(True)
    window.set_always_on_top(False)

    assert not bool(window.windowFlags() & main_window.Qt.WindowType.WindowStaysOnTopHint)


def test_main_window_registers_home_and_settings_views(monkeypatch, qtbot) -> None:
    monkeypatch.setattr(main_window, "HomeView", FakeHomeView)
    monkeypatch.setattr(main_window, "SettingsView", FakeSettingsView)

    window = MainWindow()
    qtbot.addWidget(window)

    assert window.stackedWidget.indexOf(window.home_view) >= 0
    assert window.stackedWidget.indexOf(window.settings_view) >= 0
