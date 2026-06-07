from PySide6.QtWidgets import QHBoxLayout, QWidget
from qfluentwidgets import TransparentPushButton, TransparentToolButton
from remaku.resources.icon import RemakuIcon


class Toolbar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        file_menu = TransparentPushButton("File", self)
        layout.addWidget(file_menu)

        edit_menu = TransparentPushButton("Edit", self)
        layout.addWidget(edit_menu)

        help_menu = TransparentPushButton("Help", self)
        layout.addWidget(help_menu)

        run_button = TransparentPushButton(RemakuIcon.PLAY, "Run", self)
        layout.addWidget(run_button)

        add_step_button = TransparentPushButton(RemakuIcon.PLUS, "Add", self)
        layout.addWidget(add_step_button)

        delete_button = TransparentToolButton(RemakuIcon.TRASH, self)
        layout.addWidget(delete_button)

        move_up_button = TransparentToolButton(RemakuIcon.ARROW_UP, self)
        layout.addWidget(move_up_button)

        move_down_button = TransparentToolButton(RemakuIcon.ARROW_DOWN, self)
        layout.addWidget(move_down_button)

        undo_button = TransparentToolButton(RemakuIcon.UNDO, self)
        layout.addWidget(undo_button)

        redo_button = TransparentToolButton(RemakuIcon.REDO, self)
        layout.addWidget(redo_button)

        layout.addStretch()
