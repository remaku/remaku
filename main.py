import sys

from PySide6.QtWidgets import QApplication

import remaku.resources.resources_rc  # noqa: F401
from remaku.controllers.main_controller import MainController
from remaku.models.config_model import config_model
from remaku.models.macro_model import MacroModel
from remaku.services.migration import migrate_legacy_templates
from remaku.theme import apply_theme
from remaku.views.main_window import MainWindow


def main():
    app = QApplication(sys.argv)

    macro_model = MacroModel()

    if not config_model.config.general.templates_migrated:
        migrate_legacy_templates(macro_model)
        config_model.config.general.templates_migrated = True
        config_model.save()

    apply_theme(config_model.config.general.theme)

    window = MainWindow()
    _controller = MainController(window, macro_model)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
