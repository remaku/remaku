from qfluentwidgets import CheckBox, ComboBox, LineEdit

from remaku.models.config_model import AppConfig
from remaku.views import settings_view
from remaku.views.settings_view import SettingsView


class FakeConfigModel:
    def __init__(self) -> None:
        self.config = AppConfig()


def test_settings_view_creates_expected_setting_widgets(monkeypatch, qtbot) -> None:
    monkeypatch.setattr(settings_view, "config_model", FakeConfigModel())

    view = SettingsView()
    qtbot.addWidget(view)

    assert view.objectName() == "settings"
    assert set(view.widgets) == {
        "general.always_on_top",
        "general.overlay_enabled",
        "general.pause_hotkey",
        "general.check_update_on_startup",
        "general.update_channel",
        "general.theme",
        "general.language",
        "capture.fps",
        "input.jitter_ms",
    }
    assert view.widgets["capture.fps"].text() == "10"
    assert view.widgets["input.jitter_ms"].text() == "60"
    assert view.widgets["general.pause_hotkey"].text() == "ctrl+alt+p"


def test_settings_view_applies_config_values_to_widgets(monkeypatch, qtbot) -> None:
    fake_config = FakeConfigModel()
    fake_config.config.general.always_on_top = True
    fake_config.config.general.overlay_enabled = False
    fake_config.config.general.pause_hotkey = "ctrl+break"
    fake_config.config.general.update_channel = "beta"
    fake_config.config.general.theme = "dark"
    fake_config.config.general.language = "zh_TW"
    fake_config.config.capture.fps = 24
    fake_config.config.input.jitter_ms = 90
    monkeypatch.setattr(settings_view, "config_model", fake_config)

    view = SettingsView()
    qtbot.addWidget(view)

    always_on_top = view.widgets["general.always_on_top"]
    overlay_enabled = view.widgets["general.overlay_enabled"]
    pause_hotkey = view.widgets["general.pause_hotkey"]
    update_channel = view.widgets["general.update_channel"]
    theme = view.widgets["general.theme"]
    language = view.widgets["general.language"]
    fps = view.widgets["capture.fps"]
    jitter = view.widgets["input.jitter_ms"]

    assert isinstance(always_on_top, CheckBox)
    assert always_on_top.isChecked()
    assert isinstance(overlay_enabled, CheckBox)
    assert not overlay_enabled.isChecked()
    assert isinstance(pause_hotkey, LineEdit)
    assert pause_hotkey.text() == "ctrl+break"
    assert isinstance(update_channel, ComboBox)
    assert update_channel.currentData() == "beta"
    assert isinstance(theme, ComboBox)
    assert theme.currentData() == "dark"
    assert isinstance(language, ComboBox)
    assert language.currentData() == "zh_TW"
    assert isinstance(fps, LineEdit)
    assert fps.text() == "24"
    assert isinstance(jitter, LineEdit)
    assert jitter.text() == "90"
