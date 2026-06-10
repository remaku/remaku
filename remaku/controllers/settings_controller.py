from PySide6.QtCore import QObject, Qt
from qfluentwidgets import CheckBox, ComboBox, LineEdit

from remaku.core.event_bus import event_bus
from remaku.models.config_model import config_model
from remaku.theme import apply_theme
from remaku.views.main_window import MainWindow
from remaku.views.settings_view import SettingsView


class SettingsController(QObject):
    def __init__(self, view: SettingsView, main_window: MainWindow):
        super().__init__()

        self.view = view
        self.main_window = main_window

        for key, widget in self.view.widgets.items():
            if isinstance(widget, CheckBox):
                widget.checkStateChanged.connect(lambda state, k=key: self.on_checkbox_changed(k, state))

            elif isinstance(widget, ComboBox):
                widget.currentIndexChanged.connect(lambda index, k=key: self.on_combo_changed(k))

            elif isinstance(widget, LineEdit):
                widget.editingFinished.connect(lambda k=key: self.on_text_changed(k))

    def on_checkbox_changed(self, key: str, state: Qt.CheckState) -> None:
        value = state == Qt.CheckState.Checked
        self.apply_setting(key, value)

    def on_combo_changed(self, key: str) -> None:
        widget = self.view.widgets.get(key)
        if widget is None:
            return

        assert isinstance(widget, ComboBox)
        value = widget.currentData()
        self.apply_setting(key, value)

    def on_text_changed(self, key: str) -> None:
        widget = self.view.widgets.get(key)
        if widget is None:
            return

        assert isinstance(widget, LineEdit)
        text = widget.text().strip()
        value = self.validate_int(key, text)

        if value is None:
            self.restore_text_value(key, widget)
            return

        self.apply_setting(key, value)

    def validate_int(self, key: str, text: str) -> int | None:
        try:
            value = int(text)
        except ValueError:
            return None

        if key == "capture.fps" and value <= 0:
            return None

        if key == "input.jitter_ms" and value < 0:
            return None

        return value

    def restore_text_value(self, key: str, widget: LineEdit) -> None:
        parts = key.split(".", 1)
        section_name = parts[0]
        attr_name = parts[1]

        section = getattr(config_model.config, section_name)
        current_value = getattr(section, attr_name)
        widget.setText(str(current_value))

    def apply_setting(self, key: str, value: object) -> None:
        parts = key.split(".", 1)
        section_name = parts[0]
        attr_name = parts[1]

        section = getattr(config_model.config, section_name)
        setattr(section, attr_name, value)
        config_model.save()

        if key == "general.always_on_top":
            self.main_window.set_always_on_top(bool(value))

        elif key == "general.theme":
            apply_theme(str(value))

        elif key == "general.overlay_enabled":
            event_bus.settings_changed.emit()
