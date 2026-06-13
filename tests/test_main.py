import sys
from typing import cast

import pytest
from PySide6.QtWidgets import QApplication

import remaku.main as app_main
from remaku.models.config_model import AppConfig


class FakeApp:
    def __init__(self, args: list[str]) -> None:
        self.args = args
        self.translators = []

    def exec(self) -> int:
        return 7

    def installTranslator(self, translator) -> None:
        self.translators.append(translator)


class FakeWindow:
    def __init__(self) -> None:
        self.show_calls = 0

    def show(self) -> None:
        self.show_calls += 1


class FakeConfigModel:
    def __init__(self) -> None:
        self.config = AppConfig()
        self.save_calls = 0

    def save(self) -> None:
        self.save_calls += 1


def test_main_bootstraps_app_and_migrates_templates(monkeypatch) -> None:
    calls = []
    fake_config = FakeConfigModel()
    fake_windows = []
    fake_apps = []

    def make_app(args: list[str]) -> FakeApp:
        app = FakeApp(args)
        fake_apps.append(app)
        return app

    def make_window() -> FakeWindow:
        window = FakeWindow()
        fake_windows.append(window)
        return window

    monkeypatch.setattr(app_main, "setup_logging", lambda: calls.append("logging"))
    monkeypatch.setattr(app_main, "QApplication", make_app)
    monkeypatch.setattr(app_main, "load_translator", lambda app: calls.append(("translator", app)))
    monkeypatch.setattr(app_main, "MacroModel", lambda: "macro-model")
    monkeypatch.setattr(
        app_main, "migrate_legacy_templates", lambda macro_model: calls.append(("migrate", macro_model))
    )
    monkeypatch.setattr(app_main, "apply_theme", lambda theme: calls.append(("theme", theme)))
    monkeypatch.setattr(app_main, "MainWindow", make_window)
    monkeypatch.setattr(
        app_main, "MainController", lambda window, macro_model: calls.append(("controller", window, macro_model))
    )
    monkeypatch.setattr(app_main, "config_model", fake_config)
    monkeypatch.setattr(sys, "argv", ["remaku"])

    with pytest.raises(SystemExit) as error:
        app_main.main()

    assert error.value.code == 7
    assert fake_apps[0].args == ["remaku"]
    assert fake_config.config.general.templates_migrated is True
    assert fake_config.save_calls == 1
    assert fake_windows[0].show_calls == 1
    assert calls == [
        "logging",
        ("translator", fake_apps[0]),
        ("migrate", "macro-model"),
        ("theme", "system"),
        ("controller", fake_windows[0], "macro-model"),
    ]


def test_main_skips_migration_when_templates_already_migrated(monkeypatch) -> None:
    fake_config = FakeConfigModel()
    fake_config.config.general.templates_migrated = True
    migrate_calls = []

    monkeypatch.setattr(app_main, "setup_logging", lambda: None)
    monkeypatch.setattr(app_main, "QApplication", FakeApp)
    monkeypatch.setattr(app_main, "load_translator", lambda app: None)
    monkeypatch.setattr(app_main, "MacroModel", lambda: "macro-model")
    monkeypatch.setattr(app_main, "migrate_legacy_templates", lambda macro_model: migrate_calls.append(macro_model))
    monkeypatch.setattr(app_main, "apply_theme", lambda theme: None)
    monkeypatch.setattr(app_main, "MainWindow", FakeWindow)
    monkeypatch.setattr(app_main, "MainController", lambda window, macro_model: object())
    monkeypatch.setattr(app_main, "config_model", fake_config)
    monkeypatch.setattr(sys, "argv", ["remaku"])

    with pytest.raises(SystemExit):
        app_main.main()

    assert migrate_calls == []
    assert fake_config.save_calls == 0


def test_main_schedules_preview_update(monkeypatch) -> None:
    fake_config = FakeConfigModel()
    single_shots = []

    monkeypatch.setattr(app_main, "setup_logging", lambda: None)
    monkeypatch.setattr(app_main, "QApplication", FakeApp)
    monkeypatch.setattr(app_main, "load_translator", lambda app: None)
    monkeypatch.setattr(app_main, "MacroModel", lambda: "macro-model")
    monkeypatch.setattr(app_main, "migrate_legacy_templates", lambda macro_model: None)
    monkeypatch.setattr(app_main, "apply_theme", lambda theme: None)
    monkeypatch.setattr(app_main, "MainWindow", FakeWindow)
    monkeypatch.setattr(app_main, "MainController", lambda window, macro_model: object())
    monkeypatch.setattr(app_main, "config_model", fake_config)
    monkeypatch.setattr(app_main.QTimer, "singleShot", lambda delay, callback: single_shots.append((delay, callback)))
    monkeypatch.setattr(sys, "argv", ["remaku", "--preview-update"])

    with pytest.raises(SystemExit):
        app_main.main()

    assert single_shots[0][0] == 500


def test_load_translator_installs_supported_language(monkeypatch) -> None:
    fake_config = FakeConfigModel()
    fake_config.config.general.language = "zh_TW"
    fake_app = FakeApp([])

    class FakeTranslator:
        def __init__(self, app) -> None:
            self.app = app
            self.loaded_path = ""

        def load(self, path: str) -> bool:
            self.loaded_path = path
            return True

    monkeypatch.setattr(app_main, "config_model", fake_config)
    monkeypatch.setattr(app_main, "QTranslator", FakeTranslator)
    app_main.active_translator = None

    app_main.load_translator(cast(QApplication, fake_app))

    assert len(fake_app.translators) == 1
    assert app_main.active_translator is fake_app.translators[0]


def test_load_translator_ignores_unsupported_language(monkeypatch) -> None:
    fake_config = FakeConfigModel()
    fake_config.config.general.language = "en_US"
    fake_app = FakeApp([])
    monkeypatch.setattr(app_main, "config_model", fake_config)
    app_main.active_translator = None

    app_main.load_translator(cast(QApplication, fake_app))

    assert fake_app.translators == []
    assert app_main.active_translator is None
