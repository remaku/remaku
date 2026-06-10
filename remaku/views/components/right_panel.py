import pydirectinput as pdi
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIntValidator, QKeyEvent, QKeySequence
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    CardWidget,
    CheckBox,
    ComboBox,
    IconWidget,
    LineEdit,
    PushButton,
    ScrollArea,
    Slider,
)

from remaku.core import window
from remaku.core.event_bus import event_bus
from remaku.models.macro_model import (
    DelayStep,
    GridNavStep,
    HoldKeyUntilGoneStep,
    IfAnyImageStep,
    IfImageStep,
    KeyStep,
    Macro,
    RepeatStep,
    Step,
    WaitImageStep,
)
from remaku.resources.icon import RemakuIcon
from remaku.views.components.elided_label import ElidedBodyLabel, ElidedSubtitleLabel
from remaku.views.components.step_menu import show_step_menu
from remaku.views.components.template_editor import TemplateEditor

NUMERIC_PROPERTY_KEYS = frozenset(
    {
        "ms",
        "hold_ms",
        "timeout_ms",
        "load_delay_ms",
        "find_timeout_ms",
        "gone_grace_ms",
        "hard_timeout_ms",
        "count",
        "rows",
        "start",
    }
)


class RightPanel(ScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.init_ui()

    def init_ui(self):
        self.setMinimumWidth(220)
        self.setMaximumWidth(350)
        self.setWidgetResizable(True)
        self.setFrameShape(ScrollArea.Shape.NoFrame)
        self.setStyleSheet("background: transparent;")

        self.content_widget = CardWidget()
        self.content_layout = QVBoxLayout(self.content_widget)

        self.content_layout.setContentsMargins(8, 8, 8, 8)
        self.content_layout.setSpacing(12)
        self.content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.setWidget(self.content_widget)
        self.show_macro_properties(None)

    def clear_content(self) -> None:
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)

            if item is None:
                continue

            widget = item.widget()

            if widget is not None:
                widget.deleteLater()

    def show_macro_properties(self, macro: Macro | None) -> None:
        self.clear_content()

        self.add_title_label(self.tr("Macro Properties"))

        if macro is None:
            label = BodyLabel(self.tr("Select a macro to inspect its metadata."), self.content_widget)
            label.setWordWrap(True)

            self.content_layout.addWidget(label)
            return

        self.add_target_window_combo(macro)
        self.add_hotkey_text_input(macro)
        self.add_enabled_checkbox(macro)

    def show_step_properties(self, macro: Macro, title_text: str, step: Step) -> None:
        self.clear_content()

        self.add_title_label(title_text)
        self.add_skip_checkbox(step.skip)
        self.add_note_input(step.note)

        match step:
            case KeyStep():
                self.add_key_input(self.tr("Key"), step.key)
                self.add_text_input(self.tr("Hold (ms)"), str(step.hold_ms), "hold_ms")
            case DelayStep():
                self.add_text_input(self.tr("Duration (ms)"), str(step.ms), "ms")
            case WaitImageStep():
                self.add_template_editor(macro, step.template)
                self.add_slider(self.tr("Threshold"), step.threshold, property_key="threshold")
                self.add_text_input(self.tr("Timeout (ms)"), str(step.timeout_ms), "timeout_ms")
                self.add_dropdown(
                    self.tr("On Timeout"),
                    step.on_timeout,
                    [(self.tr("Stop"), "stop"), (self.tr("Continue"), "continue")],
                    "on_timeout",
                )
            case HoldKeyUntilGoneStep():
                self.add_key_input(self.tr("Key"), step.key)
                self.add_template_editor(macro, step.template)
                self.add_slider(self.tr("Threshold"), step.threshold, property_key="threshold")
                self.add_text_input(self.tr("Load Delay (ms)"), str(step.load_delay_ms), "load_delay_ms")
                self.add_text_input(self.tr("Find Timeout (ms)"), str(step.find_timeout_ms), "find_timeout_ms")
                self.add_text_input(self.tr("Gone Grace (ms)"), str(step.gone_grace_ms), "gone_grace_ms")
                self.add_text_input(self.tr("Hard Timeout (ms)"), str(step.hard_timeout_ms), "hard_timeout_ms")
            case RepeatStep():
                self.add_text_input(self.tr("Count"), str(step.count), "count")
            case IfImageStep():
                self.add_template_editor(macro, step.template)
                self.add_slider(self.tr("Threshold"), step.threshold, property_key="threshold")
                self.add_text_input(self.tr("Timeout (ms)"), str(step.timeout_ms), "timeout_ms")
                # then
                # else
            case IfAnyImageStep():
                self.add_template_list_editor(macro, step.templates)
                self.add_slider(self.tr("Threshold"), step.threshold, property_key="threshold")
                self.add_text_input(self.tr("Timeout (ms)"), str(step.timeout_ms), "timeout_ms")
                self.add_dropdown(
                    self.tr("On Timeout"),
                    step.on_timeout,
                    [(self.tr("Stop"), "stop"), (self.tr("Continue"), "continue")],
                    "on_timeout",
                )
            case GridNavStep():
                self.add_text_input(self.tr("Rows"), str(step.rows), "rows")
                self.add_text_input(self.tr("Start Cell"), str(step.start), "start")

    def show_branch_properties(self, macro: Macro, parent_title: str, branch_title: str, steps: list[Step]) -> None:
        self.clear_content()

        self.add_title_label(branch_title)

        parent_label = ElidedBodyLabel(self.tr("Inside {parent}").format(parent=parent_title), self.content_widget)
        parent_label.setWordWrap(True)
        self.content_layout.addWidget(parent_label)

        add_step_button = PushButton(RemakuIcon.PLUS, self.tr("Add Step"), self.content_widget)
        add_step_button.clicked.connect(
            lambda: show_step_menu(
                self, add_step_button, lambda step_type: event_bus.step_add_requested.emit(step_type)
            )
        )
        self.content_layout.addWidget(add_step_button)

    def handle_add_step_requested(self, step_type: str) -> None:
        event_bus.step_add_requested.emit(step_type)

    def add_title_label(self, text: str) -> None:
        title = ElidedSubtitleLabel(text, self.content_widget)
        self.content_layout.addWidget(title)

    def add_field_label(self, text: str) -> None:
        label = BodyLabel(text, self.content_widget)
        self.content_layout.addWidget(label)

    def add_text_input(self, label: str, value: str, property_key: str = "") -> None:
        self.add_field_label(label)
        field = LineEdit(self.content_widget)
        field.setText(value)

        if property_key:
            if property_key in NUMERIC_PROPERTY_KEYS:
                field.setValidator(QIntValidator(field))
                field.textChanged.connect(lambda text, w=field: w.setError(False))
                field.editingFinished.connect(lambda pk=property_key, w=field: self.commit_numeric_field(pk, w))
            else:
                field.editingFinished.connect(
                    lambda pk=property_key, w=field: event_bus.step_property_changed.emit(pk, w.text())
                )

        self.content_layout.addWidget(field)

    def commit_numeric_field(self, property_key: str, field: LineEdit) -> None:
        text = field.text().strip()

        if not text:
            field.setError(True)
            return

        try:
            int(text)
        except ValueError:
            field.setError(True)
            return

        field.setError(False)
        event_bus.step_property_changed.emit(property_key, text)

    def add_slider(
        self, label: str, value: int | float, min_value: int = 0, max_value: int = 100, property_key: str = ""
    ) -> None:
        percentage = value if isinstance(value, int) else int(value * 100)

        slider_label = BodyLabel(f"{label} ({percentage}%)", self.content_widget)
        self.content_layout.addWidget(slider_label)

        slider = Slider(Qt.Orientation.Horizontal, self.content_widget)
        slider.setRange(min_value, max_value)
        slider.setValue(percentage)

        if property_key:
            slider.valueChanged.connect(lambda val, lbl=slider_label, text=label: lbl.setText(f"{text} ({val}%)"))

            save_timer = QTimer(slider)
            save_timer.setSingleShot(True)
            save_timer.setInterval(200)

            save_timer.timeout.connect(
                lambda pk=property_key, s=slider: event_bus.step_property_changed.emit(pk, str(s.value()))
            )
            slider.valueChanged.connect(lambda: save_timer.start())

        self.content_layout.addWidget(slider)

    def add_dropdown(self, label: str, value: str, options: list[tuple[str, str]], property_key: str = "") -> None:
        self.add_field_label(label)
        combo = ComboBox(self.content_widget)

        for option_label, option_value in options:
            combo.addItem(self.tr(option_label), userData=option_value)

        index = combo.findData(value)

        if index >= 0:
            combo.setCurrentIndex(index)

        if property_key:
            combo.currentIndexChanged.connect(
                lambda index, pk=property_key, c=combo: event_bus.step_property_changed.emit(pk, str(c.currentData()))
            )

        self.content_layout.addWidget(combo)

    def add_target_window_combo(self, macro: Macro) -> None:
        self.add_field_label(self.tr("Target window"))
        target_combo = ComboBox(self.content_widget)
        target_combo.addItem(self.tr("(Use foreground window)"), userData="")

        for title in window.list_visible_windows():
            target_combo.addItem(title, userData=title)

        index = target_combo.findData(macro.meta.target_window)

        if index < 0 and macro.meta.target_window:
            target_combo.addItem(macro.meta.target_window, userData=macro.meta.target_window)
            index = target_combo.count() - 1

        if index >= 0:
            target_combo.setCurrentIndex(index)

        target_combo.currentIndexChanged.connect(
            lambda index, c=target_combo: event_bus.macro_meta_changed.emit("target_window", str(c.currentData()))
        )

        self.content_layout.addWidget(target_combo)

    def add_hotkey_text_input(self, macro: Macro) -> None:
        self.add_field_label(self.tr("Hotkey"))
        hotkey_edit = LineEdit(self.content_widget)
        hotkey_edit.setText(macro.meta.hotkey)
        hotkey_edit.setPlaceholderText(self.tr("Press a hotkey"))
        hotkey_edit.setReadOnly(True)
        hotkey_edit.setClearButtonEnabled(True)

        hotkey_edit.textChanged.connect(
            lambda text: event_bus.macro_meta_changed.emit("hotkey", "") if not text else None
        )
        hotkey_edit.keyPressEvent = lambda e: self.capture_hotkey(e, hotkey_edit)

        self.content_layout.addWidget(hotkey_edit)

    def capture_hotkey(self, event: QKeyEvent, edit: LineEdit) -> None:
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

        hotkey_str = "+".join(parts)
        edit.setText(hotkey_str)
        event_bus.macro_meta_changed.emit("hotkey", hotkey_str)

    def add_key_input(self, label: str, value: str) -> None:
        self.add_field_label(label)
        field = LineEdit(self.content_widget)
        field.setText(value)
        field.setReadOnly(True)
        field.setClearButtonEnabled(True)

        field.textChanged.connect(lambda text: event_bus.step_property_changed.emit("key", "") if not text else None)
        field.keyPressEvent = lambda e: self.capture_key(e, field)

        self.content_layout.addWidget(field)

    def capture_key(self, event: QKeyEvent, edit: LineEdit) -> None:
        key = event.key()

        if key in (
            Qt.Key.Key_Shift,
            Qt.Key.Key_Control,
            Qt.Key.Key_Alt,
            Qt.Key.Key_Meta,
        ):
            return

        key_name = QKeySequence(key).toString().lower()
        key_name = {
            "return": "enter",
            "del": "delete",
            "pgdown": "pagedown",
            "pgup": "pageup",
            "ins": "insert",
            "print": "printscreen",
        }.get(key_name, key_name)

        if key_name not in pdi.KEYBOARD_MAPPING:
            return

        edit.blockSignals(True)
        edit.setText(key_name)
        edit.blockSignals(False)
        event_bus.step_property_changed.emit("key", key_name)

    def add_enabled_checkbox(self, macro: Macro) -> None:
        enabled_checkbox = CheckBox(self.tr("Enabled"), self.content_widget)
        enabled_checkbox.setChecked(macro.meta.enabled)

        enabled_checkbox.checkStateChanged.connect(
            lambda state: event_bus.macro_meta_changed.emit("enabled", str(state == Qt.CheckState.Checked))
        )

        self.content_layout.addWidget(enabled_checkbox)

    def add_skip_checkbox(self, value: bool) -> None:
        skip_checkbox = CheckBox(self.tr("Skip"), self.content_widget)
        skip_checkbox.setChecked(value)

        skip_checkbox.checkStateChanged.connect(
            lambda state: event_bus.step_property_changed.emit("skip", str(state == Qt.CheckState.Checked))
        )

        self.content_layout.addWidget(skip_checkbox)

    def add_note_input(self, value: str) -> None:
        self.add_field_label(self.tr("Note"))
        note_edit = LineEdit(self.content_widget)
        note_edit.setText(value)
        note_edit.setPlaceholderText(self.tr("Add a note for this step"))

        note_edit.editingFinished.connect(lambda w=note_edit: event_bus.step_property_changed.emit("note", w.text()))

        self.content_layout.addWidget(note_edit)

    def add_template_editor(self, macro: Macro, template_id: str) -> None:
        template_editor = TemplateEditor(macro, template_id, self.content_widget)
        self.content_layout.addWidget(template_editor)

    def add_template_list_editor(self, macro: Macro, template_ids: list[str]) -> None:
        for template_id in template_ids:
            self.add_template_card(macro, template_id)

        add_template_button = PushButton(RemakuIcon.PLUS, self.tr("Add Template"), self.content_widget)
        add_template_button.clicked.connect(lambda: event_bus.template_add_requested.emit())
        self.content_layout.addWidget(add_template_button)

    def add_template_card(self, macro: Macro, template_id: str) -> None:
        trigger = QWidget(self.content_widget)
        trigger.setCursor(Qt.CursorShape.PointingHandCursor)
        self.content_layout.addWidget(trigger)

        trigger_layout = QHBoxLayout(trigger)
        trigger_layout.setContentsMargins(0, 6, 0, 6)
        trigger_layout.setSpacing(6)

        icon_widget = IconWidget(RemakuIcon.CHEVRON_RIGHT, trigger)
        icon_widget.setFixedSize(16, 16)
        trigger_layout.addWidget(icon_widget)

        template_meta = macro.templates.get(template_id)
        trigger_label = BodyLabel(
            template_meta.label if template_meta and template_meta.label else template_id, trigger
        )
        trigger_layout.addWidget(trigger_label)

        card = CardWidget(self.content_widget)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(8, 8, 8, 8)
        card_layout.setSpacing(8)

        editor = TemplateEditor(macro, template_id, card)
        card_layout.addWidget(editor)

        card.setVisible(False)

        def toggle_card(event):
            card.setVisible(not card.isVisible())
            icon = RemakuIcon.CHEVRON_DOWN if card.isVisible() else RemakuIcon.CHEVRON_RIGHT
            icon_widget.setIcon(icon)

        trigger.mousePressEvent = toggle_card

        self.content_layout.addWidget(card)
