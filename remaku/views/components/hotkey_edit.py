from PySide6.QtCore import QEvent, Qt, QTimer, Signal
from PySide6.QtGui import QKeyEvent, QKeySequence
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import LineEdit, MessageBoxBase, PushButton, SubtitleLabel, TogglePushButton

KEY_CAPTURE_PROPERTY = "remakuKeyboardCapture"
MODIFIERS = ("shift", "ctrl", "win", "alt")


class HotkeyEdit(LineEdit):
    keyCaptured = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setReadOnly(True)
        self.setClearButtonEnabled(False)
        self.setPlaceholderText(self.tr("Press a key"))
        self.setProperty(KEY_CAPTURE_PROPERTY, True)

    def event(self, event) -> bool:
        if not isinstance(event, QKeyEvent):
            return super().event(event)

        if event.type() == QEvent.Type.ShortcutOverride and not self.is_modifier_key(event.key()):
            event.accept()
            return True

        if event.type() == QEvent.Type.KeyPress and self.is_focus_navigation_key(event.key()):
            self.capture_event_key(event)
            QTimer.singleShot(0, self.setFocus)
            return True

        return super().event(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        self.capture_event_key(event)

    def focusNextPrevChild(self, next_child: bool) -> bool:
        return False

    def capture_event_key(self, event: QKeyEvent) -> None:
        key = event.key()

        if self.is_modifier_key(key):
            return

        key_name = QKeySequence(key).toString().lower()
        key_name = {
            "backtab": "tab",
            "return": "enter",
            "del": "delete",
            "pgdown": "pagedown",
            "pgup": "pageup",
            "ins": "insert",
            "print": "printscreen",
        }.get(key_name, key_name)

        self.setText(key_name)
        self.keyCaptured.emit(key_name)

    def is_modifier_key(self, key: int) -> bool:
        return key in (
            Qt.Key.Key_Shift,
            Qt.Key.Key_Control,
            Qt.Key.Key_Alt,
            Qt.Key.Key_Meta,
        )

    def is_focus_navigation_key(self, key: int) -> bool:
        return key in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab)


class HotkeyPicker(QWidget):
    textChanged = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.modifier_buttons: dict[str, TogglePushButton] = {}
        self.key = ""
        self.setProperty(KEY_CAPTURE_PROPERTY, True)
        self.init_ui()

    def init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        modifier_row = QHBoxLayout()
        modifier_row.setContentsMargins(0, 0, 0, 0)
        modifier_row.setSpacing(6)

        labels = {
            "shift": self.tr("SHIFT"),
            "ctrl": self.tr("CTRL"),
            "win": self.tr("WIN"),
            "alt": self.tr("ALT"),
        }

        for modifier in MODIFIERS:
            button = TogglePushButton(labels[modifier], self)
            button.toggled.connect(lambda checked, modifier=modifier: self.update_text())
            modifier_row.addWidget(button)
            self.modifier_buttons[modifier] = button

        key_row = QHBoxLayout()
        key_row.setContentsMargins(0, 0, 0, 0)
        key_row.setSpacing(6)

        self.key_edit = HotkeyEdit(self)
        self.key_edit.keyCaptured.connect(self.set_key)
        key_row.addWidget(self.key_edit, 1)

        remove_button = PushButton(self.tr("Remove"), self)
        remove_button.clicked.connect(self.clear)
        key_row.addWidget(remove_button)

        layout.addLayout(modifier_row)
        layout.addLayout(key_row)

    def text(self) -> str:
        return self.build_text()

    def setText(self, value: str) -> None:
        parts = [part.strip().lower() for part in value.split("+") if part.strip()]
        key = ""

        for modifier, button in self.modifier_buttons.items():
            button.blockSignals(True)
            button.setChecked(modifier in parts)
            button.blockSignals(False)

        for part in parts:
            if part not in MODIFIERS:
                key = part

        self.key = key
        self.sync_key_edit()

    def clear(self) -> None:
        for button in self.modifier_buttons.values():
            button.blockSignals(True)
            button.setChecked(False)
            button.blockSignals(False)

        self.key = ""
        self.sync_key_edit()
        self.textChanged.emit("")

    def set_key(self, key: str) -> None:
        self.key = key

        if not key:
            self.sync_key_edit()
            self.textChanged.emit("")
            return

        self.sync_key_edit()
        self.textChanged.emit(self.build_text())

    def update_text(self) -> None:
        self.sync_key_edit()
        self.textChanged.emit(self.build_text())

    def build_text(self) -> str:
        parts = [modifier for modifier in MODIFIERS if self.modifier_buttons[modifier].isChecked()]

        if self.key:
            parts.append(self.key)

        return "+".join(parts)

    def sync_key_edit(self) -> None:
        self.key_edit.blockSignals(True)
        self.key_edit.setText(self.build_text())
        self.key_edit.blockSignals(False)


class HotkeyPickerDialog(MessageBoxBase):
    def __init__(self, value: str, parent=None):
        super().__init__(parent)

        self.title_label = SubtitleLabel(self.tr("Select a hotkey"), self)
        self.picker = HotkeyPicker(self)
        self.picker.setText(value)

        self.viewLayout.addWidget(self.title_label)
        self.viewLayout.addSpacing(4)
        self.viewLayout.addWidget(self.picker)
        self.yesButton.setText(self.tr("OK"))
        self.cancelButton.setText(self.tr("Cancel"))

    def text(self) -> str:
        return self.picker.text()


class HotkeyInput(QWidget):
    textChanged = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.value = ""
        self.setProperty(KEY_CAPTURE_PROPERTY, True)
        self.init_ui()

    def init_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.select_button = PushButton(self.tr("Select a hotkey"), self)
        self.select_button.setProperty(KEY_CAPTURE_PROPERTY, True)
        self.select_button.clicked.connect(self.open_picker)
        layout.addWidget(self.select_button)

    def text(self) -> str:
        return self.value

    def setText(self, value: str) -> None:
        self.set_value(value, emit=False)

    def clear(self) -> None:
        self.set_value("", emit=True)

    def set_value(self, value: str, *, emit: bool) -> None:
        normalized = value.strip().lower()
        self.value = normalized

        self.select_button.setText(normalized or self.tr("Select a hotkey"))

        if emit:
            self.textChanged.emit(normalized)

    def open_picker(self) -> None:
        dialog = HotkeyPickerDialog(self.value, self.window())

        if dialog.exec():
            self.set_value(dialog.text(), emit=True)
