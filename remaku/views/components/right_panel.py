from PySide6.QtCore import QCoreApplication, Qt, QTimer, Signal
from PySide6.QtGui import QFocusEvent, QIcon, QIntValidator
from PySide6.QtWidgets import QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget
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
    TextEdit,
    ToolTipFilter,
    ToolTipPosition,
)

from remaku.core import window
from remaku.core.event_bus import event_bus
from remaku.models.macro_model import (
    DelayStep,
    GridNavStep,
    HoldKeyUntilGoneStep,
    IfAnyImageStep,
    IfImageStep,
    IfNumberStep,
    KeyStep,
    Macro,
    MouseClickStep,
    MouseMoveStep,
    MouseScrollStep,
    RepeatStep,
    RepeatUntilNumberStep,
    Step,
    TextInputStep,
    WaitImageStep,
    WaitNumberStep,
)
from remaku.resources.icon import RemakuIcon
from remaku.views.components.elided_label import ElidedBodyLabel, ElidedSubtitleLabel
from remaku.views.components.hotkey_edit import HotkeyInput
from remaku.views.components.step_menu import show_step_menu
from remaku.views.components.template_editor import TemplateEditor


class CommitOnFocusOutTextEdit(TextEdit):
    text_committed = Signal(str)

    def focusOutEvent(self, event: QFocusEvent) -> None:
        self.text_committed.emit(self.toPlainText())
        super().focusOutEvent(event)


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
        "interval_ms",
        "clicks",
        "x",
        "y",
        "width",
        "height",
        "capture_width",
        "capture_height",
        "stable_reads",
        "value",
    }
)


def remaku_qicon(icon: RemakuIcon) -> QIcon:
    return QIcon(icon.path())


class PropertyFormMixin:
    content_widget: QWidget
    content_layout: QVBoxLayout

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

    def add_multiline_text_input(self, label: str, value: str, property_key: str = "") -> None:
        self.add_field_label(label)
        field = CommitOnFocusOutTextEdit(self.content_widget)
        field.setPlainText(value)
        field.setMinimumHeight(80)
        field.setMaximumHeight(120)
        field.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        if property_key:
            field.text_committed.connect(lambda text, pk=property_key: event_bus.step_property_changed.emit(pk, text))

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
            combo.addItem(option_label, userData=option_value)

        index = combo.findData(value)

        if index >= 0:
            combo.setCurrentIndex(index)

        if property_key:
            combo.currentIndexChanged.connect(
                lambda index, pk=property_key, c=combo: event_bus.step_property_changed.emit(pk, str(c.currentData()))
            )

        self.content_layout.addWidget(combo)

    def refresh_target_windows(self, combo: ComboBox, selected_window: str) -> None:
        combo.blockSignals(True)
        combo.clear()
        combo.addItem(QCoreApplication.translate("RightPanel", "(Use foreground window)"), userData="")

        for title in window.list_visible_windows():
            combo.addItem(title, userData=title)

        index = combo.findData(selected_window)

        if index < 0 and selected_window:
            combo.addItem(selected_window, userData=selected_window)
            index = combo.count() - 1

        if index >= 0:
            combo.setCurrentIndex(index)

        combo.blockSignals(False)

    def add_target_window_combo(self, macro: Macro) -> None:
        self.add_field_label(QCoreApplication.translate("RightPanel", "Target window"))
        target_combo = ComboBox(self.content_widget)

        self.refresh_target_windows(target_combo, macro.meta.target_window)

        target_combo.mousePressEvent = lambda event: (
            self.refresh_target_windows(target_combo, str(target_combo.currentData() or ""))
            or ComboBox.mousePressEvent(target_combo, event)
        )

        target_combo.currentIndexChanged.connect(
            lambda index, c=target_combo: event_bus.macro_meta_changed.emit("target_window", str(c.currentData()))
        )

        self.content_layout.addWidget(target_combo)

    def add_hotkey_text_input(self, macro: Macro) -> None:
        self.add_field_label(QCoreApplication.translate("RightPanel", "Hotkey"))
        hotkey_edit = HotkeyInput(self.content_widget)
        hotkey_edit.setText(macro.meta.hotkey)

        hotkey_edit.textChanged.connect(lambda text: event_bus.macro_meta_changed.emit("hotkey", text))

        self.content_layout.addWidget(hotkey_edit)

    def add_key_input(self, label: str, value: str) -> None:
        self.add_field_label(label)
        field = HotkeyInput(self.content_widget)
        field.setText(value)
        field.textChanged.connect(lambda text: event_bus.step_property_changed.emit("key", text))

        self.content_layout.addWidget(field)

    def add_checkbox_with_hint(self, checkbox: CheckBox, hint: str) -> None:
        row = QWidget(self.content_widget)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(6)

        info_icon = IconWidget(remaku_qicon(RemakuIcon.INFO), row)
        info_icon.setToolTip(hint)
        info_icon.setToolTipDuration(-1)
        info_icon.setCursor(Qt.CursorShape.WhatsThisCursor)
        info_icon.setFixedSize(16, 16)
        info_icon.installEventFilter(ToolTipFilter(info_icon, showDelay=300, position=ToolTipPosition.TOP))

        row_layout.addWidget(checkbox)
        row_layout.addWidget(info_icon)
        row_layout.addStretch(1)

        self.content_layout.addWidget(row)

    def add_enabled_checkbox(self, macro: Macro) -> None:
        enabled_checkbox = CheckBox(QCoreApplication.translate("RightPanel", "Enabled"), self.content_widget)
        enabled_checkbox.setChecked(macro.meta.enabled)

        enabled_checkbox.checkStateChanged.connect(
            lambda state: event_bus.macro_meta_changed.emit("enabled", str(state == Qt.CheckState.Checked))
        )

        self.content_layout.addWidget(enabled_checkbox)

    def add_gaming_mode_checkbox(self, macro: Macro) -> None:
        gaming_mode_checkbox = CheckBox(QCoreApplication.translate("RightPanel", "Gaming Mode"), self.content_widget)
        gaming_mode_checkbox.setChecked(macro.gaming_mode)

        gaming_mode_checkbox.checkStateChanged.connect(
            lambda state: event_bus.macro_meta_changed.emit("gaming_mode", str(state == Qt.CheckState.Checked))
        )

        self.add_checkbox_with_hint(
            gaming_mode_checkbox,
            QCoreApplication.translate(
                "RightPanel",
                "Scales templates for changing game resolutions. Turn it off for desktop apps when the target window size stays the same.",
            ),
        )

    def add_background_input_checkbox(self, macro: Macro) -> None:
        background_input_checkbox = CheckBox(
            QCoreApplication.translate("RightPanel", "Background Input"), self.content_widget
        )
        background_input_checkbox.setChecked(macro.background_input)

        background_input_checkbox.checkStateChanged.connect(
            lambda state: event_bus.macro_meta_changed.emit("background_input", str(state == Qt.CheckState.Checked))
        )

        self.add_checkbox_with_hint(
            background_input_checkbox,
            QCoreApplication.translate(
                "RightPanel",
                "Sends keys and mouse messages directly to the target window without focusing it. Some games ignore background messages; turn it off to use normal foreground input.",
            ),
        )

    def add_keep_target_focused_checkbox(self, macro: Macro) -> None:
        keep_target_focused_checkbox = CheckBox(
            QCoreApplication.translate("RightPanel", "Prevent Focus Loss"), self.content_widget
        )
        keep_target_focused_checkbox.setChecked(macro.keep_target_focused)

        keep_target_focused_checkbox.checkStateChanged.connect(
            lambda state: event_bus.macro_meta_changed.emit("keep_target_focused", str(state == Qt.CheckState.Checked))
        )

        self.add_checkbox_with_hint(
            keep_target_focused_checkbox,
            QCoreApplication.translate(
                "RightPanel",
                "Prevents the game from detecting that it lost focus, so it won't pause when you click away. May not work with all games.",
            ),
        )

    def add_skip_checkbox(self, value: bool, enabled: bool = True) -> None:
        skip_checkbox = CheckBox(QCoreApplication.translate("RightPanel", "Skip"), self.content_widget)
        skip_checkbox.setChecked(value)
        skip_checkbox.setEnabled(enabled)

        skip_checkbox.checkStateChanged.connect(
            lambda state: event_bus.step_property_changed.emit("skip", str(state == Qt.CheckState.Checked))
        )

        self.content_layout.addWidget(skip_checkbox)

    def add_note_input(self, value: str) -> None:
        self.add_field_label(QCoreApplication.translate("RightPanel", "Note"))
        note_edit = LineEdit(self.content_widget)
        note_edit.setText(value)
        note_edit.setPlaceholderText(QCoreApplication.translate("RightPanel", "Add a note for this step"))

        note_edit.editingFinished.connect(lambda w=note_edit: event_bus.step_property_changed.emit("note", w.text()))

        self.content_layout.addWidget(note_edit)

    def add_template_editor(self, macro: Macro, template_id: str) -> None:
        template_editor = TemplateEditor(macro, template_id, self.content_widget)
        self.content_layout.addWidget(template_editor)

    def add_template_list_editor(self, macro: Macro, template_ids: list[str]) -> None:
        for template_id in template_ids:
            self.add_template_card(macro, template_id)

        add_template_button = PushButton(
            RemakuIcon.PLUS, QCoreApplication.translate("RightPanel", "Add Template"), self.content_widget
        )
        add_template_button.clicked.connect(lambda: event_bus.template_add_requested.emit())
        self.content_layout.addWidget(add_template_button)

    def add_template_card(self, macro: Macro, template_id: str) -> None:
        trigger = QWidget(self.content_widget)
        trigger.setCursor(Qt.CursorShape.PointingHandCursor)
        self.content_layout.addWidget(trigger)

        trigger_layout = QHBoxLayout(trigger)
        trigger_layout.setContentsMargins(0, 6, 0, 6)
        trigger_layout.setSpacing(6)

        icon_widget = IconWidget(remaku_qicon(RemakuIcon.CHEVRON_RIGHT), trigger)
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
            icon_widget.setIcon(remaku_qicon(icon))

        trigger.mousePressEvent = toggle_card

        self.content_layout.addWidget(card)

    def add_number_area_editor(self, step) -> None:
        pick_button = PushButton(
            RemakuIcon.SCAN_SEARCH,
            QCoreApplication.translate("RightPanel", "Pick Area"),
            self.content_widget,
        )
        pick_button.clicked.connect(event_bus.number_area_pick_requested.emit)
        self.content_layout.addWidget(pick_button)

        self.add_text_input("X", str(step.x), "x")
        self.add_text_input("Y", str(step.y), "y")
        self.add_text_input(QCoreApplication.translate("RightPanel", "Width"), str(step.width), "width")
        self.add_text_input(QCoreApplication.translate("RightPanel", "Height"), str(step.height), "height")
        self.add_dropdown(
            QCoreApplication.translate("RightPanel", "Relative"),
            "true" if step.relative else "false",
            [
                (QCoreApplication.translate("RightPanel", "Client"), "true"),
                (QCoreApplication.translate("RightPanel", "Absolute"), "false"),
            ],
            "relative",
        )
        self.add_text_input(
            QCoreApplication.translate("RightPanel", "Capture Width"),
            str(step.capture_width),
            "capture_width",
        )
        self.add_text_input(
            QCoreApplication.translate("RightPanel", "Capture Height"),
            str(step.capture_height),
            "capture_height",
        )

    def add_number_condition_editor(self, step) -> None:
        self.add_dropdown(
            QCoreApplication.translate("RightPanel", "Operator"),
            step.operator,
            [
                (QCoreApplication.translate("RightPanel", "Equal to (=)"), "="),
                (QCoreApplication.translate("RightPanel", "Not equal to (≠)"), "≠"),
                (QCoreApplication.translate("RightPanel", "Greater than (>)"), ">"),
                (QCoreApplication.translate("RightPanel", "Greater than or equal to (≥)"), "≥"),
                (QCoreApplication.translate("RightPanel", "Less than (<)"), "<"),
                (QCoreApplication.translate("RightPanel", "Less than or equal to (≤)"), "≤"),
            ],
            "operator",
        )
        self.add_text_input(QCoreApplication.translate("RightPanel", "Value"), str(step.value), "value")
        self.add_text_input(
            QCoreApplication.translate("RightPanel", "Timeout (ms)"),
            str(step.timeout_ms),
            "timeout_ms",
        )
        self.add_text_input(
            QCoreApplication.translate("RightPanel", "Stable Reads"),
            str(step.stable_reads),
            "stable_reads",
        )


class StepPropertiesWidget(QWidget, PropertyFormMixin):
    def __init__(self, macro: Macro, step: Step, title_text: str, skip_enabled: bool = True, parent=None):
        super().__init__(parent)

        self.macro = macro
        self.step = step
        self.content_widget = self
        self.content_layout = QVBoxLayout(self)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(12)
        self.content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.add_title_label(title_text)
        self.add_skip_checkbox(step.skip, skip_enabled)
        self.add_note_input(step.note)
        self.add_step_fields()

    def add_step_fields(self) -> None:
        raise NotImplementedError


class KeyStepPropertiesWidget(StepPropertiesWidget):
    step: KeyStep

    def add_step_fields(self) -> None:
        self.add_key_input(QCoreApplication.translate("RightPanel", "Key"), self.step.key)
        self.add_text_input(QCoreApplication.translate("RightPanel", "Hold (ms)"), str(self.step.hold_ms), "hold_ms")


class DelayStepPropertiesWidget(StepPropertiesWidget):
    step: DelayStep

    def add_step_fields(self) -> None:
        self.add_text_input(QCoreApplication.translate("RightPanel", "Duration (ms)"), str(self.step.ms), "ms")


class WaitImageStepPropertiesWidget(StepPropertiesWidget):
    step: WaitImageStep

    def add_step_fields(self) -> None:
        self.add_template_editor(self.macro, self.step.template)
        self.add_slider(
            QCoreApplication.translate("RightPanel", "Threshold"), self.step.threshold, property_key="threshold"
        )
        self.add_text_input(
            QCoreApplication.translate("RightPanel", "Timeout (ms)"), str(self.step.timeout_ms), "timeout_ms"
        )
        self.add_dropdown(
            QCoreApplication.translate("RightPanel", "On Timeout"),
            self.step.on_timeout,
            [
                (QCoreApplication.translate("RightPanel", "Stop"), "stop"),
                (QCoreApplication.translate("RightPanel", "Continue"), "continue"),
            ],
            "on_timeout",
        )


class HoldKeyUntilGoneStepPropertiesWidget(StepPropertiesWidget):
    step: HoldKeyUntilGoneStep

    def add_step_fields(self) -> None:
        self.add_key_input(QCoreApplication.translate("RightPanel", "Key"), self.step.key)
        self.add_template_editor(self.macro, self.step.template)
        self.add_slider(
            QCoreApplication.translate("RightPanel", "Threshold"), self.step.threshold, property_key="threshold"
        )
        self.add_text_input(
            QCoreApplication.translate("RightPanel", "Load Delay (ms)"),
            str(self.step.load_delay_ms),
            "load_delay_ms",
        )
        self.add_text_input(
            QCoreApplication.translate("RightPanel", "Find Timeout (ms)"),
            str(self.step.find_timeout_ms),
            "find_timeout_ms",
        )
        self.add_text_input(
            QCoreApplication.translate("RightPanel", "Gone Grace (ms)"),
            str(self.step.gone_grace_ms),
            "gone_grace_ms",
        )
        self.add_text_input(
            QCoreApplication.translate("RightPanel", "Hard Timeout (ms)"),
            str(self.step.hard_timeout_ms),
            "hard_timeout_ms",
        )


class TextInputStepPropertiesWidget(StepPropertiesWidget):
    step: TextInputStep

    def add_step_fields(self) -> None:
        self.add_multiline_text_input(QCoreApplication.translate("RightPanel", "Text"), self.step.text, "text")
        self.add_text_input(
            QCoreApplication.translate("RightPanel", "Interval (ms)"),
            str(self.step.interval_ms),
            "interval_ms",
        )


class WaitNumberStepPropertiesWidget(StepPropertiesWidget):
    step: WaitNumberStep

    def add_step_fields(self) -> None:
        self.add_number_area_editor(self.step)
        self.add_number_condition_editor(self.step)


class IfNumberStepPropertiesWidget(StepPropertiesWidget):
    step: IfNumberStep

    def add_step_fields(self) -> None:
        self.add_number_area_editor(self.step)
        self.add_number_condition_editor(self.step)


class RepeatUntilNumberStepPropertiesWidget(StepPropertiesWidget):
    step: RepeatUntilNumberStep

    def add_step_fields(self) -> None:
        self.add_number_area_editor(self.step)
        self.add_number_condition_editor(self.step)
        self.add_text_input(QCoreApplication.translate("RightPanel", "Max Runs"), str(self.step.count), "count")
        check_first = CheckBox(QCoreApplication.translate("RightPanel", "Check Before First Run"), self.content_widget)
        check_first.setChecked(self.step.check_first)
        check_first.checkStateChanged.connect(
            lambda state: event_bus.step_property_changed.emit("check_first", str(state == Qt.CheckState.Checked))
        )
        self.content_layout.addWidget(check_first)


class RepeatStepPropertiesWidget(StepPropertiesWidget):
    step: RepeatStep

    def add_step_fields(self) -> None:
        self.add_text_input(QCoreApplication.translate("RightPanel", "Count"), str(self.step.count), "count")


class IfImageStepPropertiesWidget(StepPropertiesWidget):
    step: IfImageStep

    def add_step_fields(self) -> None:
        self.add_template_editor(self.macro, self.step.template)
        self.add_slider(
            QCoreApplication.translate("RightPanel", "Threshold"), self.step.threshold, property_key="threshold"
        )
        self.add_text_input(
            QCoreApplication.translate("RightPanel", "Timeout (ms)"), str(self.step.timeout_ms), "timeout_ms"
        )


class IfAnyImageStepPropertiesWidget(StepPropertiesWidget):
    step: IfAnyImageStep

    def add_step_fields(self) -> None:
        self.add_template_list_editor(self.macro, self.step.templates)
        self.add_slider(
            QCoreApplication.translate("RightPanel", "Threshold"), self.step.threshold, property_key="threshold"
        )
        self.add_text_input(
            QCoreApplication.translate("RightPanel", "Timeout (ms)"), str(self.step.timeout_ms), "timeout_ms"
        )
        self.add_dropdown(
            QCoreApplication.translate("RightPanel", "On Timeout"),
            self.step.on_timeout,
            [
                (QCoreApplication.translate("RightPanel", "Stop"), "stop"),
                (QCoreApplication.translate("RightPanel", "Continue"), "continue"),
            ],
            "on_timeout",
        )


class GridNavStepPropertiesWidget(StepPropertiesWidget):
    step: GridNavStep

    def add_step_fields(self) -> None:
        self.add_text_input(QCoreApplication.translate("RightPanel", "Rows"), str(self.step.rows), "rows")
        self.add_text_input(QCoreApplication.translate("RightPanel", "Start Cell"), str(self.step.start), "start")


class MouseClickStepPropertiesWidget(StepPropertiesWidget):
    step: MouseClickStep

    def add_step_fields(self) -> None:
        self.add_dropdown(
            QCoreApplication.translate("RightPanel", "Button"),
            self.step.button,
            [
                (QCoreApplication.translate("RightPanel", "Left"), "left"),
                (QCoreApplication.translate("RightPanel", "Right"), "right"),
                (QCoreApplication.translate("RightPanel", "Middle"), "middle"),
            ],
            "button",
        )
        self.add_dropdown(
            QCoreApplication.translate("RightPanel", "Target"),
            self.step.target,
            [
                (QCoreApplication.translate("RightPanel", "Coordinate"), "coordinate"),
                (QCoreApplication.translate("RightPanel", "Image Center"), "template"),
            ],
            "target",
        )

        if self.step.target == "coordinate":
            self.add_text_input("X", str(self.step.x), "x")
            self.add_text_input("Y", str(self.step.y), "y")
            self.add_dropdown(
                QCoreApplication.translate("RightPanel", "Relative"),
                "true" if self.step.relative else "false",
                [
                    (QCoreApplication.translate("RightPanel", "Client"), "true"),
                    (QCoreApplication.translate("RightPanel", "Absolute"), "false"),
                ],
                "relative",
            )
        else:
            self.add_template_editor(self.macro, self.step.template)
            self.add_slider(
                QCoreApplication.translate("RightPanel", "Threshold"),
                self.step.threshold,
                property_key="threshold",
            )
            self.add_text_input(
                QCoreApplication.translate("RightPanel", "Timeout (ms)"),
                str(self.step.timeout_ms),
                "timeout_ms",
            )
            self.add_dropdown(
                QCoreApplication.translate("RightPanel", "On Timeout"),
                self.step.on_timeout,
                [
                    (QCoreApplication.translate("RightPanel", "Stop"), "stop"),
                    (QCoreApplication.translate("RightPanel", "Continue"), "continue"),
                ],
                "on_timeout",
            )


class MouseMoveStepPropertiesWidget(StepPropertiesWidget):
    step: MouseMoveStep

    def add_step_fields(self) -> None:
        self.add_dropdown(
            QCoreApplication.translate("RightPanel", "Target"),
            self.step.target,
            [
                (QCoreApplication.translate("RightPanel", "Coordinate"), "coordinate"),
                (QCoreApplication.translate("RightPanel", "Image Center"), "template"),
            ],
            "target",
        )

        if self.step.target == "coordinate":
            self.add_text_input("X", str(self.step.x), "x")
            self.add_text_input("Y", str(self.step.y), "y")
            self.add_dropdown(
                QCoreApplication.translate("RightPanel", "Relative"),
                "true" if self.step.relative else "false",
                [
                    (QCoreApplication.translate("RightPanel", "Client"), "true"),
                    (QCoreApplication.translate("RightPanel", "Absolute"), "false"),
                ],
                "relative",
            )
        else:
            self.add_template_editor(self.macro, self.step.template)
            self.add_slider(
                QCoreApplication.translate("RightPanel", "Threshold"),
                self.step.threshold,
                property_key="threshold",
            )
            self.add_text_input(
                QCoreApplication.translate("RightPanel", "Timeout (ms)"),
                str(self.step.timeout_ms),
                "timeout_ms",
            )
            self.add_dropdown(
                QCoreApplication.translate("RightPanel", "On Timeout"),
                self.step.on_timeout,
                [
                    (QCoreApplication.translate("RightPanel", "Stop"), "stop"),
                    (QCoreApplication.translate("RightPanel", "Continue"), "continue"),
                ],
                "on_timeout",
            )


class MouseScrollStepPropertiesWidget(StepPropertiesWidget):
    step: MouseScrollStep

    def add_step_fields(self) -> None:
        self.add_text_input(QCoreApplication.translate("RightPanel", "Scroll Clicks"), str(self.step.clicks), "clicks")
        self.add_text_input(
            QCoreApplication.translate("RightPanel", "Interval (ms)"),
            str(self.step.interval_ms),
            "interval_ms",
        )
        hint = BodyLabel(
            QCoreApplication.translate("RightPanel", "Positive = scroll up, negative = scroll down"),
            self.content_widget,
        )
        self.content_layout.addWidget(hint)


STEP_PROPERTIES_WIDGETS: dict[type[Step], type[StepPropertiesWidget]] = {
    KeyStep: KeyStepPropertiesWidget,
    DelayStep: DelayStepPropertiesWidget,
    WaitImageStep: WaitImageStepPropertiesWidget,
    HoldKeyUntilGoneStep: HoldKeyUntilGoneStepPropertiesWidget,
    TextInputStep: TextInputStepPropertiesWidget,
    WaitNumberStep: WaitNumberStepPropertiesWidget,
    IfNumberStep: IfNumberStepPropertiesWidget,
    RepeatUntilNumberStep: RepeatUntilNumberStepPropertiesWidget,
    RepeatStep: RepeatStepPropertiesWidget,
    IfImageStep: IfImageStepPropertiesWidget,
    IfAnyImageStep: IfAnyImageStepPropertiesWidget,
    GridNavStep: GridNavStepPropertiesWidget,
    MouseClickStep: MouseClickStepPropertiesWidget,
    MouseMoveStep: MouseMoveStepPropertiesWidget,
    MouseScrollStep: MouseScrollStepPropertiesWidget,
}


class RightPanel(ScrollArea, PropertyFormMixin):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.init_ui()

    def init_ui(self):
        self.setMinimumWidth(220)
        self.setMaximumWidth(350)
        self.setWidgetResizable(True)
        self.setFrameShape(ScrollArea.Shape.NoFrame)
        self.setStyleSheet("background: transparent;")

        self.content_widget = CardWidget(self)
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
        self.add_gaming_mode_checkbox(macro)
        self.add_background_input_checkbox(macro)
        self.add_keep_target_focused_checkbox(macro)

    def show_step_properties(self, macro: Macro, title_text: str, step: Step, skip_enabled: bool = True) -> None:
        self.clear_content()

        widget_class = STEP_PROPERTIES_WIDGETS.get(type(step))

        if widget_class is None:
            return

        self.content_layout.addWidget(widget_class(macro, step, title_text, skip_enabled, self.content_widget))

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
