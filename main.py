import contextlib
import platform
import sys

from loguru import logger
from PySide6.QtCore import QTimer, QTranslator
from PySide6.QtWidgets import QApplication

import remaku.resources.resources_rc  # noqa: F401
from remaku.controllers.main_controller import MainController
from remaku.core.i18n import SUPPORTED_TRANSLATOR_LANGUAGES, resolve_language
from remaku.models.config_model import config_model
from remaku.models.macro_model import MacroModel
from remaku.paths import log_dir
from remaku.services.migration import migrate_legacy_templates
from remaku.services.updater import UpdateInfo
from remaku.theme import apply_theme
from remaku.version import __version__
from remaku.views.components.update_dialog import UpdateDialog
from remaku.views.main_window import MainWindow

active_translator: QTranslator | None = None


def setup_logging() -> None:
    logs_path = log_dir()
    logs_path.mkdir(parents=True, exist_ok=True)

    log_fmt = "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<7} | {thread.name}:{module}:{line} | {message}"

    logger.remove()
    logger.add(logs_path / "remaku.log", format=log_fmt, rotation="2 MB", retention=5, enqueue=True)

    if sys.stderr:
        logger.add(sys.stderr, format=log_fmt, level="DEBUG")

    sys.excepthook = lambda *args: logger.opt(exception=args).critical("Uncaught exception")


def main():
    setup_logging()
    logger.info(
        "Starting Remaku v{} | Python {} | {} {}",
        __version__,
        sys.version.split()[0],
        platform.system(),
        platform.version(),
    )

    app = QApplication(sys.argv)
    load_translator(app)

    macro_model = MacroModel()

    if not config_model.config.general.templates_migrated:
        migrate_legacy_templates(macro_model)
        config_model.config.general.templates_migrated = True
        config_model.save()

    apply_theme(config_model.config.general.theme)

    window = MainWindow()
    _controller = MainController(window, macro_model)
    window.show()

    if "--preview-update" in sys.argv:
        QTimer.singleShot(500, lambda: preview_update(window))

    sys.exit(app.exec())


def load_translator(app: QApplication) -> None:
    global active_translator

    language = resolve_language(config_model.config.general.language)

    if language not in SUPPORTED_TRANSLATOR_LANGUAGES:
        return

    translator = QTranslator(app)
    if not translator.load(f":/remaku/locales/{language}.qm"):
        return

    app.installTranslator(translator)
    active_translator = translator


def preview_update(window):
    info = UpdateInfo(
        tag="v99.0.0",
        version=(99, 0, 0, 999999),
        body="<!-- lang:en -->\n### Added\n- Example feature\n<!-- lang:zh_TW -->\n### 新增\n- 範例功能",
        installer_url="",
        release_url="https://github.com/remaku/remaku/releases/tag/v99.0.0",
    )
    dialog = UpdateDialog(window, info)
    dialog.show()

    QTimer.singleShot(2000, lambda: preview_download_phase(dialog))


def preview_download_phase(dialog: UpdateDialog):
    dialog.phase = dialog.PHASE_DOWNLOAD
    dialog.skip_button.setEnabled(False)
    dialog.cancelButton.setEnabled(False)
    dialog.yesButton.setText("Cancel")
    with contextlib.suppress(RuntimeError):
        dialog.yesButton.clicked.disconnect()
    dialog.yesButton.clicked.connect(dialog.handle_cancel_download)
    dialog.progress.show()
    dialog.progress.setValue(34)
    dialog.status_label.setText("6.7 MB / 20.0 MB")


if __name__ == "__main__":
    main()
