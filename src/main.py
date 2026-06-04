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

    if "--preview-update" in sys.argv:
        from updater import UpdateDialog, UpdateInfo

        info = UpdateInfo(
            tag="v99.0.0",
            version=(99, 0, 0, 999999),
            body="<!-- lang:en -->\n### Added\n- Example feature\n<!-- lang:zh_tw -->\n### 新增\n- 範例功能\n<!-- lang:zh_cn -->\n### 新增\n- 示例功能",
            installer_url="https://example.com/fake.exe",
            release_url="https://github.com/remaku/remaku/releases/tag/v99.0.0",
        )
        dialog = UpdateDialog(window, info)
        dialog.show()
        dialog.enter_download_phase()
        if dialog.download:
            dialog.download.cancel()
        dialog.progress.show()
        dialog.progress.setValue(35)
        dialog.status_lbl.setText("6.7 MB / 20.0 MB")

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
