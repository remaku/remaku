from PySide6.QtCore import QObject, QTimer

from remaku.controllers.home_controller import HomeController
from remaku.controllers.settings_controller import SettingsController
from remaku.core.dialogs import show_message_dialog
from remaku.core.event_bus import event_bus
from remaku.models.config_model import config_model
from remaku.models.macro_model import MacroModel
from remaku.services.updater import CheckResult, UpdateInfo, check_async
from remaku.views.components.overlay import OverlayWidget
from remaku.views.components.update_dialog import UpdateDialog
from remaku.views.main_window import MainWindow


class MainController(QObject):
    def __init__(self, main_window: MainWindow, macro_model: MacroModel):
        super().__init__(main_window)

        self.main_window = main_window
        self.macro_model = macro_model

        self.main_window.set_always_on_top(config_model.config.general.always_on_top)

        self.home_controller = HomeController(
            self.main_window.home_view,
            self.macro_model,
        )

        self.settings_controller = SettingsController(self.main_window.settings_view, self.main_window)

        event_bus.switch_page_requested.connect(self.switch_page)
        event_bus.check_updates_requested.connect(self.check_updates)
        event_bus.settings_changed.connect(self.apply_overlay_settings)
        event_bus.overlay_position_changed.connect(self.update_overlay_position)

        self.overlay = OverlayWidget()
        self.overlay_timer = QTimer(self.main_window)
        self.overlay_timer.setInterval(200)
        self.overlay_timer.timeout.connect(self.refresh_overlay)
        self.overlay_timer.start()
        self.apply_overlay_settings()
        self.refresh_overlay()

        if config_model.config.general.check_update_on_startup:
            QTimer.singleShot(1000, self.startup_check_update)

    def apply_overlay_settings(self) -> None:
        config = config_model.config.general
        self.overlay.move(*config.overlay_position)

    def update_overlay_position(self, x: int, y: int) -> None:
        config_model.config.general.overlay_position = (x, y)
        config_model.save()

    def translated_status_state(self, state: str) -> str:
        labels = {
            "waiting_window": self.tr("Open the selected window to continue"),
            "waiting_foreground": self.tr("Switch back to the selected window to continue"),
        }

        return labels.get(state, state)

    def refresh_overlay(self) -> None:
        runner = self.home_controller.current_runner
        if runner is None:
            self.overlay.hide()
            return

        status = runner.get_status()

        if not status.running:
            self.overlay.hide()
            return

        self.home_controller.highlight_current_step()

        label = runner.label
        elapsed_prefix = ""
        if runner.start_time is not None:
            elapsed = int(status.elapsed_s)
            elapsed_prefix = f"{elapsed // 60:02d}:{elapsed % 60:02d} | "

        message = self.tr("Running: {label}").format(label=label)
        message = f"{elapsed_prefix}{message}"

        if status.state and status.state not in ("-", "running"):
            message = f"{elapsed_prefix}{self.translated_status_state(status.state)}"
        else:
            if status.progress and status.repeat_total:
                loop_progress = self.tr("Loop {progress}/{total}").format(
                    progress=status.progress,
                    total=status.repeat_total,
                )
                message += f" | {loop_progress}"

            current = getattr(runner, "current_step", None)
            if current is not None:
                summary = self.home_controller.describe_step(current)
                message += f" | {summary}"

            if status.score > 0:
                match_label = runner.template_label(status.match_id) if status.match_id else ""
                score_text = f"{int(status.score * 100)}%"
                message += f" | {match_label} {score_text}" if match_label else f" | {score_text}"

        self.overlay.set_text(message)

        if config_model.config.general.overlay_enabled:
            self.overlay.show()

    def switch_page(self, page: str):
        match page:
            case "settings":
                self.main_window.switchTo(self.main_window.settings_view)
            case _:
                return

    def prompt_update(self, info: UpdateInfo) -> None:
        dialog = UpdateDialog(self.main_window, info)
        dialog.show()

    def check_updates(self) -> None:
        def callback(result: CheckResult) -> None:
            if result.status == "available" and result.info is not None:
                self.prompt_update(result.info)
                return

            if result.status == "up_to_date":
                show_message_dialog(
                    self.main_window,
                    self.tr("Up to date"),
                    self.tr("You are already using the latest version."),
                )
                return

            show_message_dialog(
                self.main_window,
                self.tr("Update check failed"),
                result.error or self.tr("Unable to check for updates."),
            )

        check_async(self.main_window, callback)

    def startup_check_update(self) -> None:
        def callback(result: CheckResult) -> None:
            if result.status != "available" or result.info is None:
                return

            if result.info.tag == config_model.config.general.skipped_version:
                return

            self.prompt_update(result.info)

        check_async(self.main_window, callback)
