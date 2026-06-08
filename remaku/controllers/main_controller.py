from remaku.controllers.home_controller import HomeController
from remaku.models.config_model import AppConfig
from remaku.views.main_window import MainWindow


class MainController:
    def __init__(self, main_window: MainWindow, config: AppConfig):
        self.main_window = main_window

        self.main_window.set_always_on_top(config.general.always_on_top)

        self.home_controller = HomeController(self.main_window.home_view)
