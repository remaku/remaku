from remaku.controllers.home_controller import HomeController
from remaku.ui.main_window import MainWindow


class MainController:
    def __init__(self, view: MainWindow):
        self.view = view

        self.home_controller = HomeController(self.view.home_page)
