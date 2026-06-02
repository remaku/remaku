"""Settings interface.

Provides a graphical interface for editing application settings, as a sub-page of the main window.
"""

from collections.abc import Callable

from loguru import logger
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    CardWidget,
    CheckBox,
    ComboBox,
    LineEdit,
    MessageBox,
    PrimaryPushButton,
    ScrollArea,
    TitleLabel,
)

import config as cfg
from i18n import t

FIELD_WIDTH = 140


class SettingsPage(QWidget):
    def __init__(
        self,
        parent,
        conf: cfg.Config,
        on_save: Callable[[cfg.Config], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("settingsPage")

        self.conf = conf
        self.on_save = on_save

        self.build_ui()

    def build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(16)

        outer.addWidget(TitleLabel(t("settings.title")))

        scroll = ScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(ScrollArea.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")

        form = QWidget()
        form.setStyleSheet("background: transparent;")
        form_layout = QVBoxLayout(form)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(4)
        form_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.form_layout = form_layout

        scroll.setWidget(form)
        outer.addWidget(scroll, stretch=1)

        conf = self.conf

        self.section(t("settings.section.general"))
        self.var_always_on_top = self.checkbox(t("settings.always_on_top"))
        self.var_always_on_top.setChecked(conf.general.always_on_top)
        self.var_overlay = self.checkbox(t("settings.overlay_enabled"))
        self.var_overlay.setChecked(conf.general.overlay_enabled)
        self.var_auto_update = self.checkbox(t("settings.check_update_on_startup"))
        self.var_auto_update.setChecked(conf.general.check_update_on_startup)
        self.var_update_channel = self.dropdown(
            t("settings.update_channel"), conf.general.update_channel, ["stable", "beta"], "settings.channel"
        )
        self.var_theme = self.dropdown(
            t("settings.theme"), conf.general.theme, ["system", "light", "dark"], "settings.theme"
        )
        self.var_language = self.language_dropdown(conf.general.language)

        self.section(t("settings.section.capture"))
        self.var_fps = self.entry(t("settings.fps"), conf.capture.fps)

        self.section(t("settings.section.input"))
        self.var_jitter = self.entry(t("settings.jitter"), conf.input.jitter_ms)

        btn_row = QWidget()
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(0, 8, 0, 0)
        btn_layout.setSpacing(8)
        btn_layout.addStretch(1)

        save = PrimaryPushButton(t("action.save"))
        save.setFixedWidth(100)
        save.clicked.connect(self.save)
        btn_layout.addWidget(save)

        outer.addWidget(btn_row)

    def section(self, title: str) -> None:
        """Section heading."""
        label = BodyLabel(title)
        label.setContentsMargins(0, 12, 0, 4)
        self.form_layout.addWidget(label)

    def checkbox(self, label: str) -> CheckBox:
        card = CardWidget()
        layout = QHBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        cb = CheckBox(label)
        layout.addWidget(cb)
        self.form_layout.addWidget(card)
        return cb

    def entry(self, label: str, value) -> LineEdit:
        card = CardWidget()
        layout = QHBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        lbl = BodyLabel(label)
        layout.addWidget(lbl)
        layout.addStretch(1)

        edit = LineEdit()
        edit.setText(str(value))
        edit.setFixedWidth(FIELD_WIDTH)
        layout.addWidget(edit)

        self.form_layout.addWidget(card)
        return edit

    def dropdown(self, label: str, value: str, options: list[str], key_prefix: str) -> ComboBox:
        card = CardWidget()
        layout = QHBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        lbl = BodyLabel(label)
        layout.addWidget(lbl)
        layout.addStretch(1)

        combo = ComboBox()

        for opt in options:
            combo.addItem(t(f"{key_prefix}.{opt}"), userData=opt)

        idx = options.index(value) if value in options else 0
        combo.setCurrentIndex(idx)
        combo.setFixedWidth(FIELD_WIDTH)
        layout.addWidget(combo)

        self.form_layout.addWidget(card)
        return combo

    def language_dropdown(self, value: str) -> ComboBox:
        lang_options = ["auto", "zh_tw", "zh_cn", "en"]
        lang_labels = [t("settings.language_auto"), "繁體中文", "简体中文", "English"]

        card = CardWidget()
        layout = QHBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        lbl = BodyLabel(t("settings.language"))
        layout.addWidget(lbl)
        layout.addStretch(1)

        combo = ComboBox()
        for i, label in enumerate(lang_labels):
            combo.addItem(label, userData=lang_options[i])
        idx = lang_options.index(value) if value in lang_options else 0
        combo.setCurrentIndex(idx)
        combo.setFixedWidth(FIELD_WIDTH)
        combo.currentIndexChanged.connect(self.on_language_changed)
        layout.addWidget(combo)

        self.form_layout.addWidget(card)
        return combo

    def on_language_changed(self) -> None:
        MessageBox(t("settings.restart_title"), t("settings.restart_msg"), self).exec()

    def save(self) -> None:
        try:
            conf = cfg.Config(
                general=cfg.GeneralCfg(
                    target_window=self.conf.general.target_window,
                    always_on_top=self.var_always_on_top.isChecked(),
                    overlay_enabled=self.var_overlay.isChecked(),
                    check_update_on_startup=self.var_auto_update.isChecked(),
                    update_channel=self.var_update_channel.currentData() or "stable",
                    skipped_version=self.conf.general.skipped_version,
                    theme=self.var_theme.currentData() or "auto",
                    language=self.var_language.currentData() or "auto",
                    overlay_position=self.conf.general.overlay_position,
                ),
                capture=cfg.CaptureCfg(
                    fps=int(self.var_fps.text()),
                ),
                input=cfg.InputCfg(
                    jitter_ms=int(self.var_jitter.text()),
                ),
            )

            cfg.save(conf)

            if self.on_save:
                self.on_save(conf)

        except (ValueError, OSError) as e:
            logger.warning("settings: failed to save: {}", e)
            MessageBox(t("settings.save_failed"), t("settings.save_failed_msg", error=e), self).exec()
