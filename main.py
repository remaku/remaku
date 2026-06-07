import sys

import remaku.resources.resources_rc  # noqa: F401
from PySide6.QtWidgets import QApplication
from remaku.controllers.main_controller import MainController
from remaku.ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)

    window = MainWindow()
    _controller = MainController(window)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
