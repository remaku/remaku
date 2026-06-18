from dataclasses import dataclass
from typing import Any, ClassVar, cast

from PySide6.QtCore import QObject, QRect

from remaku.controllers import main_controller
from remaku.controllers.main_controller import MainController
from remaku.models.config_model import AppConfig
from remaku.services.engine import Status


@dataclass
class FakeConfigModel:
    config: AppConfig
    save_calls: int = 0

    def save(self) -> None:
        self.save_calls += 1


class FakeOverlay:
    def __init__(self) -> None:
        self.moved_to: tuple[int, int] | None = None
        self.text = ""
        self.show_calls = 0
        self.hide_calls = 0
        self.paused_values: list[bool] = []

    def move(self, x: int, y: int) -> None:
        self.moved_to = (x, y)

    def set_text(self, text: str) -> None:
        self.text = text

    def set_paused(self, paused: bool) -> None:
        self.paused_values.append(paused)

    def show(self) -> None:
        self.show_calls += 1

    def hide(self) -> None:
        self.hide_calls += 1


class FakeHomeController:
    def __init__(self) -> None:
        self.current_runner: object | None = None
        self.highlight_calls = 0

    def highlight_current_step(self) -> None:
        self.highlight_calls += 1

    def describe_step(self, step: dict) -> str:
        return f"step:{step['type']}"


class FakePackExplorerController:
    def __init__(self) -> None:
        self.ensure_loaded_calls = 0

    def ensure_loaded(self) -> None:
        self.ensure_loaded_calls += 1


class FakeMainWindow(QObject):
    def __init__(self) -> None:
        super().__init__()
        self.switched_to = None
        self.always_on_top_values: list[bool] = []
        self.home_view = object()
        self.pack_explorer_view = object()
        self.settings_view = object()
        self.screen_geometry = QRect(0, 0, 1920, 1080)

    def set_always_on_top(self, value: bool) -> None:
        self.always_on_top_values.append(value)

    def switchTo(self, view) -> None:
        self.switched_to = view

    def screen(self):
        return FakeScreen(self.screen_geometry)


class FakeScreen:
    def __init__(self, geometry: QRect) -> None:
        self.geometry = geometry

    def availableGeometry(self) -> QRect:
        return self.geometry


class FakeTimer:
    single_shots: ClassVar[list[tuple[int, object]]] = []

    def __init__(self, parent: object) -> None:
        self.parent = parent
        self.interval = 0
        self.callback = None
        self.started = False
        self.timeout = self

    def setInterval(self, interval: int) -> None:
        self.interval = interval

    def connect(self, callback: object) -> None:
        self.callback = callback

    def start(self) -> None:
        self.started = True

    @classmethod
    def singleShot(cls, interval: int, callback: object) -> None:
        cls.single_shots.append((interval, callback))


class FakeRunner:
    label = "Sample"
    start_time: object | None = None

    def __init__(self, status: Status) -> None:
        self.status = status
        self.current_step = {"type": "key"}

    def get_status(self) -> Status:
        return self.status

    def template_label(self, template_id: str) -> str:
        return f"Template {template_id}"


def make_controller(
    monkeypatch,
) -> tuple[MainController, FakeConfigModel, FakeHomeController, FakeOverlay, FakeMainWindow]:
    fake_config = FakeConfigModel(AppConfig())
    fake_home = FakeHomeController()
    fake_overlay = FakeOverlay()
    fake_window = FakeMainWindow()
    monkeypatch.setattr(main_controller, "config_model", fake_config)
    controller = cast(Any, MainController.__new__(MainController))
    controller.main_window = fake_window
    controller.home_controller = fake_home
    controller.overlay = fake_overlay
    return cast(MainController, controller), fake_config, fake_home, fake_overlay, fake_window


def test_init_wires_dependencies_and_startup_check(monkeypatch) -> None:
    fake_config = FakeConfigModel(AppConfig())
    fake_config.config.general.always_on_top = True
    main_window = FakeMainWindow()
    macro_model = object()
    home_controllers = []
    settings_controllers = []
    pack_controllers = []
    overlays = []
    FakeTimer.single_shots = []
    monkeypatch.setattr(main_controller, "config_model", fake_config)
    monkeypatch.setattr(
        main_controller,
        "HomeController",
        lambda view, model: home_controllers.append((view, model)) or FakeHomeController(),
    )
    monkeypatch.setattr(
        main_controller,
        "SettingsController",
        lambda view, window: settings_controllers.append((view, window)) or object(),
    )
    monkeypatch.setattr(
        main_controller,
        "PackExplorerController",
        lambda view, model: pack_controllers.append((view, model)) or FakePackExplorerController(),
    )
    monkeypatch.setattr(main_controller, "OverlayWidget", lambda: overlays.append(FakeOverlay()) or overlays[-1])
    monkeypatch.setattr(main_controller, "QTimer", FakeTimer)

    controller = MainController(cast(Any, main_window), cast(Any, macro_model))

    assert main_window.always_on_top_values == [True]
    assert home_controllers == [(main_window.home_view, macro_model)]
    assert pack_controllers == [(main_window.pack_explorer_view, macro_model)]
    assert settings_controllers == [(main_window.settings_view, main_window)]
    assert overlays[0].moved_to == (100, 100)
    assert overlays[0].hide_calls == 1
    assert cast(Any, controller).overlay_timer.interval == 200
    assert cast(Any, controller).overlay_timer.callback == controller.refresh_overlay
    assert cast(Any, controller).overlay_timer.started is True
    assert FakeTimer.single_shots == [(1000, controller.startup_check_update)]


def test_init_skips_startup_check_when_disabled(monkeypatch) -> None:
    fake_config = FakeConfigModel(AppConfig())
    fake_config.config.general.check_update_on_startup = False
    FakeTimer.single_shots = []
    monkeypatch.setattr(main_controller, "config_model", fake_config)
    monkeypatch.setattr(main_controller, "HomeController", lambda view, model: FakeHomeController())
    monkeypatch.setattr(main_controller, "SettingsController", lambda view, window: object())
    monkeypatch.setattr(main_controller, "PackExplorerController", lambda view, model: FakePackExplorerController())
    monkeypatch.setattr(main_controller, "OverlayWidget", FakeOverlay)
    monkeypatch.setattr(main_controller, "QTimer", FakeTimer)

    MainController(cast(Any, FakeMainWindow()), cast(Any, object()))

    assert FakeTimer.single_shots == []


def test_update_overlay_position_saves_config_and_moves_overlay(monkeypatch) -> None:
    controller, fake_config, _home, overlay, _window = make_controller(monkeypatch)

    controller.update_overlay_position(12, 34)

    assert fake_config.config.general.overlay_position == (12, 34)
    assert fake_config.save_calls == 1
    assert overlay.moved_to == (12, 34)


def test_apply_overlay_settings_moves_overlay(monkeypatch) -> None:
    controller, fake_config, _home, overlay, _window = make_controller(monkeypatch)
    fake_config.config.general.overlay_position = (20, 40)

    controller.apply_overlay_settings()

    assert overlay.moved_to == (20, 40)


def test_apply_overlay_settings_places_default_position_on_main_window_screen(monkeypatch) -> None:
    controller, _fake_config, _home, overlay, window = make_controller(monkeypatch)
    window.screen_geometry = QRect(734, 2160, 2420, 1668)

    controller.apply_overlay_settings()

    assert overlay.moved_to == (834, 2260)


def test_refresh_overlay_hides_when_no_runner(monkeypatch) -> None:
    controller, _fake_config, _home, overlay, _window = make_controller(monkeypatch)

    controller.refresh_overlay()

    assert overlay.hide_calls == 1


def test_refresh_overlay_hides_when_runner_is_not_running(monkeypatch) -> None:
    controller, _fake_config, home, overlay, _window = make_controller(monkeypatch)
    home.current_runner = FakeRunner(Status(running=False))

    controller.refresh_overlay()

    assert overlay.hide_calls == 1


def test_refresh_overlay_shows_running_status(monkeypatch) -> None:
    controller, fake_config, home, overlay, _window = make_controller(monkeypatch)
    fake_config.config.general.overlay_enabled = True
    home.current_runner = FakeRunner(Status(running=True, progress=1, repeat_total=3, score=0.92, match_id="start"))

    controller.refresh_overlay()

    assert home.highlight_calls == 1
    assert overlay.show_calls == 1
    assert overlay.paused_values == [False]
    assert "Sample" in overlay.text
    assert "Loop 1/3" in overlay.text
    assert "step:key" in overlay.text
    assert "Template start 92%" in overlay.text


def test_refresh_overlay_uses_waiting_state_message(monkeypatch) -> None:
    controller, fake_config, home, overlay, _window = make_controller(monkeypatch)
    fake_config.config.general.overlay_enabled = True
    home.current_runner = FakeRunner(Status(running=True, state="waiting_window"))

    controller.refresh_overlay()

    assert overlay.show_calls == 1
    assert overlay.text == "Open the selected window to continue"


def test_refresh_overlay_uses_elapsed_time_and_paused_state(monkeypatch) -> None:
    controller, fake_config, home, overlay, _window = make_controller(monkeypatch)
    fake_config.config.general.overlay_enabled = True
    runner = FakeRunner(Status(running=True, paused=True, state="paused", elapsed_s=125))
    runner.start_time = object()
    home.current_runner = runner

    controller.refresh_overlay()

    assert overlay.text == "02:05 | Paused"
    assert overlay.paused_values == [True]
    assert overlay.show_calls == 1


def test_refresh_overlay_shows_score_without_match_label(monkeypatch) -> None:
    controller, fake_config, home, overlay, _window = make_controller(monkeypatch)
    fake_config.config.general.overlay_enabled = True
    home.current_runner = FakeRunner(Status(running=True, score=0.5))

    controller.refresh_overlay()

    assert overlay.text == "Running: Sample | step:key | 50%"


def test_refresh_overlay_updates_text_without_showing_when_disabled(monkeypatch) -> None:
    controller, fake_config, home, overlay, _window = make_controller(monkeypatch)
    fake_config.config.general.overlay_enabled = False
    home.current_runner = FakeRunner(Status(running=True))

    controller.refresh_overlay()

    assert overlay.text == "Running: Sample | step:key"
    assert overlay.show_calls == 0


def test_switch_page_shows_packs_and_loads_explorer(monkeypatch) -> None:
    controller, _fake_config, _home, _overlay, window = make_controller(monkeypatch)
    pack_controller = FakePackExplorerController()
    cast(Any, controller).pack_explorer_controller = pack_controller

    controller.switch_page("packs")

    assert window.switched_to is window.pack_explorer_view
    assert pack_controller.ensure_loaded_calls == 1


def test_switch_page_shows_settings(monkeypatch) -> None:
    controller, _fake_config, _home, _overlay, window = make_controller(monkeypatch)

    controller.switch_page("settings")

    assert window.switched_to is window.settings_view


def test_switch_page_ignores_unknown_page(monkeypatch) -> None:
    controller, _fake_config, _home, _overlay, window = make_controller(monkeypatch)

    controller.switch_page("home")

    assert window.switched_to is None


def test_prompt_update_shows_dialog(monkeypatch) -> None:
    controller, _fake_config, _home, _overlay, window = make_controller(monkeypatch)
    shown = []
    dialogs = []
    info = main_controller.UpdateInfo("v2.0.0", (2, 0, 0, 999999), "", "", "")

    class FakeDialog:
        def __init__(self, parent: object, update_info: main_controller.UpdateInfo) -> None:
            dialogs.append((parent, update_info))

        def show(self) -> None:
            shown.append("show")

    monkeypatch.setattr(main_controller, "UpdateDialog", FakeDialog)

    controller.prompt_update(info)

    assert dialogs == [(window, info)]
    assert shown == ["show"]


def test_startup_check_update_skips_remembered_version(monkeypatch) -> None:
    controller, fake_config, _home, _overlay, _window = make_controller(monkeypatch)
    prompts = []
    callbacks = []
    fake_config.config.general.skipped_version = "v2.0.0"

    def prompt_update(info: main_controller.UpdateInfo) -> None:
        prompts.append(info)

    cast(Any, controller).prompt_update = prompt_update
    monkeypatch.setattr(main_controller, "check_async", lambda parent, callback: callbacks.append(callback))

    controller.startup_check_update()
    callbacks[0](
        main_controller.CheckResult(
            status="available", info=main_controller.UpdateInfo("v2.0.0", (2, 0, 0, 999999), "", "", "")
        )
    )

    assert prompts == []


def test_check_updates_prompts_available_update(monkeypatch) -> None:
    controller, _fake_config, _home, _overlay, _window = make_controller(monkeypatch)
    prompts = []
    callbacks = []
    info = main_controller.UpdateInfo("v2.0.0", (2, 0, 0, 999999), "", "", "")

    def prompt_update(info: main_controller.UpdateInfo) -> None:
        prompts.append(info)

    cast(Any, controller).prompt_update = prompt_update
    monkeypatch.setattr(main_controller, "check_async", lambda parent, callback: callbacks.append(callback))

    controller.check_updates()
    callbacks[0](main_controller.CheckResult(status="available", info=info))

    assert prompts == [info]


def test_check_updates_reports_up_to_date(monkeypatch) -> None:
    controller, _fake_config, _home, _overlay, _window = make_controller(monkeypatch)
    callbacks = []
    messages = []
    monkeypatch.setattr(main_controller, "check_async", lambda parent, callback: callbacks.append(callback))
    monkeypatch.setattr(
        main_controller,
        "show_message_dialog",
        lambda parent, title, content: messages.append((title, content)),
    )

    controller.check_updates()
    callbacks[0](main_controller.CheckResult(status="up_to_date"))

    assert messages == [("Up to date", "You are already using the latest version.")]


def test_check_updates_reports_failure(monkeypatch) -> None:
    controller, _fake_config, _home, _overlay, _window = make_controller(monkeypatch)
    callbacks = []
    messages = []
    monkeypatch.setattr(main_controller, "check_async", lambda parent, callback: callbacks.append(callback))
    monkeypatch.setattr(
        main_controller,
        "show_message_dialog",
        lambda parent, title, content: messages.append((title, content)),
    )

    controller.check_updates()
    callbacks[0](main_controller.CheckResult(status="error", error="Network unavailable"))

    assert messages == [("Update check failed", "Network unavailable")]


def test_startup_check_update_prompts_available_update(monkeypatch) -> None:
    controller, _fake_config, _home, _overlay, _window = make_controller(monkeypatch)
    prompts = []
    callbacks = []
    info = main_controller.UpdateInfo("v2.0.0", (2, 0, 0, 999999), "", "", "")
    cast(Any, controller).prompt_update = prompts.append
    monkeypatch.setattr(main_controller, "check_async", lambda parent, callback: callbacks.append(callback))

    controller.startup_check_update()
    callbacks[0](main_controller.CheckResult(status="available", info=info))

    assert prompts == [info]


def test_startup_check_update_ignores_non_available_result(monkeypatch) -> None:
    controller, _fake_config, _home, _overlay, _window = make_controller(monkeypatch)
    prompts = []
    callbacks = []
    cast(Any, controller).prompt_update = prompts.append
    monkeypatch.setattr(main_controller, "check_async", lambda parent, callback: callbacks.append(callback))

    controller.startup_check_update()
    callbacks[0](main_controller.CheckResult(status="up_to_date"))

    assert prompts == []
