from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QResizeEvent
from PySide6.QtWidgets import QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, ComboBox, LineEdit, PushButton

from remaku.core.event_bus import event_bus
from remaku.models.macro_model import DEFAULT_TEMPLATE_MATCH_MODE, Macro
from remaku.paths import template_path


class TemplateEditor(QWidget):
    rename_requested = Signal(str, str)
    add_branch_step_requested = Signal(str)
    resolution_changed = Signal(str, str, str)

    def __init__(self, macro: Macro, template_id: str, parent=None) -> None:
        super().__init__(parent)

        self.macro = macro
        self.template_id = template_id
        self.template_info = self.macro.templates.get(template_id)
        self.template_label = self.template_info.label if self.template_info else ""
        self.capture_width = self.template_info.capture_width if self.template_info else 0
        self.capture_height = self.template_info.capture_height if self.template_info else 0
        self.match_mode = self.template_info.match_mode if self.template_info else DEFAULT_TEMPLATE_MATCH_MODE
        self.original_pixmap: QPixmap | None = None
        self.preview_label: BodyLabel | None = None
        self.init_ui()

    def init_ui(self) -> None:
        self.content_layout = QVBoxLayout(self)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(12)

        self.add_field_label(self.tr("Template"))
        self.add_template_preview(self.template_id)
        self.add_text_input(value=self.template_label, field_key="label")
        self.add_match_mode_input()

        capture_screen_button = PushButton(self.tr("Capture Screen"), self)
        capture_screen_button.clicked.connect(lambda: event_bus.template_capture_requested.emit(self.template_id))
        self.content_layout.addWidget(capture_screen_button)

        pick_image_button = PushButton(self.tr("Pick Image"), self)
        pick_image_button.clicked.connect(lambda: event_bus.template_pick_requested.emit(self.template_id))
        self.content_layout.addWidget(pick_image_button)

        delete_template_button = PushButton(self.tr("Delete Template"), self)
        delete_template_button.clicked.connect(lambda: event_bus.template_delete_requested.emit(self.template_id))
        self.content_layout.addWidget(delete_template_button)

        self.add_text_input(self.tr("Capture Width"), str(self.capture_width), field_key="capture_width")
        self.add_text_input(self.tr("Capture Height"), str(self.capture_height), field_key="capture_height")

    def add_match_mode_input(self) -> None:
        self.add_field_label(self.tr("Match Mode"))

        combo = ComboBox(self)
        combo.addItem(self.tr("Fast: grayscale"), userData="grayscale")
        combo.addItem(self.tr("Precise: color"), userData="color")

        selected_index = combo.findData(self.match_mode)
        combo.setCurrentIndex(max(0, selected_index))
        combo.currentIndexChanged.connect(
            lambda _index, tid=self.template_id, w=combo: event_bus.template_meta_changed.emit(
                tid,
                "match_mode",
                str(w.currentData()),
            )
        )

        self.content_layout.addWidget(combo)

    def add_field_label(self, text: str) -> None:
        label = BodyLabel(text, self)
        self.content_layout.addWidget(label)

    def add_text_input(self, label: str | None = None, value: str = "", field_key: str = "") -> None:
        if label is not None:
            self.add_field_label(label)

        edit = LineEdit(self)
        edit.setText(value)

        if field_key:
            edit.editingFinished.connect(
                lambda fk=field_key, tid=self.template_id, w=edit: event_bus.template_meta_changed.emit(
                    tid, fk, w.text()
                )
            )

        self.content_layout.addWidget(edit)

    def add_template_preview(self, template_id: str) -> None:
        self.original_pixmap = QPixmap(template_path(self.macro.meta.id, template_id)) if template_id else QPixmap()

        self.preview_label = BodyLabel(self)
        self.preview_label.setMinimumWidth(1)
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.update_preview()

        self.content_layout.addWidget(self.preview_label)

    def update_preview(self) -> None:
        if self.preview_label is None:
            return

        if self.original_pixmap and not self.original_pixmap.isNull():
            target_width = max(1, self.width())
            scaled = self.original_pixmap.scaled(
                target_width,
                self.height(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.preview_label.setPixmap(scaled)
        else:
            self.preview_label.setText(self.tr("No template available"))
            self.preview_label.setFixedHeight(120)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)

        self.update_preview()
