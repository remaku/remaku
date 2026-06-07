"""Application entry point for the Remaku desktop app."""

import sys

from PySide6.QtWidgets import QApplication

import remaku.resources.resources_rc  # noqa: F401
from remaku.config.manager import ConfigManager
from remaku.controllers.main_controller import MainController
from remaku.ui.main_window import MainWindow
from remaku.ui.theme import apply_theme


def main() -> None:
    app = QApplication(sys.argv)
    config_manager = ConfigManager()
    config = config_manager.load()

    apply_theme(config.general.theme)

    window = MainWindow(config)
    _controller = MainController(window)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
