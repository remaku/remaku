from dataclasses import dataclass

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


class FakeSignal:
    def __init__(self) -> None:
        self.emitted_values: list[int] = []

    def emit(self, value: int) -> None:
        self.emitted_values.append(value)


@dataclass
class FakeEventBus:
    hotkey_triggered: FakeSignal


@dataclass
class FakeMessage:
    message: int
    wParam: int
    hWnd: int = 1


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


def test_main_window_emits_windows_hotkey(monkeypatch, qtbot) -> None:
    monkeypatch.setattr(main_window, "HomeView", FakeHomeView)

    monkeypatch.setattr(main_window, "SettingsView", FakeSettingsView)
    fake_signal = FakeSignal()
    monkeypatch.setattr(main_window, "event_bus", FakeEventBus(fake_signal))

    window = MainWindow()
    qtbot.addWidget(window)

    with monkeypatch.context() as patch:
        patch.setattr(
            main_window.ctypes.wintypes.MSG,
            "from_address",
            lambda message: FakeMessage(message=0x0312, wParam=99),
        )
        window.nativeEvent(b"windows_generic_MSG", 123)

    assert fake_signal.emitted_values == [99]


def test_main_window_ignores_non_hotkey_native_event(monkeypatch, qtbot) -> None:
    monkeypatch.setattr(main_window, "HomeView", FakeHomeView)

    monkeypatch.setattr(main_window, "SettingsView", FakeSettingsView)
    fake_signal = FakeSignal()
    monkeypatch.setattr(main_window, "event_bus", FakeEventBus(fake_signal))

    window = MainWindow()
    qtbot.addWidget(window)

    with monkeypatch.context() as patch:
        patch.setattr(
            main_window.ctypes.wintypes.MSG,
            "from_address",
            lambda message: FakeMessage(message=0x0001, wParam=99),
        )
        window.nativeEvent(b"windows_generic_MSG", 123)
        window.nativeEvent(b"other", 123)

    assert fake_signal.emitted_values == []
