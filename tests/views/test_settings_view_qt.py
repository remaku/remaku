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
        "general.check_update_on_startup",
        "general.update_channel",
        "general.theme",
        "general.language",
        "capture.fps",
        "input.jitter_ms",
    }
    assert view.widgets["capture.fps"].text() == "10"
    assert view.widgets["input.jitter_ms"].text() == "60"
