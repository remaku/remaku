from dataclasses import dataclass
from typing import Any, cast

from PySide6.QtWidgets import QApplication
from qfluentwidgets import ComboBox, LineEdit

from remaku.controllers import settings_controller
from remaku.controllers.settings_controller import SettingsController
from remaku.models.config_model import AppConfig


@dataclass
class FakeConfigModel:
    config: AppConfig
    save_calls: int = 0

    def save(self) -> None:
        self.save_calls += 1


class FakeMainWindow:
    def __init__(self) -> None:
        self.always_on_top_values: list[bool] = []

    def set_always_on_top(self, value: bool) -> None:
        self.always_on_top_values.append(value)


class FakeSignal:
    def __init__(self) -> None:
        self.callbacks = []

    def connect(self, callback) -> None:
        self.callbacks.append(callback)


class FakeCheckBox:
    def __init__(self) -> None:
        self.toggled = FakeSignal()


class FakeComboBox:
    def __init__(self) -> None:
        self.currentIndexChanged = FakeSignal()


class FakeLineEdit:
    def __init__(self) -> None:
        self.editingFinished = FakeSignal()


class FakeView:
    def __init__(self) -> None:
        self.widgets: dict = {}


def make_controller(monkeypatch) -> tuple[SettingsController, FakeConfigModel, FakeMainWindow]:
    fake_config = FakeConfigModel(AppConfig())
    main_window = FakeMainWindow()
    monkeypatch.setattr(settings_controller, "config_model", fake_config)
    controller = cast(Any, SettingsController.__new__(SettingsController))
    controller.view = FakeView()
    controller.main_window = main_window
    return cast(SettingsController, controller), fake_config, main_window


def test_init_connects_supported_widgets(monkeypatch) -> None:
    check_box = FakeCheckBox()
    combo = FakeComboBox()
    line_edit = FakeLineEdit()
    view = FakeView()
    view.widgets = {
        "general.always_on_top": check_box,
        "general.theme": combo,
        "capture.fps": line_edit,
        "ignored": object(),
    }
    main_window = FakeMainWindow()
    calls = []
    monkeypatch.setattr(settings_controller, "CheckBox", FakeCheckBox)
    monkeypatch.setattr(settings_controller, "ComboBox", FakeComboBox)
    monkeypatch.setattr(settings_controller, "LineEdit", FakeLineEdit)
    monkeypatch.setattr(
        SettingsController, "on_checkbox_changed", lambda self, key, checked: calls.append((key, checked))
    )
    monkeypatch.setattr(SettingsController, "on_combo_changed", lambda self, key: calls.append((key, "combo")))
    monkeypatch.setattr(SettingsController, "on_text_changed", lambda self, key: calls.append((key, "text")))

    SettingsController(cast(Any, view), cast(Any, main_window))
    check_box.toggled.callbacks[0](True)
    combo.currentIndexChanged.callbacks[0](0)
    line_edit.editingFinished.callbacks[0]()

    assert len(check_box.toggled.callbacks) == 1
    assert len(combo.currentIndexChanged.callbacks) == 1
    assert len(line_edit.editingFinished.callbacks) == 1
    assert calls == [
        ("general.always_on_top", True),
        ("general.theme", "combo"),
        ("capture.fps", "text"),
    ]


def test_validate_int_accepts_positive_capture_fps(monkeypatch) -> None:
    controller, _fake_config, _main_window = make_controller(monkeypatch)

    assert controller.validate_int("capture.fps", "30") == 30


def test_validate_int_rejects_non_positive_capture_fps(monkeypatch) -> None:
    controller, _fake_config, _main_window = make_controller(monkeypatch)

    assert controller.validate_int("capture.fps", "0") is None
    assert controller.validate_int("capture.fps", "bad") is None


def test_validate_int_rejects_negative_jitter(monkeypatch) -> None:
    controller, _fake_config, _main_window = make_controller(monkeypatch)

    assert controller.validate_int("input.jitter_ms", "-1") is None
    assert controller.validate_int("input.jitter_ms", "25") == 25


def test_apply_setting_saves_and_applies_always_on_top(monkeypatch) -> None:
    controller, fake_config, main_window = make_controller(monkeypatch)

    controller.apply_setting("general.always_on_top", True)

    assert fake_config.config.general.always_on_top is True
    assert fake_config.save_calls == 1
    assert main_window.always_on_top_values == [True]


def test_apply_setting_ignores_unchanged_value(monkeypatch) -> None:
    controller, fake_config, main_window = make_controller(monkeypatch)

    controller.apply_setting("general.theme", "system")

    assert fake_config.save_calls == 0
    assert main_window.always_on_top_values == []


def test_apply_setting_applies_theme(monkeypatch) -> None:
    controller, fake_config, _main_window = make_controller(monkeypatch)
    themes = []
    monkeypatch.setattr(settings_controller, "apply_theme", themes.append)

    controller.apply_setting("general.theme", "dark")

    assert fake_config.config.general.theme == "dark"
    assert fake_config.save_calls == 1
    assert themes == ["dark"]


def test_apply_setting_emits_overlay_change(monkeypatch, qtbot) -> None:
    controller, fake_config, _main_window = make_controller(monkeypatch)

    with qtbot.waitSignal(settings_controller.event_bus.settings_changed, timeout=100):
        controller.apply_setting("general.overlay_enabled", False)

    assert fake_config.config.general.overlay_enabled is False
    assert fake_config.save_calls == 1


def test_apply_setting_emits_change_for_pause_hotkey(monkeypatch, qtbot) -> None:
    controller, fake_config, _main_window = make_controller(monkeypatch)

    with qtbot.waitSignal(settings_controller.event_bus.settings_changed, timeout=100):
        controller.apply_setting("general.pause_hotkey", "ctrl+break")

    assert fake_config.config.general.pause_hotkey == "ctrl+break"
    assert fake_config.save_calls == 1


def test_on_checkbox_changed_applies_bool(monkeypatch) -> None:
    controller, fake_config, main_window = make_controller(monkeypatch)

    controller.on_checkbox_changed("general.always_on_top", True)

    assert fake_config.config.general.always_on_top is True
    assert main_window.always_on_top_values == [True]


def test_on_combo_changed_applies_current_data(monkeypatch, qtbot) -> None:
    controller, fake_config, _main_window = make_controller(monkeypatch)
    combo = ComboBox()
    qtbot.addWidget(combo)
    combo.addItem("Dark", userData="dark")
    controller.view.widgets = {"general.theme": combo}

    controller.on_combo_changed("general.theme")

    assert fake_config.config.general.theme == "dark"
    assert fake_config.save_calls == 1


def test_on_combo_changed_ignores_missing_widget(monkeypatch) -> None:
    controller, fake_config, _main_window = make_controller(monkeypatch)

    controller.on_combo_changed("general.theme")

    assert fake_config.config.general.theme == "system"
    assert fake_config.save_calls == 0


def test_on_text_changed_applies_valid_integer(monkeypatch, qtbot) -> None:
    controller, fake_config, _main_window = make_controller(monkeypatch)
    edit = LineEdit()
    qtbot.addWidget(edit)
    edit.setText(" 45 ")
    controller.view.widgets = {"capture.fps": edit}

    controller.on_text_changed("capture.fps")

    assert fake_config.config.capture.fps == 45
    assert fake_config.save_calls == 1


def test_on_text_changed_applies_pause_hotkey_text(monkeypatch, qtbot) -> None:
    controller, fake_config, _main_window = make_controller(monkeypatch)
    edit = LineEdit()
    qtbot.addWidget(edit)
    edit.setText(" Ctrl+Break ")
    controller.view.widgets = {"general.pause_hotkey": edit}

    controller.on_text_changed("general.pause_hotkey")

    assert fake_config.config.general.pause_hotkey == "ctrl+break"
    assert fake_config.save_calls == 1


def test_on_text_changed_ignores_missing_widget(monkeypatch) -> None:
    controller, fake_config, _main_window = make_controller(monkeypatch)

    controller.on_text_changed("capture.fps")

    assert fake_config.config.capture.fps == 10
    assert fake_config.save_calls == 0


def test_on_text_changed_restores_invalid_integer(monkeypatch, qtbot) -> None:
    controller, fake_config, _main_window = make_controller(monkeypatch)
    fake_config.config.capture.fps = 30
    edit = LineEdit()
    qtbot.addWidget(edit)
    edit.setText("0")
    controller.view.widgets = {"capture.fps": edit}

    controller.on_text_changed("capture.fps")

    assert edit.text() == "30"
    assert fake_config.save_calls == 0


def test_apply_language_setting_restarts_application(monkeypatch) -> None:
    controller, fake_config, _main_window = make_controller(monkeypatch)
    calls = []
    controller.restart_application = lambda: calls.append("restart")

    controller.apply_setting("general.language", "zh-TW")

    assert fake_config.config.general.language == "zh-TW"
    assert fake_config.save_calls == 1
    assert calls == ["restart"]


def test_restart_application_starts_current_program_and_quits(monkeypatch, qtbot) -> None:
    controller, _fake_config, _main_window = make_controller(monkeypatch)
    app = QApplication.instance()
    assert app is not None
    starts = []
    quits = []
    monkeypatch.setattr(settings_controller.sys, "executable", "python.exe")
    monkeypatch.setattr(settings_controller.sys, "argv", ["main.py", "--flag"])
    monkeypatch.setattr(settings_controller.sys, "frozen", False, raising=False)
    monkeypatch.setattr(
        settings_controller.QProcess, "startDetached", lambda program, args: starts.append((program, args)) or True
    )
    monkeypatch.setattr(app, "quit", lambda: quits.append("quit"))

    controller.restart_application()

    assert starts == [("python.exe", [settings_controller.os.path.abspath("main.py"), "--flag"])]
    assert quits == ["quit"]


def test_restart_application_returns_without_application(monkeypatch) -> None:
    controller, _fake_config, _main_window = make_controller(monkeypatch)
    starts = []
    monkeypatch.setattr(settings_controller.QApplication, "instance", lambda: None)
    monkeypatch.setattr(
        settings_controller.QProcess, "startDetached", lambda program, args: starts.append((program, args))
    )

    controller.restart_application()

    assert starts == []
