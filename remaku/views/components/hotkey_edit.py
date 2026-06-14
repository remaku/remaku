from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent, QKeySequence
from qfluentwidgets import LineEdit


class HotkeyEdit(LineEdit):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setReadOnly(True)
        self.setClearButtonEnabled(True)
        self.setPlaceholderText(self.tr("Press a hotkey"))

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()

        if key in (
            Qt.Key.Key_Shift,
            Qt.Key.Key_Control,
            Qt.Key.Key_Alt,
            Qt.Key.Key_Meta,
        ):
            return

        parts: list[str] = []
        mods = event.modifiers()

        if mods & Qt.KeyboardModifier.ControlModifier:
            parts.append("ctrl")
        if mods & Qt.KeyboardModifier.AltModifier:
            parts.append("alt")
        if mods & Qt.KeyboardModifier.ShiftModifier:
            parts.append("shift")

        key_name = QKeySequence(key).toString().lower()
        parts.append(key_name)

        self.setText("+".join(parts))
