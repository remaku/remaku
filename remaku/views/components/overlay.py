from PySide6.QtWidgets import QLabel

from remaku.core.event_bus import event_bus
from remaku.views.components.base_overlay import BaseOverlayWidget, white_icon


class OverlayWidget(BaseOverlayWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self.pause_button = self.make_icon_button("pause", self.tr("Pause"))
        self.pause_button.clicked.connect(event_bus.overlay_pause_toggled.emit)
        self.content_layout.addWidget(self.pause_button)

        self.button = self.make_icon_button("stop", self.tr("Stop"))
        self.button.clicked.connect(event_bus.overlay_toggled.emit)
        self.content_layout.addWidget(self.button)

        self.label = QLabel(self)
        self.label.setStyleSheet("color: white; font-size: 13px;")
        self.content_layout.addWidget(self.label, 1)

    def set_text(self, text: str) -> None:
        self.label.setText(text)
        self.adjustSize()

    def set_paused(self, paused: bool) -> None:
        icon_name = "play" if paused else "pause"
        tooltip = self.tr("Resume") if paused else self.tr("Pause")
        self.pause_button.setIcon(white_icon(icon_name))
        self.pause_button.setToolTip(tooltip)
