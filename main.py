import sys

from PySide6.QtWidgets import QApplication

import remaku.resources.resources_rc  # noqa: F401
from remaku.controllers.main_controller import MainController
from remaku.models.config_model import ConfigModel
from remaku.theme import apply_theme
from remaku.views.main_window import MainWindow


def main():
    app = QApplication(sys.argv)

    config_model = ConfigModel()
    config = config_model.load()
    apply_theme(config.general.theme)

    window = MainWindow()
    _controller = MainController(window, config)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
