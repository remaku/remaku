from remaku.controllers.home_controller import HomeController
from remaku.models.config_model import AppConfig
from remaku.views.main_window import MainWindow


class MainController:
    def __init__(self, main_window: MainWindow, macro_model: MacroModel):
        self.main_window = main_window
        self.macro_model = macro_model

        self.main_window.set_always_on_top(config_model.config.general.always_on_top)

        event_bus.switch_page_requested.connect(self.switch_page)
        event_bus.check_updates_requested.connect(self.check_updates)
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
                    self.main_window.tr("Up to date"),
                    self.main_window.tr("You are already using the latest version."),
                )
                return

            show_message_dialog(
                self.main_window,
                self.main_window.tr("Update check failed"),
                result.error or self.main_window.tr("Unable to check for updates."),
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
