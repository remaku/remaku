from PySide6.QtCore import Signal
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QHBoxLayout, QWidget
from qfluentwidgets import Action, RoundMenu, TransparentPushButton, TransparentToolButton

from remaku.resources.icon import RemakuIcon


class Toolbar(QWidget):
    action_triggered = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.init_ui()

    def init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(6)

        self.file_menu_button = TransparentPushButton(self.tr("File"), self)
        self.file_menu_button.clicked.connect(self.show_file_menu)
        main_layout.addWidget(self.file_menu_button)

        self.edit_menu_button = TransparentPushButton(self.tr("Edit"), self)
        self.edit_menu_button.clicked.connect(self.show_edit_menu)
        main_layout.addWidget(self.edit_menu_button)

        self.help_menu_button = TransparentPushButton(self.tr("Help"), self)
        self.help_menu_button.clicked.connect(self.show_help_menu)
        main_layout.addWidget(self.help_menu_button)

        main_layout.addWidget(TransparentPushButton(RemakuIcon.PLAY, self.tr("Run"), self))
        main_layout.addWidget(TransparentPushButton(RemakuIcon.PLUS, self.tr("Add"), self))
        main_layout.addWidget(TransparentToolButton(RemakuIcon.TRASH, self))
        main_layout.addWidget(TransparentToolButton(RemakuIcon.ARROW_UP, self))
        main_layout.addWidget(TransparentToolButton(RemakuIcon.ARROW_DOWN, self))
        main_layout.addWidget(TransparentToolButton(RemakuIcon.UNDO, self))
        main_layout.addWidget(TransparentToolButton(RemakuIcon.REDO, self))

        main_layout.addStretch()

    def popup_menu(self, button, items):
        menu = RoundMenu(parent=self)

        for item in items:
            if item.get("separator"):
                menu.addSeparator()
                continue

            action = Action(self.tr(item["label"]), self)

            if "shortcut" in item:
                action.setShortcut(QKeySequence(item["shortcut"]))

            action.triggered.connect(lambda checked, item_id=item["id"]: self.action_triggered.emit(item_id))

            self.addAction(action)
            menu.addAction(action)

        menu.exec(button.mapToGlobal(button.rect().bottomLeft()))

    def show_file_menu(self):
        self.popup_menu(
            self.file_menu_button,
            [
                {"id": "new_macro", "label": "New Macro", "shortcut": "Ctrl+N"},
                {"id": "duplicate_macro", "label": "Duplicate Macro"},
                {"separator": True},
                {"id": "import_macro", "label": "Import Macro"},
                {"id": "export_macro", "label": "Export Macro"},
                {"separator": True},
                {"id": "settings", "label": "Settings", "shortcut": "Ctrl+,"},
                {"separator": True},
                {"id": "quit", "label": "Quit"},
            ],
        )

    def show_edit_menu(self):
        self.popup_menu(
            self.edit_menu_button,
            [
                {"id": "undo", "label": "Undo", "shortcut": "Ctrl+Z"},
                {"id": "redo", "label": "Redo", "shortcut": "Ctrl+Y"},
                {"separator": True},
                {"id": "cut", "label": "Cut", "shortcut": "Ctrl+X"},
                {"id": "copy", "label": "Copy", "shortcut": "Ctrl+C"},
                {"id": "paste", "label": "Paste", "shortcut": "Ctrl+V"},
                {"separator": True},
                {"id": "add_step", "label": "Add Step", "shortcut": "Ctrl+Shift+N"},
                {"id": "duplicate_step", "label": "Duplicate Step", "shortcut": "Ctrl+D"},
                {"id": "delete_step", "label": "Delete Step", "shortcut": "Del"},
                {"separator": True},
                {"id": "move_up", "label": "Move Up", "shortcut": "Alt+Up"},
                {"id": "move_down", "label": "Move Down", "shortcut": "Alt+Down"},
            ],
        )

    def show_help_menu(self):
        self.popup_menu(
            self.help_menu_button,
            [
                {"id": "about", "label": "About"},
                {"id": "support_author", "label": "Support the Author"},
                {"id": "check_updates", "label": "Check for Updates"},
                {"separator": True},
                {"id": "open_logs", "label": "Open Logs"},
            ],
        )
