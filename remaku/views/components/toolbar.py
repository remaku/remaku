from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QHBoxLayout, QWidget
from qfluentwidgets import Action, RoundMenu, TransparentPushButton, TransparentToolButton

from remaku.core.event_bus import event_bus
from remaku.resources.icon import RemakuIcon
from remaku.views.components.step_menu import show_step_menu


class Toolbar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        event_bus.macro_running_changed.connect(self.handle_macro_running_changed)
        event_bus.macro_recording_changed.connect(self.handle_macro_recording_changed)
        event_bus.show_toolbar_step_menu_requested.connect(self.show_add_menu)

        self.init_ui()

    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.file_menu_button = TransparentPushButton(self.tr("File"), self)
        self.file_menu_button.clicked.connect(self.show_file_menu)
        layout.addWidget(self.file_menu_button)

        self.edit_menu_button = TransparentPushButton(self.tr("Edit"), self)
        self.edit_menu_button.clicked.connect(self.show_edit_menu)
        layout.addWidget(self.edit_menu_button)

        self.help_menu_button = TransparentPushButton(self.tr("Help"), self)
        self.help_menu_button.clicked.connect(self.show_help_menu)
        layout.addWidget(self.help_menu_button)

        self.run_button = TransparentPushButton(RemakuIcon.PLAY, self.tr("Run"), self)
        self.run_button.clicked.connect(lambda: event_bus.action_triggered.emit("run"))
        layout.addWidget(self.run_button)

        self.record_button = TransparentPushButton(RemakuIcon.KEYBOARD, self.tr("Record"), self)
        self.record_button.clicked.connect(lambda: event_bus.action_triggered.emit("record"))
        layout.addWidget(self.record_button)

        self.add_button = TransparentPushButton(RemakuIcon.PLUS, self.tr("Add"), self)
        self.add_button.clicked.connect(self.show_add_menu)
        layout.addWidget(self.add_button)

        self.delete_button = TransparentToolButton(RemakuIcon.TRASH, self)
        self.delete_button.clicked.connect(lambda: event_bus.action_triggered.emit("delete_step"))
        layout.addWidget(self.delete_button)

        self.move_up_button = TransparentToolButton(RemakuIcon.ARROW_UP, self)
        self.move_up_button.clicked.connect(lambda: event_bus.action_triggered.emit("move_up"))
        layout.addWidget(self.move_up_button)

        self.move_down_button = TransparentToolButton(RemakuIcon.ARROW_DOWN, self)
        self.move_down_button.clicked.connect(lambda: event_bus.action_triggered.emit("move_down"))
        layout.addWidget(self.move_down_button)

        self.undo_button = TransparentToolButton(RemakuIcon.UNDO, self)
        self.undo_button.clicked.connect(lambda: event_bus.action_triggered.emit("undo"))
        layout.addWidget(self.undo_button)

        self.redo_button = TransparentToolButton(RemakuIcon.REDO, self)
        self.redo_button.clicked.connect(lambda: event_bus.action_triggered.emit("redo"))
        layout.addWidget(self.redo_button)

        layout.addStretch()

    def popup_menu(self, button, items):
        menu = RoundMenu(parent=self)

        for item in items:
            if item.get("separator"):
                menu.addSeparator()
                continue

            action = Action(item["label"], self)

            if "shortcut" in item:
                action.setShortcut(QKeySequence(item["shortcut"]))

            action.triggered.connect(lambda checked, item_id=item["id"]: event_bus.action_triggered.emit(item_id))

            menu.addAction(action)

        menu.exec(button.mapToGlobal(button.rect().bottomLeft()))

    def show_add_menu(self) -> None:
        show_step_menu(self, self.add_button, lambda step_type: event_bus.step_add_requested.emit(step_type))

    def show_file_menu(self):
        self.popup_menu(
            self.file_menu_button,
            [
                {"id": "new_macro", "label": self.tr("New Macro"), "shortcut": "Ctrl+N"},
                {"id": "duplicate_macro", "label": self.tr("Duplicate Macro")},
                {"id": "record", "label": self.tr("Record Macro")},
                {"separator": True},
                {"id": "import_macro", "label": self.tr("Import Macro")},
                {"id": "export_macro", "label": self.tr("Export Macro")},
                {"id": "open_macro_folder", "label": self.tr("Open Macro Folder")},
                {"separator": True},
                {"id": "settings", "label": self.tr("Settings"), "shortcut": "Ctrl+,"},
                {"separator": True},
                {"id": "quit", "label": self.tr("Quit")},
            ],
        )

    def show_edit_menu(self):
        self.popup_menu(
            self.edit_menu_button,
            [
                {"id": "undo", "label": self.tr("Undo"), "shortcut": "Ctrl+Z"},
                {"id": "redo", "label": self.tr("Redo"), "shortcut": "Ctrl+Y"},
                {"separator": True},
                {"id": "cut", "label": self.tr("Cut"), "shortcut": "Ctrl+X"},
                {"id": "copy", "label": self.tr("Copy"), "shortcut": "Ctrl+C"},
                {"id": "paste", "label": self.tr("Paste"), "shortcut": "Ctrl+V"},
                {"separator": True},
                {"id": "record", "label": self.tr("Record Macro")},
                {"separator": True},
                {"id": "add_step", "label": self.tr("Add Step"), "shortcut": "Ctrl+Shift+N"},
                {"id": "duplicate_step", "label": self.tr("Duplicate Step"), "shortcut": "Ctrl+D"},
                {"id": "delete_step", "label": self.tr("Delete Step"), "shortcut": "Del"},
                {"separator": True},
                {"id": "move_up", "label": self.tr("Move Up"), "shortcut": "Alt+Up"},
                {"id": "move_down", "label": self.tr("Move Down"), "shortcut": "Alt+Down"},
            ],
        )

    def show_help_menu(self):
        self.popup_menu(
            self.help_menu_button,
            [
                {"id": "about", "label": self.tr("About")},
                {"id": "support_author", "label": self.tr("Support the Author")},
                {"id": "check_updates", "label": self.tr("Check for Updates")},
                {"separator": True},
                {"id": "open_logs", "label": self.tr("Open Logs")},
            ],
        )

    def handle_macro_running_changed(self, is_running: bool) -> None:
        self.run_button.setText(self.tr("Stop") if is_running else self.tr("Run"))
        self.run_button.setIcon(RemakuIcon.PAUSE if is_running else RemakuIcon.PLAY)
        self.record_button.setDisabled(is_running)

    def handle_macro_recording_changed(self, is_recording: bool) -> None:
        self.record_button.setText(self.tr("Recording") if is_recording else self.tr("Record"))
        self.record_button.setDisabled(is_recording)
        self.run_button.setDisabled(is_recording)
