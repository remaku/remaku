from PySide6.QtWidgets import QWidget

from remaku.views.components.confirm_dialog import ConfirmDialog
from remaku.views.components.message_dialog import MessageDialog


def show_message_dialog(parent: QWidget, title: str, content: str) -> None:
    dialog = MessageDialog(title, content, parent)
    dialog.exec()


def show_confirm_dialog(parent: QWidget, title: str, content: str, yes_text: str = "OK") -> bool:
    dialog = ConfirmDialog(title, content, parent)
    dialog.yesButton.setText(yes_text)
    return bool(dialog.exec())
