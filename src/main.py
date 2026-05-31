"""Application entry point.

Initializes configuration and launches the main window.
"""

import os
import platform
import sys

from loguru import logger
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication
from qfluentwidgets import Theme, setTheme

import config as cfg
import i18n
from main_window import MainWindow
from version import __version__, root


def main() -> None:
    logger.remove()

    log_fmt = "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<7} | {thread.name}:{module}:{line} | {message}"
    log_path = cfg.logs_dir() / "remaku.log"

    logger.add(log_path, format=log_fmt, rotation="2 MB", retention=5, enqueue=True)

    if sys.stderr:
        logger.add(sys.stderr, format=log_fmt, level="DEBUG")

    sys.excepthook = lambda *args: logger.opt(exception=args).critical("Uncaught exception")

    logger.info(
        "Starting Remaku v{} | Python {} | {} {}",
        __version__,
        sys.version.split()[0],
        platform.system(),
        platform.version(),
    )

    os.environ.setdefault("QT_QPA_PLATFORM", "windows:fontengine=directwrite")
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(str(root / "icon.ico")))

    font = QFont("Microsoft JhengHei UI", 9)
    font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)

    app.setFont(font)

    conf = cfg.load()

    i18n.load(conf.general.language)

    theme_map = {"light": Theme.LIGHT, "dark": Theme.DARK, "system": Theme.AUTO}
    setTheme(theme_map.get(conf.general.theme, Theme.AUTO))

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
