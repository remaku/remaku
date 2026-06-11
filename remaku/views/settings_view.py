from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, CardWidget, CheckBox, ComboBox, LineEdit, ScrollArea, StrongBodyLabel, TitleLabel

from remaku.models.config_model import config_model


class SettingsView(ScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.widgets: dict[str, CheckBox | ComboBox | LineEdit] = {}

        self.init_ui()

    def init_ui(self):
        self.setObjectName("settings")

        self.setWidgetResizable(True)
        self.setFrameShape(ScrollArea.Shape.NoFrame)
        self.setStyleSheet("background: transparent;")

        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(16, 16, 16, 32)
        self.content_layout.setSpacing(4)
        self.content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        title = TitleLabel(self.tr("Settings"), self.content_widget)
        title.setContentsMargins(0, 0, 0, 12)
        self.content_layout.addWidget(title)

        self.add_section(self.tr("General"))
        self.add_checkbox("general.always_on_top", self.tr("Always on Top"), config_model.config.general.always_on_top)
        self.add_checkbox(
            "general.overlay_enabled", self.tr("Show Status Overlay"), config_model.config.general.overlay_enabled
        )
        self.add_checkbox(
            "general.check_update_on_startup",
            self.tr("Check for updates on startup"),
            config_model.config.general.check_update_on_startup,
        )
        self.add_dropdown(
            "general.update_channel",
            self.tr("Update Channel"),
            config_model.config.general.update_channel,
            [(self.tr("Stable"), "stable"), (self.tr("Beta"), "beta")],
        )
        self.add_dropdown(
            "general.theme",
            self.tr("Theme"),
            config_model.config.general.theme,
            [(self.tr("System"), "system"), (self.tr("Dark"), "dark"), (self.tr("Light"), "light")],
        )
        self.add_dropdown(
            "general.language",
            self.tr("Language"),
            config_model.config.general.language,
            [(self.tr("System"), "system"), ("English", "en_US"), ("繁體中文", "zh_TW"), ("简体中文", "zh_CN")],
        )

        self.add_section(self.tr("Capture"))
        self.add_text_input("capture.fps", self.tr("FPS"), str(config_model.config.capture.fps))

        self.add_section(self.tr("Input"))
        self.add_text_input("input.jitter_ms", self.tr("Jitter (ms)"), str(config_model.config.input.jitter_ms))

        self.setWidget(self.content_widget)

    def add_section(self, title: str) -> None:
        label = StrongBodyLabel(title, self.content_widget)
        label.setContentsMargins(0, 12, 0, 4)
        self.content_layout.addWidget(label)

    def add_checkbox(self, key: str, label: str, checked: bool = False) -> None:
        card = CardWidget()
        layout = QHBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        checkbox = CheckBox(label)
        checkbox.setChecked(checked)
        layout.addWidget(checkbox)
        self.content_layout.addWidget(card)
        self.widgets[key] = checkbox

    def add_dropdown(self, key: str, label: str, value: str, options: list[tuple[str, str]]) -> None:
        card = CardWidget()
        layout = QHBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)

        layout.addWidget(BodyLabel(label))
        layout.addStretch(1)

        combo = ComboBox()

        for option_label, option_value in options:
            combo.addItem(self.tr(option_label), userData=option_value)

        index = combo.findData(value)

        if index >= 0:
            combo.setCurrentIndex(index)

        layout.addWidget(combo)

        self.content_layout.addWidget(card)
        self.widgets[key] = combo

    def add_text_input(self, key: str, label: str, value: str) -> None:
        card = CardWidget()
        layout = QHBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)

        layout.addWidget(BodyLabel(label))
        layout.addStretch(1)

        edit = LineEdit()
        edit.setText(value)
        layout.addWidget(edit)

        self.content_layout.addWidget(card)
        self.widgets[key] = edit
