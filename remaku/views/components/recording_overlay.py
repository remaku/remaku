from collections.abc import Callable

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QLabel, QPushButton

from remaku.core.event_bus import event_bus
from remaku.views.components.base_overlay import BaseOverlayWidget, white_icon


class RecordingOverlay(BaseOverlayWidget):
    def __init__(self, stats_provider: Callable[[], tuple[float, int]], parent=None) -> None:
        super().__init__(parent)

        self.stats_provider = stats_provider
        self.paused = False

        self.status_label = QLabel(self.tr("Recording"), self)
        self.status_label.setStyleSheet("color: white; font-size: 13px;")
        self.content_layout.addWidget(self.status_label)

        self.stats_label = QLabel("00:00 | 0", self)
        self.stats_label.setStyleSheet("color: white; font-size: 13px;")
        self.content_layout.addWidget(self.stats_label)

        self.pause_button = self.make_icon_button("pause", self.tr("Pause"))
        self.pause_button.clicked.connect(lambda: event_bus.action_triggered.emit("record_pause"))
        self.content_layout.addWidget(self.pause_button)

        self.stop_button = self.make_icon_button("stop", self.tr("Stop"))
        self.stop_button.clicked.connect(lambda: event_bus.action_triggered.emit("record_stop"))
        self.content_layout.addWidget(self.stop_button)

        self.cancel_button = QPushButton(self.tr("Cancel"), self)
        self.cancel_button.setToolTip(self.tr("Cancel recording"))
        self.cancel_button.setStyleSheet(
            "QPushButton { background: rgba(255, 255, 255, 40); border: none; border-radius: 4px; "
            "color: white; min-height: 24px; padding: 0 8px; }"
            "QPushButton:hover { background: rgba(255, 255, 255, 80); }"
        )
        self.cancel_button.clicked.connect(lambda: event_bus.action_triggered.emit("record_cancel"))
        self.content_layout.addWidget(self.cancel_button)

        self.timer = QTimer(self)
        self.timer.setInterval(250)
        self.timer.timeout.connect(self.refresh_stats)

    def start(self) -> None:
        self.refresh_stats()
        self.timer.start()
        self.show()
        self.raise_()

    def stop(self) -> None:
        self.timer.stop()
        self.hide()

    def set_paused(self, paused: bool) -> None:
        self.paused = paused
        self.status_label.setText(self.tr("Paused") if paused else self.tr("Recording"))
        self.pause_button.setIcon(white_icon("play" if paused else "pause"))
        self.pause_button.setToolTip(self.tr("Resume") if paused else self.tr("Pause"))

    def refresh_stats(self) -> None:
        elapsed_s, event_count = self.stats_provider()
        elapsed = int(elapsed_s)
        self.stats_label.setText(
            self.tr("{elapsed} | {count} events").format(
                elapsed=f"{elapsed // 60:02d}:{elapsed % 60:02d}",
                count=event_count,
            )
        )
