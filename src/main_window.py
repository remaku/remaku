"""Main window interface.

Provides a three-panel layout, menus, and status bar for managing and running macros.
"""

import contextlib
import copy
import ctypes
import ctypes.wintypes
import json
import os
import shutil
import time
import webbrowser
import zipfile

import pydirectinput as pdi
from loguru import logger
from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QCursor, QIcon, QKeyEvent, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QListWidgetItem,
    QSplitter,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    Action,
    BodyLabel,
    CaptionLabel,
    CardWidget,
    CheckBox,
    ComboBox,
    FluentWindow,
    LineEdit,
    ListWidget,
    MessageBox,
    MessageBoxBase,
    PushButton,
    RoundMenu,
    ScrollArea,
    Slider,
    SubtitleLabel,
    Theme,
    TransparentPushButton,
    TransparentToolButton,
    qrouter,
    setTheme,
)

import config as cfg
import updater
import window
from i18n import t
from icons import icon
from macro_engine import MacroRunner, load_macro
from region_selector import RegionSelector
from settings import SettingsPage
from version import __version__, root


class MainWindow(FluentWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Remaku")
        self.setWindowIcon(QIcon(str(root / "icon.ico")))
        self.setMinimumSize(900, 600)
        self.resize(900, 600)
        # Disable sub-interface slide animation
        self.stackedWidget.setAnimationEnabled(False)

        self.conf = cfg.load()
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, self.conf.general.always_on_top)
        self.current_runner: MacroRunner | None = None
        self.load_macros()
        self.build_ui()
        self.register_shortcuts()

        if self.runners:
            self.macro_list.setCurrentRow(0)

        self.update_empty_states()
        self.register_hotkeys()

        if self.conf.general.check_update_on_startup:
            QTimer.singleShot(1000, self.startup_check_update)

    def resizeEvent(self, e):
        # HACK: MSFluentWindow's title bar shifts position after navigationInterface
        # is hidden. Manually force it to (0,0) and correct the width.
        # Side effect: titleBar.resize is called twice (parent already calls once),
        # but without this the title bar misaligns in certain situations.
        super().resizeEvent(e)
        self.titleBar.move(0, 0)
        self.titleBar.resize(self.width(), self.titleBar.height())

    def onStackedWidgetChanged(self, index: int):
        widget = self.stackedWidget.widget(index)
        isHome = widget is self.central
        self.returnButton.setVisible(not isHome)

    def register_shortcuts(self) -> None:
        """Register window-level keyboard shortcuts."""
        QShortcut(QKeySequence("Ctrl+N"), self).activated.connect(self.on_add_macro)
        QShortcut(QKeySequence("Ctrl+,"), self).activated.connect(self.open_settings)
        QShortcut(QKeySequence("Ctrl+Shift+N"), self).activated.connect(self.on_add_step)
        sc_del = QShortcut(QKeySequence("Delete"), self.step_list)
        sc_del.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        sc_del.activated.connect(self.on_delete_step)
        QShortcut(QKeySequence("Alt+Up"), self).activated.connect(lambda: self.on_move_step(-1))
        QShortcut(QKeySequence("Alt+Down"), self).activated.connect(lambda: self.on_move_step(1))
        QShortcut(QKeySequence("Ctrl+Z"), self).activated.connect(self.undo)
        QShortcut(QKeySequence("Ctrl+Y"), self).activated.connect(self.redo)
        QShortcut(QKeySequence("Ctrl+D"), self).activated.connect(self.duplicate_steps)
        QShortcut(QKeySequence("Ctrl+C"), self).activated.connect(self.copy_steps)
        QShortcut(QKeySequence("Ctrl+X"), self).activated.connect(self.cut_steps)
        QShortcut(QKeySequence("Ctrl+V"), self).activated.connect(self.paste_steps)

    def register_hotkeys(self) -> None:
        user32 = ctypes.windll.user32

        for hid in getattr(self, "hotkey_ids", []):
            user32.UnregisterHotKey(int(self.winId()), hid)

        self.hotkey_ids: list[int] = []
        self.hotkey_map: dict[int, MacroRunner] = {}

        for i, runner in enumerate(self.runners):
            if not runner.macro.get("meta", {}).get("enabled", True):
                continue

            hotkey = runner.macro.get("meta", {}).get("hotkey", "")

            if not hotkey:
                continue

            mods, vk = self.parse_hotkey(hotkey)

            if vk == 0:
                continue

            hid = 0xBF00 + i

            if user32.RegisterHotKey(int(self.winId()), hid, mods, vk):
                self.hotkey_ids.append(hid)
                self.hotkey_map[hid] = runner
                logger.info("Registered hotkey: {} -> {}", hotkey, runner.label)
            else:
                logger.warning("Hotkey registration failed: {}", hotkey)

    def parse_hotkey(self, hotkey: str) -> tuple[int, int]:
        MOD_ALT = 0x0001
        MOD_CTRL = 0x0002
        MOD_SHIFT = 0x0004
        mods = 0
        vk = 0
        parts = hotkey.lower().split("+")

        for part in parts:
            if part == "ctrl":
                mods |= MOD_CTRL
            elif part == "alt":
                mods |= MOD_ALT
            elif part == "shift":
                mods |= MOD_SHIFT
            else:
                vk = self.key_to_vk(part)

        return mods, vk

    def key_to_vk(self, key: str) -> int:
        vk_map: dict[str, int] = {
            "f1": 0x70,
            "f2": 0x71,
            "f3": 0x72,
            "f4": 0x73,
            "f5": 0x74,
            "f6": 0x75,
            "f7": 0x76,
            "f8": 0x77,
            "f9": 0x78,
            "f10": 0x79,
            "f11": 0x7A,
            "f12": 0x7B,
            "space": 0x20,
            "enter": 0x0D,
            "return": 0x0D,
            "tab": 0x09,
            "esc": 0x1B,
            "escape": 0x1B,
            "insert": 0x2D,
            "delete": 0x2E,
            "home": 0x24,
            "end": 0x23,
            "pageup": 0x21,
            "pagedown": 0x22,
            "up": 0x26,
            "down": 0x28,
            "left": 0x25,
            "right": 0x27,
        }

        if key in vk_map:
            return vk_map[key]

        if len(key) == 1:
            return ctypes.windll.user32.VkKeyScanW(ord(key)) & 0xFF

        return 0

    def run_hotkey(self, runner: MacroRunner) -> None:
        if runner.is_running():
            runner.stop()
        elif runner.macro.get("meta", {}).get("enabled", True):
            runner.conf = self.conf
            runner.start()
            self.start_refresh_timer()

    def nativeEvent(self, event_type: bytes | bytearray, message: int) -> object:  # type: ignore[override]
        WM_HOTKEY = 0x0312

        if event_type == b"windows_generic_MSG":
            msg = ctypes.wintypes.MSG.from_address(int(message))
            if msg.message == WM_HOTKEY:
                hid = msg.wParam
                runner = getattr(self, "hotkey_map", {}).get(hid)
                if runner:
                    self.run_hotkey(runner)

        return super().nativeEvent(event_type, message)

    @property
    def macro_templates_dir(self):
        """Path to the current macro's template folder."""
        name = self.current_runner.name if self.current_runner else ""
        return cfg.templates_dir(name)

    def load_macros(self) -> None:
        self.runners: list[MacroRunner] = []
        runners = []

        for json_file in cfg.macros_dir().glob("*.json"):
            try:
                macro = load_macro(json_file)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Skipping corrupted macro {}: {}", json_file.name, e)
                continue

            runner = MacroRunner(self.conf, macro, source_path=json_file)
            runners.append(runner)

        order = self.conf.general.macro_order
        order_map = {name: i for i, name in enumerate(order)}
        runners.sort(key=lambda r: order_map.get(r.name, len(order)))
        self.runners = runners

    def build_ui(self) -> None:
        # HACK: MSFluentWindow shows a left navigation panel by default and reserves
        # title bar space for it. We don't use the nav panel, so we hide it and
        # manually adjust the title bar:
        # 1. Hide navigationInterface
        # 2. Set hBoxLayout left margin to 12px (replacing the default 20px spacing)
        # 3. Insert a return button in the title bar (shown when entering sub-pages)
        # 4. Combined with resizeEvent forcing title bar position to avoid misalignment
        self.navigationInterface.setVisible(False)
        self.titleBar.hBoxLayout.setContentsMargins(12, 0, 0, 0)

        self.returnButton = TransparentToolButton(icon("arrow-left"), self)
        self.returnButton.setToolTip(t("action.back"))
        self.returnButton.setFixedSize(24, 24)
        self.returnButton.setIconSize(QSize(14, 14))
        self.returnButton.clicked.connect(qrouter.pop)
        qrouter.emptyChanged.connect(self.returnButton.setDisabled)
        self.returnButton.setDisabled(True)
        self.returnButton.hide()
        self.titleBar.hBoxLayout.insertWidget(
            0,
            self.returnButton,
            0,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        )
        self.titleBar.hBoxLayout.insertSpacing(1, 8)
        self.stackedWidget.currentChanged.connect(self.onStackedWidgetChanged)

        self.central = QWidget()
        main_layout = QVBoxLayout(self.central)
        main_layout.setContentsMargins(8, 0, 8, 8)
        main_layout.setSpacing(8)

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(0, 0, 0, 0)
        toolbar.setSpacing(6)

        self.menu_file = TransparentPushButton(t("menu.file"))
        self.menu_file.clicked.connect(self.show_file_menu)
        toolbar.addWidget(self.menu_file)

        self.menu_edit = TransparentPushButton(t("menu.edit"))
        self.menu_edit.clicked.connect(self.show_edit_menu)
        toolbar.addWidget(self.menu_edit)

        self.menu_help = TransparentPushButton(t("menu.help"))
        self.menu_help.clicked.connect(self.show_help_menu)
        toolbar.addWidget(self.menu_help)

        self.btn_run = TransparentPushButton(icon("play"), t("action.run"))
        self.btn_run.clicked.connect(self.on_run)
        toolbar.addWidget(self.btn_run)

        self.btn_add_step = TransparentPushButton(icon("plus"), t("action.add"))
        self.btn_add_step.clicked.connect(self.on_add_step)
        toolbar.addWidget(self.btn_add_step)

        self.btn_del = TransparentToolButton(icon("trash-2"))
        self.btn_del.clicked.connect(self.on_delete_step)
        toolbar.addWidget(self.btn_del)

        self.btn_up = TransparentToolButton(icon("arrow-up"))
        self.btn_up.clicked.connect(lambda: self.on_move_step(-1))
        toolbar.addWidget(self.btn_up)

        self.btn_down = TransparentToolButton(icon("arrow-down"))
        self.btn_down.clicked.connect(lambda: self.on_move_step(1))
        toolbar.addWidget(self.btn_down)

        self.btn_undo = TransparentToolButton(icon("undo-2"))
        self.btn_undo.clicked.connect(self.undo)
        toolbar.addWidget(self.btn_undo)

        self.btn_redo = TransparentToolButton(icon("redo-2"))
        self.btn_redo.clicked.connect(self.redo)
        toolbar.addWidget(self.btn_redo)

        toolbar.addStretch()

        main_layout.addLayout(toolbar)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet("QSplitter::handle { background: transparent; }")

        self.left_panel = CardWidget()
        self.left_panel.setMinimumWidth(200)
        self.left_panel.setMaximumWidth(300)

        left_layout = QVBoxLayout(self.left_panel)
        left_layout.setContentsMargins(8, 8, 8, 8)
        left_layout.setSpacing(12)

        header = QHBoxLayout()
        left_layout.addLayout(header)

        title = SubtitleLabel(t("macro.title"))
        header.addWidget(title)
        header.addStretch()

        add_btn = PushButton(icon("plus"), t("action.add"))
        add_btn.clicked.connect(self.on_add_macro)
        header.addWidget(add_btn)

        self.macro_list = ListWidget()
        self.macro_list.setDragDropMode(ListWidget.DragDropMode.InternalMove)
        self.macro_list.currentRowChanged.connect(self.on_macro_selected)
        self.macro_list.itemClicked.connect(lambda: self.show_macro_props())
        self.macro_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.macro_list.customContextMenuRequested.connect(self.on_macro_context_menu)
        self.macro_list.model().rowsMoved.connect(self.on_macros_reordered)
        left_layout.addWidget(self.macro_list, 1)

        self.macro_empty_label = BodyLabel(t("macro.empty_hint"))
        self.macro_empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.macro_empty_label.setWordWrap(True)
        left_layout.addWidget(self.macro_empty_label, 1)

        for runner in self.runners:
            item = QListWidgetItem(runner.label)
            item.setData(Qt.ItemDataRole.UserRole, runner.name)
            self.macro_list.addItem(item)

        splitter.addWidget(self.left_panel)

        self.center_panel = CardWidget()
        center_layout = QVBoxLayout(self.center_panel)
        center_layout.setContentsMargins(8, 8, 8, 8)
        center_layout.setSpacing(0)

        self.step_list = ListWidget()
        self.step_list.setIconSize(QSize(18, 18))
        self.step_list.setSelectionMode(ListWidget.SelectionMode.ExtendedSelection)
        self.step_list.currentRowChanged.connect(self.on_step_selected)
        self.step_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.step_list.customContextMenuRequested.connect(self.on_step_context_menu)
        center_layout.addWidget(self.step_list, 1)

        self.step_empty_label = BodyLabel(t("step.empty_hint"))
        self.step_empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.step_empty_label.setWordWrap(True)
        center_layout.addWidget(self.step_empty_label, 1)

        splitter.addWidget(self.center_panel)

        self.right_panel = ScrollArea()
        self.right_panel.setMinimumWidth(220)
        self.right_panel.setMaximumWidth(350)
        self.right_panel.setWidgetResizable(True)
        self.right_panel.setFrameShape(ScrollArea.Shape.NoFrame)
        self.right_panel.setStyleSheet("background: transparent;")

        right_content = CardWidget()
        self.right_layout = QVBoxLayout(right_content)
        self.right_layout.setContentsMargins(8, 8, 8, 8)
        self.right_layout.setSpacing(12)
        self.right_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.prop_title = SubtitleLabel(t("step.props_title"))
        self.prop_title.setWordWrap(True)
        self.right_layout.addWidget(self.prop_title)

        self.prop_container = QWidget()
        self.prop_fields_layout = QVBoxLayout(self.prop_container)
        self.prop_fields_layout.setContentsMargins(0, 0, 0, 0)
        self.prop_fields_layout.setSpacing(12)
        self.right_layout.addWidget(self.prop_container)

        self.right_panel.setWidget(right_content)
        splitter.addWidget(self.right_panel)

        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)
        splitter.setCollapsible(2, False)
        splitter.setSizes([220, 550, 250])

        main_layout.addWidget(splitter, 1)

        self.status_label = CaptionLabel(t("status.macro_count", count=len(self.runners)))
        main_layout.addWidget(self.status_label)

        self.central.setObjectName("mainPanel")
        self.addSubInterface(self.central, "", "", isTransparent=True)

    def show_file_menu(self) -> None:
        menu = RoundMenu(parent=self)

        menu.addAction(Action(t("menu.file.new_macro"), triggered=self.on_add_macro, shortcut="Ctrl+N"))
        menu.addAction(Action(t("menu.file.duplicate_macro"), triggered=self.on_duplicate_macro))

        menu.addSeparator()

        menu.addAction(Action(t("menu.file.export"), triggered=self.on_export_json))
        menu.addAction(Action(t("menu.file.import"), triggered=self.on_import_json))

        menu.addSeparator()

        menu.addAction(Action(t("menu.file.settings"), triggered=self.open_settings, shortcut="Ctrl+,"))

        menu.addSeparator()

        menu.addAction(Action(t("menu.file.quit"), triggered=self.close))

        menu.exec(self.menu_file.mapToGlobal(self.menu_file.rect().bottomLeft()))

    def show_edit_menu(self) -> None:
        menu = RoundMenu(parent=self)

        menu.addAction(Action(t("menu.edit.undo"), triggered=self.undo, shortcut="Ctrl+Z"))
        menu.addAction(Action(t("menu.edit.redo"), triggered=self.redo, shortcut="Ctrl+Y"))

        menu.addSeparator()

        menu.addAction(Action(t("menu.edit.cut"), triggered=self.cut_steps, shortcut="Ctrl+X"))
        menu.addAction(Action(t("menu.edit.copy"), triggered=self.copy_steps, shortcut="Ctrl+C"))
        menu.addAction(Action(t("menu.edit.paste"), triggered=self.paste_steps, shortcut="Ctrl+V"))

        menu.addSeparator()

        menu.addAction(Action(t("menu.edit.add_step"), triggered=self.on_add_step, shortcut="Ctrl+Shift+N"))
        menu.addAction(Action(t("menu.edit.duplicate_step"), triggered=self.duplicate_steps, shortcut="Ctrl+D"))
        menu.addAction(Action(t("menu.edit.delete_step"), triggered=self.on_delete_step, shortcut="Delete"))

        menu.addSeparator()

        menu.addAction(Action(t("menu.edit.move_up"), triggered=lambda: self.on_move_step(-1), shortcut="Alt+Up"))
        menu.addAction(Action(t("menu.edit.move_down"), triggered=lambda: self.on_move_step(1), shortcut="Alt+Down"))

        menu.exec(self.menu_edit.mapToGlobal(self.menu_edit.rect().bottomLeft()))

    def show_help_menu(self) -> None:
        menu = RoundMenu(parent=self)

        menu.addAction(Action(t("menu.help.about"), triggered=self.on_about))
        menu.addAction(Action(t("menu.help.sponsor"), triggered=self.on_sponsor))
        menu.addAction(Action(t("menu.help.check_update"), triggered=self.on_check_update))
        menu.addSeparator()
        menu.addAction(Action(t("menu.help.open_logs"), triggered=self.on_open_logs))

        menu.exec(self.menu_help.mapToGlobal(self.menu_help.rect().bottomLeft()))

    def update_empty_states(self) -> None:
        has_macros = self.macro_list.count() > 0
        self.macro_list.setVisible(has_macros)
        self.macro_empty_label.setVisible(not has_macros)

        has_steps = self.step_list.count() > 0
        self.step_list.setVisible(has_steps)
        self.step_empty_label.setVisible(not has_steps)

        has_selection = self.current_runner is not None
        self.btn_run.setEnabled(has_selection)
        self.btn_add_step.setEnabled(has_selection)
        self.btn_del.setEnabled(has_selection)
        self.btn_up.setEnabled(has_selection)
        self.btn_down.setEnabled(has_selection)

    def commit_field_edits(self) -> None:
        for edit in self.right_panel.findChildren(LineEdit):
            if edit.hasFocus():
                edit.editingFinished.emit()
                edit.clearFocus()

    def changeEvent(self, event) -> None:
        if event.type() == event.Type.ActivationChange and not self.isActiveWindow():
            self.commit_field_edits()

        super().changeEvent(event)

    def on_macro_selected(self, row: int) -> None:
        self.commit_field_edits()

        if row < 0 or row >= len(self.runners):
            return

        self.current_runner = self.runners[row]
        self.populate_steps()
        self.show_macro_props()
        self.update_undo_redo_state()

    def on_step_selected(self, row: int) -> None:
        self.commit_field_edits()

        if not self.current_runner:
            return

        if row < 0 or row >= len(getattr(self, "flat_steps", [])):
            self.show_macro_props()
            return

        self.show_props(self.flat_steps[row])

    def show_macro_props(self) -> None:
        self.clear_props()

        if not self.current_runner:
            return

        self.prop_title.setText(t("prop.macro_props"))

        lbl = BodyLabel(t("prop.target_window"))
        self.prop_fields_layout.addWidget(lbl)

        combo = ComboBox()
        combo.blockSignals(True)
        combo.addItem(t("prop.target_window_foreground"), "")

        for title in window.list_visible_windows():
            combo.addItem(title, title)

        current = self.current_runner.target_window
        idx = combo.findData(current)

        if idx < 0 and current:
            combo.addItem(current, current)
            idx = combo.count() - 1

        if idx >= 0:
            combo.setCurrentIndex(idx)
        combo.blockSignals(False)

        combo.currentIndexChanged.connect(lambda: self.on_target_window_combo(combo))
        self.prop_fields_layout.addWidget(combo)

        lbl_hotkey = BodyLabel(t("prop.hotkey"))
        self.prop_fields_layout.addWidget(lbl_hotkey)

        hotkey_edit = LineEdit()

        hotkey_edit.setText(self.current_runner.macro.get("meta", {}).get("hotkey", ""))
        hotkey_edit.setPlaceholderText(t("prop.hotkey_placeholder"))
        hotkey_edit.setReadOnly(True)
        hotkey_edit.setClearButtonEnabled(True)
        hotkey_edit.textChanged.connect(lambda txt: self.set_macro_hotkey(txt) if not txt else None)
        hotkey_edit.keyPressEvent = lambda e: self.on_hotkey_capture(e, hotkey_edit)
        self.prop_fields_layout.addWidget(hotkey_edit)

        enabled_checkbox = CheckBox(t("prop.enabled"))
        enabled_checkbox.setChecked(self.current_runner.macro.get("meta", {}).get("enabled", True))
        enabled_checkbox.toggled.connect(self.on_enabled_toggled)
        self.prop_fields_layout.addWidget(enabled_checkbox)

    def on_hotkey_capture(self, event: QKeyEvent, edit: LineEdit) -> None:
        key = event.key()

        if key in (Qt.Key.Key_Escape,):
            edit.setText("")
            self.set_macro_hotkey("")
            return

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
        self.set_macro_hotkey(hotkey_str)

    def set_macro_hotkey(self, hotkey: str) -> None:
        if not self.current_runner:
            return

        self.current_runner.macro.setdefault("meta", {})["hotkey"] = hotkey
        self.save_current_macro()
        self.register_hotkeys()

    def on_enabled_toggled(self, checked: bool) -> None:
        if not self.current_runner:
            return

        self.current_runner.macro.setdefault("meta", {})["enabled"] = checked
        self.save_current_macro()
        self.register_hotkeys()

    def on_target_window_combo(self, combo: ComboBox) -> None:
        if not self.current_runner:
            return

        value = combo.currentData() or ""

        self.current_runner.macro["meta"]["target_window"] = value
        self.current_runner.target_window = value
        self.save_current_macro()

    def populate_steps(self) -> None:
        self.step_list.clear()
        self.flat_steps: list[dict] = []
        self.flat_parents: list[list[dict]] = []

        if not self.current_runner:
            self.update_empty_states()
            return

        steps = self.current_runner.macro.get("steps", [])

        self.add_steps_to_list(steps, steps, indent=0)
        self.update_empty_states()

    def add_steps_to_list(self, steps: list[dict], parent: list[dict], indent: int) -> None:
        for step in steps:
            self.flat_steps.append(step)
            self.flat_parents.append(parent)

            idx = len(self.flat_steps)
            icon, summary = self.step_display(step)
            prefix = "       " * indent
            text = f"{prefix}{summary}"
            item = QListWidgetItem(f"{idx:>3}   {text}")

            if icon:
                item.setIcon(icon)

            self.step_list.addItem(item)

            if step.get("type") == "repeat":
                sub = step.get("steps", [])
                self.add_steps_to_list(sub, sub, indent + 1)

            elif step.get("type") in ("if_image", "if_any_image"):
                for sub in step.get("then", []):
                    self.flat_steps.append(sub)
                    self.flat_parents.append(step.get("then", []))
                    sub_idx = len(self.flat_steps)
                    sub_icon, sub_summary = self.step_display(sub)
                    item = QListWidgetItem(
                        f"{sub_idx:>3}   {'    ' * (indent + 1)}[{t('step.branch.match')}] {sub_summary}"
                    )

                    if sub_icon:
                        item.setIcon(sub_icon)

                    self.step_list.addItem(item)

                for sub in step.get("else", []):
                    self.flat_steps.append(sub)
                    self.flat_parents.append(step.get("else", []))
                    sub_idx = len(self.flat_steps)
                    sub_icon, sub_summary = self.step_display(sub)
                    item = QListWidgetItem(
                        f"{sub_idx:>3}   {'    ' * (indent + 1)}[{t('step.branch.else')}] {sub_summary}"
                    )

                    if sub_icon:
                        item.setIcon(sub_icon)

                    self.step_list.addItem(item)

                for branch_key, branch_steps in step.get("branches", {}).items():
                    label = self.template_label(branch_key)

                    for sub in branch_steps:
                        self.flat_steps.append(sub)
                        self.flat_parents.append(branch_steps)
                        sub_idx = len(self.flat_steps)
                        sub_icon, sub_summary = self.step_display(sub)
                        item = QListWidgetItem(f"{sub_idx:>3}   {'    ' * (indent + 1)}[{label}] {sub_summary}")

                        if sub_icon:
                            item.setIcon(sub_icon)

                        self.step_list.addItem(item)

            elif step.get("type") == "grid_nav":
                for sub in step.get("on_next_row", []):
                    self.flat_steps.append(sub)
                    self.flat_parents.append(step.get("on_next_row", []))
                    sub_idx = len(self.flat_steps)
                    sub_icon, sub_summary = self.step_display(sub)
                    item = QListWidgetItem(
                        f"{sub_idx:>3}   {'    ' * (indent + 1)}[{t('step.branch.next_row')}] {sub_summary}"
                    )

                    if sub_icon:
                        item.setIcon(sub_icon)

                    self.step_list.addItem(item)

                for sub in step.get("on_next_col", []):
                    self.flat_steps.append(sub)
                    self.flat_parents.append(step.get("on_next_col", []))
                    sub_idx = len(self.flat_steps)
                    sub_icon, sub_summary = self.step_display(sub)
                    item = QListWidgetItem(
                        f"{sub_idx:>3}   {'    ' * (indent + 1)}[{t('step.branch.next_col')}] {sub_summary}"
                    )

                    if sub_icon:
                        item.setIcon(sub_icon)

                    self.step_list.addItem(item)

    def step_display(self, step: dict) -> tuple[QIcon | None, str]:
        step_type = step.get("type", "?")

        icons = {
            "wait_image": icon("image"),
            "key": icon("keyboard"),
            "delay": icon("timer"),
            "repeat": icon("repeat"),
            "foreground": icon("app-window"),
            "hold_key_until_gone": icon("keyboard"),
            "if_image": icon("git-branch"),
            "if_any_image": icon("git-merge"),
            "grid_nav": icon("layout-grid"),
        }

        summaries = {
            "key": lambda s: t("step.summary.key", key=s.get("key", "")),
            "delay": lambda s: t("step.summary.delay", ms=s.get("ms", 0)),
            "wait_image": lambda s: t("step.summary.wait_image", template=self.template_label(s.get("template", ""))),
            "foreground": lambda s: t("step.summary.foreground"),
            "repeat": lambda s: t("step.summary.repeat", count=s.get("count", "?")),
            "hold_key_until_gone": lambda s: t(
                "step.summary.hold_key_until_gone",
                key=s.get("key", ""),
                template=self.template_label(s.get("template", "")),
            ),
            "if_image": lambda s: t("step.summary.if_image", template=self.template_label(s.get("template", ""))),
            "if_any_image": lambda s: t("step.summary.if_any_image"),
            "grid_nav": lambda s: t("step.summary.grid_nav"),
        }

        step_icon = icons.get(step_type)
        fn = summaries.get(step_type)
        summary = fn(step) if fn else step_type

        return step_icon, summary

    def show_props(self, step: dict) -> None:
        self.clear_props()

        step_type = step.get("type", "?")
        _, summary = self.step_display(step)

        self.prop_title.setText(summary.split("  ")[0] if "  " in summary else summary)

        skip_checkbox = CheckBox(t("prop.skip"))
        skip_checkbox.setChecked(bool(step.get("skip", False)))
        skip_checkbox.toggled.connect(lambda checked: self.on_prop_bool(step, "skip", checked))
        self.prop_fields_layout.addWidget(skip_checkbox)

        if step_type == "wait_image":
            self.show_wait_image_props(step)
            return

        if step_type == "if_image":
            self.show_if_image_props(step)
            return

        if step_type == "if_any_image":
            self.show_if_any_image_props(step)
            return

        if step_type == "hold_key_until_gone":
            self.show_hold_key_props(step)
            return

        if step_type == "grid_nav":
            self.show_grid_nav_props(step)
            return

        editable = {
            "key": [("key", t("prop.key")), ("hold_ms", t("prop.hold_ms"))],
            "delay": [("ms", t("prop.delay_ms"))],
            "repeat": [("count", t("prop.count"))],
        }

        fields = editable.get(step_type, [])

        for key, label in fields:
            lbl = BodyLabel(label)
            self.prop_fields_layout.addWidget(lbl)

            edit = LineEdit()

            edit.setText(str(step.get(key, "")))
            edit.editingFinished.connect(lambda step=step, key=key, edit=edit: self.on_prop_edit(step, key, edit))
            self.prop_fields_layout.addWidget(edit)

    def template_preview(self, template_name: str) -> BodyLabel:
        """Create a template image preview label; shows a placeholder icon if image doesn't exist."""
        preview = BodyLabel()
        preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview.setMinimumWidth(1)

        if template_name:
            path = self.macro_templates_dir / f"{template_name}.png"

            if path.exists():
                pixmap = QPixmap(str(path))

                max_w = self.right_panel.width() - 20

                if pixmap.width() > max_w:
                    pixmap = pixmap.scaledToWidth(max_w, Qt.TransformationMode.SmoothTransformation)

                preview.setPixmap(pixmap)

                return preview

        preview.setFixedHeight(120)
        preview.setPixmap(icon("image").pixmap(48, 48))

        return preview

    def template_controls(self, step: dict, template_name: str, layout: QVBoxLayout) -> None:
        """Add template name edit, capture, pick, and delete buttons to the given layout."""
        if template_name:
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)

            name_edit = LineEdit()
            name_edit.setText(self.template_label(template_name))
            name_edit.editingFinished.connect(lambda: self.on_rename_template(step, name_edit))
            row_layout.addWidget(name_edit, 1)
            layout.addWidget(row_widget)

        btn_capture = PushButton(t("action.capture"))
        btn_capture.clicked.connect(lambda: self.on_capture_template(step))
        layout.addWidget(btn_capture)

        btn_pick = PushButton(t("action.pick_image"))
        btn_pick.clicked.connect(lambda: self.on_pick_template(step))
        layout.addWidget(btn_pick)

        if template_name:
            btn_del = PushButton(t("action.delete_template"))
            btn_del.clicked.connect(lambda: self.on_delete_template(step))
            layout.addWidget(btn_del)

    def show_wait_image_props(self, step: dict) -> None:
        """wait_image property panel: image preview, capture button, similarity slider."""
        layout = self.prop_fields_layout
        template_name = step.get("template", "")

        lbl = BodyLabel(t("prop.template"))
        layout.addWidget(lbl)

        preview = self.template_preview(template_name)
        layout.addWidget(preview)

        self.template_controls(step, template_name, layout)

        threshold = step.get("threshold")

        if threshold is None:
            threshold = cfg.DEFAULT_THRESHOLD

        percentage = round(threshold * 100)

        slider_lbl = BodyLabel(t("prop.similarity", value=percentage))
        layout.addWidget(slider_lbl)

        slider = Slider(Qt.Orientation.Horizontal)
        slider.setRange(0, 100)
        slider.setValue(percentage)
        slider.valueChanged.connect(lambda value: self.on_threshold_changed(step, value, slider_lbl))
        layout.addWidget(slider)

        timeout_lbl = BodyLabel(t("prop.timeout_ms"))
        layout.addWidget(timeout_lbl)

        timeout_edit = LineEdit()
        timeout_edit.setText(str(step.get("timeout_ms", 5000)))
        timeout_edit.editingFinished.connect(lambda: self.on_prop_edit(step, "timeout_ms", timeout_edit))
        layout.addWidget(timeout_edit)

    def show_if_image_props(self, step: dict) -> None:
        """if_image property panel: image preview, capture button, timeout, then/else step counts."""
        layout = self.prop_fields_layout
        template_name = step.get("template", "")

        lbl = BodyLabel(t("prop.template"))
        layout.addWidget(lbl)

        preview = self.template_preview(template_name)
        layout.addWidget(preview)

        self.template_controls(step, template_name, layout)

        timeout_lbl = BodyLabel(t("prop.timeout_ms"))
        layout.addWidget(timeout_lbl)

        timeout_edit = LineEdit()
        timeout_edit.setText(str(step.get("timeout_ms", 3000)))
        timeout_edit.editingFinished.connect(lambda: self.on_prop_edit(step, "timeout_ms", timeout_edit))
        layout.addWidget(timeout_edit)

        then_count = len(step.get("then", []))
        else_count = len(step.get("else", []))

        then_lbl = BodyLabel(t("step.branch.match_count", count=then_count))
        layout.addWidget(then_lbl)

        btn_add_then = PushButton(icon("plus"), t("action.add"))
        btn_add_then.clicked.connect(lambda: self.add_step_to_branch(step, "then"))
        layout.addWidget(btn_add_then)

        else_lbl = BodyLabel(t("step.branch.else_count", count=else_count))
        layout.addWidget(else_lbl)

        btn_add_else = PushButton(icon("plus"), t("action.add"))
        btn_add_else.clicked.connect(lambda: self.add_step_to_branch(step, "else"))
        layout.addWidget(btn_add_else)

    def show_grid_nav_props(self, step: dict) -> None:
        """grid_nav property panel: rows, start position, next row action, next column action."""
        layout = self.prop_fields_layout

        col_lbl = BodyLabel(t("prop.rows"))
        layout.addWidget(col_lbl)

        col_edit = LineEdit()
        col_edit.setText(str(step.get("rows", 3)))
        col_edit.editingFinished.connect(lambda: self.on_prop_edit(step, "rows", col_edit))
        layout.addWidget(col_edit)

        start_lbl = BodyLabel(t("prop.start_cell"))
        layout.addWidget(start_lbl)

        start_edit = LineEdit()
        start_edit.setText(str(step.get("start", 0) + 1))
        start_edit.editingFinished.connect(lambda: self.on_grid_nav_start_edit(step, start_edit))
        layout.addWidget(start_edit)

        next_row_count = len(step.get("on_next_row", []))
        same_lbl = BodyLabel(t("step.branch.next_row_count", count=next_row_count))
        layout.addWidget(same_lbl)

        btn_add_same = PushButton(icon("plus"), t("action.add"))
        btn_add_same.clicked.connect(lambda: self.add_step_to_branch(step, "on_next_row"))
        layout.addWidget(btn_add_same)

        next_col_count = len(step.get("on_next_col", []))
        end_lbl = BodyLabel(t("step.branch.next_col_count", count=next_col_count))
        layout.addWidget(end_lbl)

        btn_add_end = PushButton(icon("plus"), t("action.add"))
        btn_add_end.clicked.connect(lambda: self.add_step_to_branch(step, "on_next_col"))
        layout.addWidget(btn_add_end)

    def show_if_any_image_props(self, step: dict) -> None:
        """if_any_image property panel: each template can capture/pick image, collapsible."""
        layout = self.prop_fields_layout
        templates = step.get("templates", [])
        expand_idx = getattr(self, "any_image_expand_idx", -1)
        self.any_image_expand_idx = -1

        timeout_lbl = BodyLabel(t("prop.timeout_ms"))
        layout.addWidget(timeout_lbl)

        timeout_edit = LineEdit()
        timeout_edit.setText(str(step.get("timeout_ms", 5000)))
        timeout_edit.editingFinished.connect(lambda: self.on_prop_edit(step, "timeout_ms", timeout_edit))
        layout.addWidget(timeout_edit)

        for idx, name in enumerate(templates):
            if not name:
                continue

            expanded = idx == expand_idx
            header = QWidget()
            header.setCursor(Qt.CursorShape.PointingHandCursor)
            header_layout = QHBoxLayout(header)
            header_layout.setContentsMargins(4, 4, 4, 4)
            header_layout.setSpacing(4)
            chevron_label = BodyLabel()
            chevron_label.setFixedSize(12, 12)
            pixmap = icon("chevron-down" if expanded else "chevron-right").pixmap(12, 12)
            chevron_label.setPixmap(pixmap)
            header_layout.addWidget(chevron_label)
            header_layout.addWidget(BodyLabel(self.template_label(name)))
            header_layout.addStretch()
            content = QWidget()
            content_layout = QVBoxLayout(content)
            content_layout.setContentsMargins(0, 4, 0, 0)
            content_layout.setSpacing(12)
            content.setVisible(expanded)

            def toggle(event=None, lbl=chevron_label, w=content):
                visible = not w.isVisible()
                w.setVisible(visible)
                lbl.setPixmap(icon("chevron-down" if visible else "chevron-right").pixmap(12, 12))

            header.mousePressEvent = toggle
            layout.addWidget(header)

            preview = self.template_preview(name)
            content_layout.addWidget(preview)

            name_edit = LineEdit()
            name_edit.setText(self.template_label(name))
            name_edit.editingFinished.connect(lambda i=idx, edit=name_edit: self.on_rename_any_template(step, i, edit))
            content_layout.addWidget(name_edit)

            btn_capture = PushButton(t("action.capture"))
            btn_capture.clicked.connect(lambda checked=False, i=idx: self.on_capture_any_template(step, i))
            content_layout.addWidget(btn_capture)

            btn_pick = PushButton(t("action.pick_image"))
            btn_pick.clicked.connect(lambda checked=False, i=idx: self.on_pick_any_template(step, i))
            content_layout.addWidget(btn_pick)

            btn_del = PushButton(t("action.delete_template"))
            btn_del.clicked.connect(lambda checked=False, i=idx: self.on_delete_any_template(step, i))
            content_layout.addWidget(btn_del)

            branch_steps = step.get("branches", {}).get(name, [])
            branch_lbl = BodyLabel(t("step.branch.on_match_count", count=len(branch_steps)))
            content_layout.addWidget(branch_lbl)

            btn_add_branch = PushButton(icon("plus"), t("action.add"))
            btn_add_branch.clicked.connect(lambda checked=False, n=name: self.add_step_to_any_branch(step, n))
            content_layout.addWidget(btn_add_branch)

            layout.addWidget(content)

        btn_add = PushButton(icon("plus"), t("action.add_template"))
        btn_add.clicked.connect(lambda: self.on_add_any_template(step))
        layout.addWidget(btn_add)

        threshold = step.get("threshold")

        if threshold is None:
            threshold = cfg.DEFAULT_THRESHOLD

        percentage = round(threshold * 100)
        slider_lbl = BodyLabel(t("prop.similarity", value=percentage))
        layout.addWidget(slider_lbl)
        slider = Slider(Qt.Orientation.Horizontal)
        slider.setRange(0, 100)
        slider.setValue(percentage)
        slider.valueChanged.connect(lambda value: self.on_threshold_changed(step, value, slider_lbl))
        layout.addWidget(slider)

        on_timeout_lbl = BodyLabel(t("prop.timeout_action"))
        layout.addWidget(on_timeout_lbl)

        timeout_combo = ComboBox()
        timeout_combo.addItems(["stop", "continue"])
        timeout_combo.setCurrentText(step.get("on_timeout", "stop"))
        timeout_combo.currentTextChanged.connect(lambda v: self.on_combo_edit(step, "on_timeout", v))
        layout.addWidget(timeout_combo)

    def on_capture_any_template(self, step: dict, idx: int) -> None:
        """Capture screen and save to the specified template slot in if_any_image."""
        self.showMinimized()

        QTimer.singleShot(200, lambda: self.launch_any_selector(step, idx))

    def launch_any_selector(self, step: dict, idx: int) -> None:
        self.selector = RegionSelector(self.current_runner.name if self.current_runner else "")
        self.selector.region_selected.connect(lambda name: self.on_any_region_captured(step, idx, name))
        self.selector.cancelled.connect(self.showNormal)
        self.selector.start()

    def on_any_region_captured(self, step: dict, idx: int, name: str) -> None:
        templates = step.get("templates", [])
        old_name = templates[idx] if idx < len(templates) else ""

        if old_name and old_name != name:
            old_path = self.macro_templates_dir / f"{old_name}.png"

            if old_path.exists():
                old_path.unlink()

            old_meta = self.macro_templates_dir / f"{old_name}.json"

            if old_meta.exists():
                old_meta.unlink()

        step["templates"][idx] = name
        self.sync_macro_templates()
        self.save_current_macro()
        self.showNormal()
        self.any_image_expand_idx = idx
        self.refresh_current_step()
        self.step_list.setFocus()

    def on_pick_any_template(self, step: dict, idx: int) -> None:
        """Pick an image file as the specified template in if_any_image."""
        path, _ = QFileDialog.getOpenFileName(self, t("dialog.select_image"), "", t("dialog.png_filter"))

        if not path:
            return

        template_name = f"{int(time.time())}"
        destination = self.macro_templates_dir / f"{template_name}.png"
        shutil.copy2(path, destination)
        step["templates"][idx] = template_name

        self.sync_macro_templates()
        self.save_current_macro()
        self.any_image_expand_idx = idx
        self.refresh_current_step()

    def on_rename_any_template(self, step: dict, idx: int, edit: LineEdit) -> None:
        """Rename the label of a specified template in if_any_image."""
        templates = step.get("templates", [])
        name = templates[idx] if idx < len(templates) else ""
        new_label = edit.text().strip()

        if not new_label or not name:
            return

        macro_templates = self.current_runner.macro.get("templates", {}) if self.current_runner else {}
        macro_templates.setdefault(name, {})["label"] = new_label

        self.save_current_macro()
        self.any_image_expand_idx = idx
        self.refresh_current_step()

    def on_delete_any_template(self, step: dict, idx: int) -> None:
        """Delete the specified template from if_any_image."""
        templates = step.get("templates", [])

        if idx >= len(templates):
            return

        name = templates.pop(idx)

        if name:
            path = self.macro_templates_dir / f"{name}.png"
            if path.exists():
                path.unlink()

        branches = step.get("branches", {})
        branches.pop(name, None)

        self.sync_macro_templates()
        self.save_current_macro()
        self.refresh_current_step()

    def add_step_to_any_branch(self, parent_step: dict, template_name: str) -> None:
        """Add a step to the specified template branch in if_any_image."""
        templates = [
            (t("step.type.key"), {"type": "key", "key": "enter", "hold_ms": 90}),
            (t("step.type.delay"), {"type": "delay", "ms": 500}),
            (
                t("step.type.wait_image"),
                {"type": "wait_image", "template": "", "timeout_ms": 5000, "on_timeout": "stop"},
            ),
            (t("step.type.foreground"), {"type": "foreground"}),
        ]

        menu = RoundMenu(parent=self)

        for label, template in templates:
            menu.addAction(
                Action(
                    label,
                    triggered=lambda _, t=template: self.do_add_step_to_any_branch(
                        parent_step, template_name, copy.deepcopy(t)
                    ),
                )
            )

        menu.exec(QCursor.pos())

    def do_add_step_to_any_branch(self, parent_step: dict, template_name: str, step: dict) -> None:
        branches = parent_step.setdefault("branches", {})
        branches.setdefault(template_name, []).append(step)

        self.sync_macro_templates()
        self.save_current_macro()
        self.populate_steps()

        idx = parent_step.get("templates", []).index(template_name)

        self.any_image_expand_idx = idx
        self.refresh_current_step()

    def on_add_any_template(self, step: dict) -> None:
        """Add an empty template to if_any_image."""
        placeholder = f"{int(time.time())}"
        step.setdefault("templates", []).append(placeholder)

        self.sync_macro_templates()
        self.save_current_macro()
        self.any_image_expand_idx = len(step["templates"]) - 1
        self.refresh_current_step()

    def refresh_current_step(self) -> None:
        """Re-render the currently selected step's property panel."""
        row = self.step_list.currentRow()

        self.populate_steps()

        if 0 <= row < self.step_list.count():
            self.step_list.setCurrentRow(row)

    def show_hold_key_props(self, step: dict) -> None:
        """hold_key_until_gone property panel."""
        layout = self.prop_fields_layout
        template_name = step.get("template", "")

        key_lbl = BodyLabel(t("prop.key"))
        layout.addWidget(key_lbl)

        key_edit = LineEdit()
        key_edit.setText(str(step.get("key", "")))
        key_edit.editingFinished.connect(lambda: self.on_prop_edit(step, "key", key_edit))
        layout.addWidget(key_edit)

        lbl = BodyLabel(t("prop.template"))
        layout.addWidget(lbl)

        preview = self.template_preview(template_name)
        layout.addWidget(preview)

        self.template_controls(step, template_name, layout)

        threshold = step.get("threshold")

        if threshold is None:
            threshold = cfg.DEFAULT_THRESHOLD

        percentage = round(threshold * 100)
        slider_lbl = BodyLabel(t("prop.similarity", value=percentage))
        layout.addWidget(slider_lbl)

        slider = Slider(Qt.Orientation.Horizontal)
        slider.setRange(0, 100)
        slider.setValue(percentage)
        slider.valueChanged.connect(lambda value: self.on_threshold_changed(step, value, slider_lbl))
        layout.addWidget(slider)

        fields = [
            ("load_delay_ms", t("prop.load_delay_ms")),
            ("find_timeout_ms", t("prop.find_timeout_ms")),
            ("gone_grace_ms", t("prop.gone_grace_ms")),
            ("hard_timeout_ms", t("prop.hard_timeout_ms")),
        ]

        for key, label in fields:
            field_lbl = BodyLabel(label)
            layout.addWidget(field_lbl)
            edit = LineEdit()
            edit.setText(str(step.get(key, "")))
            edit.editingFinished.connect(lambda s=step, k=key, e=edit: self.on_prop_edit(s, k, e))
            layout.addWidget(edit)

    def on_threshold_changed(self, step: dict, value: int, label: BodyLabel) -> None:
        label.setText(t("prop.similarity", value=value))
        step["threshold"] = round(value / 100, 2)

        self.save_current_macro()

    def on_capture_template(self, step: dict) -> None:
        self.showMinimized()

        QTimer.singleShot(200, lambda: self.launch_selector(step))

    def launch_selector(self, step: dict) -> None:
        self.selector = RegionSelector(self.current_runner.name if self.current_runner else "")
        self.selector.region_selected.connect(lambda name: self.on_region_captured(step, name))
        self.selector.cancelled.connect(self.showNormal)
        self.selector.start()

    def on_region_captured(self, step: dict, name: str) -> None:
        old_name = step.get("template", "")
        if old_name and old_name != name:
            old_path = self.macro_templates_dir / f"{old_name}.png"
            if old_path.exists():
                old_path.unlink()
            old_meta = self.macro_templates_dir / f"{old_name}.json"
            if old_meta.exists():
                old_meta.unlink()

        step["template"] = name
        self.sync_macro_templates()
        self.save_current_macro()
        self.showNormal()
        row = self.step_list.currentRow()
        self.populate_steps()

        if 0 <= row < self.step_list.count():
            self.step_list.setCurrentRow(row)

        self.step_list.setFocus()

    def on_pick_template(self, step: dict) -> None:
        """Let user pick a PNG image from the file system as a match template."""
        path, _ = QFileDialog.getOpenFileName(self, t("dialog.select_image"), "", t("dialog.png_filter"))
        if not path:
            return

        template_name = step.get("template", "")
        if not template_name:
            template_name = f"{int(time.time())}"
            step["template"] = template_name

        destination = self.macro_templates_dir / f"{template_name}.png"
        shutil.copy2(path, destination)

        self.sync_macro_templates()
        self.save_current_macro()
        self.populate_steps()

        if any(s is step for s in self.flat_steps):
            row = next(i for i, s in enumerate(self.flat_steps) if s is step)
            self.step_list.setCurrentRow(row)

    def on_rename_template(self, step: dict, edit: LineEdit) -> None:
        name = step.get("template", "")
        new_label = edit.text().strip()
        if not new_label or not name:
            return

        templates = self.current_runner.macro.get("templates", {}) if self.current_runner else {}
        templates.setdefault(name, {})["label"] = new_label
        self.save_current_macro()
        row = self.step_list.currentRow()
        self.populate_steps()

        if 0 <= row < self.step_list.count():
            self.step_list.setCurrentRow(row)

    def on_delete_template(self, step: dict) -> None:
        name = step.get("template", "")

        if not name:
            return

        path = self.macro_templates_dir / f"{name}.png"
        if path.exists():
            path.unlink()

        step["template"] = ""

        self.sync_macro_templates()
        self.save_current_macro()
        self.populate_steps()

        if any(s is step for s in self.flat_steps):
            row = next(i for i, s in enumerate(self.flat_steps) if s is step)
            self.step_list.setCurrentRow(row)

    def template_label(self, name: str) -> str:
        """Get the display name of a template."""
        if not self.current_runner:
            return name

        template = self.current_runner.macro.get("templates", {}).get(name, {})

        return template.get("label", name)

    def sync_macro_templates(self) -> None:
        """Rebuild macro["templates"] to only keep template names actually referenced by steps."""
        if not self.current_runner:
            return

        macro = self.current_runner.macro
        used: set[str] = set()

        self.collect_template_refs(macro.get("steps", []), used)

        existing = macro.get("templates", {})
        macro["templates"] = {name: existing.get(name, {"label": name}) for name in used}

        self.current_runner.template_names = list(used)

    def collect_template_refs(self, steps: list[dict], out: set) -> None:
        for step in steps:
            if template_name := step.get("template"):
                out.add(template_name)
            for template_name in step.get("templates", []):
                out.add(template_name)
            for key in ("steps", "then", "else", "on_next_row", "on_next_col"):
                if sub := step.get(key):
                    self.collect_template_refs(sub, out)
            for branch in step.get("branches", {}).values():
                self.collect_template_refs(branch, out)

    def on_prop_bool(self, step: dict, key: str, checked: bool) -> None:
        step[key] = checked
        self.save_current_macro()

    def on_combo_edit(self, step: dict, key: str, value: str) -> None:
        step[key] = value
        self.save_current_macro()

    def on_prop_edit(self, step: dict, key: str, edit: LineEdit) -> None:
        value: str | int | float = edit.text()

        if key == "key" and value not in pdi.KEYBOARD_MAPPING:
            return

        numeric_keys = (
            "ms",
            "hold_ms",
            "count",
            "timeout_ms",
            "columns",
            "rows",
            "load_delay_ms",
            "find_timeout_ms",
            "gone_grace_ms",
            "hard_timeout_ms",
        )
        if key in numeric_keys:
            try:
                value = int(value)
            except ValueError:
                return
        else:
            try:
                value = int(value)
            except ValueError:
                with contextlib.suppress(ValueError):
                    value = float(value)

        step[key] = value
        self.save_current_macro()
        row = self.step_list.currentRow()
        self.populate_steps()

        if row >= 0 and row < self.step_list.count():
            self.step_list.setCurrentRow(row)

    def on_grid_nav_start_edit(self, step: dict, edit: LineEdit) -> None:
        try:
            val = int(edit.text()) - 1
        except ValueError:
            return

        step["start"] = max(0, val)
        self.save_current_macro()
        row = self.step_list.currentRow()
        self.populate_steps()

        if row >= 0 and row < self.step_list.count():
            self.step_list.setCurrentRow(row)

    def clear_props(self) -> None:
        while self.prop_fields_layout.count():
            item = self.prop_fields_layout.takeAt(0)

            if item is None:
                continue

            widget = item.widget()

            if widget:
                widget.deleteLater()
            elif item.layout():
                while item.layout().count():
                    child = item.layout().takeAt(0)
                    if child:
                        child_widget = child.widget()
                        if child_widget:
                            child_widget.deleteLater()

        self.prop_title.setText(t("step.props_title"))

    def push_undo(self) -> None:
        """Push the pre-mutation snapshot onto the undo stack."""
        if not self.current_runner:
            return

        snapshot = getattr(self.current_runner, "last_snapshot", None)

        if snapshot is None:
            return

        stack = self.current_runner.undo_stack
        stack.append(snapshot)

        if len(stack) > 50:
            stack.pop(0)

        self.current_runner.redo_stack.clear()
        self.update_undo_redo_state()

    def undo(self) -> None:
        if not self.current_runner or not self.current_runner.undo_stack:
            return

        row = self.step_list.currentRow()

        self.current_runner.redo_stack.append(copy.deepcopy(self.current_runner.macro))
        self.current_runner.macro = self.current_runner.undo_stack.pop()
        self.current_runner.last_snapshot = copy.deepcopy(self.current_runner.macro)
        self.save_runner(self.current_runner)
        self.on_macro_selected(self.macro_list.currentRow())

        if self.step_list.count():
            self.step_list.setCurrentRow(min(row, self.step_list.count() - 1))

        self.update_undo_redo_state()

    def redo(self) -> None:
        if not self.current_runner or not self.current_runner.redo_stack:
            return

        self.current_runner.undo_stack.append(copy.deepcopy(self.current_runner.macro))
        self.current_runner.macro = self.current_runner.redo_stack.pop()
        self.current_runner.last_snapshot = copy.deepcopy(self.current_runner.macro)
        self.save_runner(self.current_runner)
        self.on_macro_selected(self.macro_list.currentRow())
        self.update_undo_redo_state()

    def update_undo_redo_state(self) -> None:
        has_undo = bool(self.current_runner and self.current_runner.undo_stack)
        has_redo = bool(self.current_runner and self.current_runner.redo_stack)
        self.btn_undo.setEnabled(has_undo)
        self.btn_redo.setEnabled(has_redo)

    def save_current_macro(self) -> None:
        if not self.current_runner:
            return

        self.push_undo()
        self.current_runner.last_snapshot = copy.deepcopy(self.current_runner.macro)
        self.save_runner(self.current_runner)

    def on_add_step(self) -> None:
        templates = [
            (t("step.type.key"), {"type": "key", "key": "enter", "hold_ms": 90}),
            (t("step.type.delay"), {"type": "delay", "ms": 500}),
            (
                t("step.type.wait_image"),
                {"type": "wait_image", "template": "", "timeout_ms": 5000, "on_timeout": "stop"},
            ),
            (t("step.type.if_image"), {"type": "if_image", "template": "", "timeout_ms": 3000, "then": [], "else": []}),
            (
                t("step.type.if_any_image"),
                {"type": "if_any_image", "templates": [], "timeout_ms": 5000, "on_timeout": "stop", "branches": {}},
            ),
            (t("step.type.foreground"), {"type": "foreground"}),
            (
                t("step.type.hold_key_until_gone"),
                {
                    "type": "hold_key_until_gone",
                    "key": "w",
                    "template": "",
                    "load_delay_ms": 2000,
                    "find_timeout_ms": 15000,
                    "gone_grace_ms": 1500,
                    "hard_timeout_ms": 180000,
                },
            ),
            (t("step.type.repeat"), {"type": "repeat", "count": 1, "steps": []}),
            (
                t("step.type.grid_nav"),
                {"type": "grid_nav", "rows": 3, "start": 0, "on_next_row": [], "on_next_col": []},
            ),
        ]

        menu = RoundMenu(parent=self)

        for label, template in templates:
            menu.addAction(Action(label, triggered=lambda _, t=template: self.do_add_step(copy.deepcopy(t))))

        menu.exec(self.btn_add_step.mapToGlobal(self.btn_add_step.rect().bottomLeft()))

    def add_step_to_branch(self, parent_step: dict, branch: str) -> None:
        templates = [
            (t("step.type.key"), {"type": "key", "key": "enter", "hold_ms": 90}),
            (t("step.type.delay"), {"type": "delay", "ms": 500}),
            (
                t("step.type.wait_image"),
                {"type": "wait_image", "template": "", "timeout_ms": 5000, "on_timeout": "stop"},
            ),
            (t("step.type.foreground"), {"type": "foreground"}),
        ]

        menu = RoundMenu(parent=self)

        for label, template in templates:
            menu.addAction(
                Action(
                    label,
                    triggered=lambda _, t=template: self.do_add_step_to_branch(parent_step, branch, copy.deepcopy(t)),
                )
            )

        menu.exec(QCursor.pos())

    def do_add_step_to_branch(self, parent_step: dict, branch: str, step: dict) -> None:
        parent_step.setdefault(branch, []).append(step)
        self.save_current_macro()
        self.populate_steps()
        new_row = next((i for i, s in enumerate(self.flat_steps) if s is step), -1)

        if new_row >= 0:
            self.step_list.setCurrentRow(new_row)

    def do_add_step(self, step: dict) -> None:
        if not self.current_runner:
            return

        row = self.step_list.currentRow()

        if row >= 0 and row < len(self.flat_steps):
            selected = self.flat_steps[row]
            if selected.get("type") == "repeat":
                selected.setdefault("steps", []).append(step)
            elif selected.get("type") in ("if_image", "if_any_image"):
                selected.setdefault("then", []).append(step)
            else:
                parent = self.flat_parents[row]
                idx = next(i for i, s in enumerate(parent) if s is selected) + 1
                parent.insert(idx, step)
        else:
            self.current_runner.macro.get("steps", []).append(step)

        self.save_current_macro()
        self.populate_steps()

        new_row = next((i for i, s in enumerate(self.flat_steps) if s is step), -1)

        if new_row >= 0:
            self.step_list.setCurrentRow(new_row)

    def on_delete_step(self) -> None:
        if not self.current_runner:
            return

        rows = sorted(idx.row() for idx in self.step_list.selectedIndexes())

        if not rows:
            return

        for row in reversed(rows):
            if row >= len(self.flat_steps):
                continue

            step = self.flat_steps[row]
            parent = self.flat_parents[row]
            idx = next((i for i, s in enumerate(parent) if s is step), -1)

            if idx >= 0:
                parent.pop(idx)

        self.sync_macro_templates()
        self.save_current_macro()
        self.populate_steps()

        if self.step_list.count():
            self.step_list.setCurrentRow(min(rows[0], self.step_list.count() - 1))
        else:
            self.step_list.clearSelection()

    def copy_steps(self) -> None:
        if not self.current_runner:
            return

        rows = sorted(idx.row() for idx in self.step_list.selectedIndexes())

        if not rows:
            return

        steps = [copy.deepcopy(self.flat_steps[r]) for r in rows if r < len(self.flat_steps)]

        if not steps:
            return

        refs: set[str] = set()
        self.collect_template_refs(steps, refs)

        templates_dir = self.macro_templates_dir
        template_data: dict[str, bytes] = {}

        for name in refs:
            path = templates_dir / f"{name}.png"
            if path.exists():
                template_data[name] = path.read_bytes()

        macro_templates = self.current_runner.macro.get("templates", {})
        template_meta = {name: copy.deepcopy(macro_templates[name]) for name in refs if name in macro_templates}

        self.step_clipboard = {
            "steps": steps,
            "templates": template_data,
            "template_meta": template_meta,
        }

    def cut_steps(self) -> None:
        self.copy_steps()

        if hasattr(self, "step_clipboard") and self.step_clipboard:
            self.on_delete_step()

    def paste_steps(self) -> None:
        if not self.current_runner or not getattr(self, "step_clipboard", None):
            return

        clipboard = self.step_clipboard
        steps_to_paste = copy.deepcopy(clipboard["steps"])

        row = self.step_list.currentRow()

        if row >= 0 and row < len(self.flat_parents):
            parent = self.flat_parents[row]
            step = self.flat_steps[row]
            idx = next((i for i, s in enumerate(parent) if s is step), -1)
            insert_at = idx + 1 if idx >= 0 else len(parent)
        else:
            parent = self.current_runner.macro.get("steps", [])
            insert_at = len(parent)

        for i, step in enumerate(steps_to_paste):
            parent.insert(insert_at + i, step)

        templates_dir = self.macro_templates_dir

        for name, data in clipboard["templates"].items():
            dest = templates_dir / f"{name}.png"
            if not dest.exists():
                dest.write_bytes(data)

        macro_templates = self.current_runner.macro.setdefault("templates", {})

        for name, meta in clipboard["template_meta"].items():
            if name not in macro_templates:
                macro_templates[name] = copy.deepcopy(meta)

        self.sync_macro_templates()
        self.save_current_macro()
        self.populate_steps()

        new_row = insert_at + len(steps_to_paste) - 1

        if new_row < self.step_list.count():
            self.step_list.setCurrentRow(new_row)

    def duplicate_steps(self) -> None:
        if not self.current_runner:
            return

        rows = sorted(idx.row() for idx in self.step_list.selectedIndexes())

        if not rows:
            return

        last_row = rows[-1]

        if last_row >= len(self.flat_steps):
            return

        parent = self.flat_parents[last_row]
        last_step = self.flat_steps[last_row]
        insert_idx = next((i for i, s in enumerate(parent) if s is last_step), -1) + 1

        duplicated = [copy.deepcopy(self.flat_steps[r]) for r in rows if r < len(self.flat_steps)]

        for i, step in enumerate(duplicated):
            parent.insert(insert_idx + i, step)

        self.sync_macro_templates()
        self.save_current_macro()
        self.populate_steps()

        new_row = last_row + len(duplicated)
        if new_row < self.step_list.count():
            self.step_list.setCurrentRow(new_row)

    def get_block_child_list(self, step: dict, direction: int) -> list[dict] | None:
        """Return the child list to enter when moving into a block step."""
        step_type = step.get("type")

        if step_type == "repeat":
            return step.get("steps")

        if step_type == "if_image":
            if direction == 1:
                return step.get("then")
            else:
                return step.get("else") or step.get("then")

        if step_type == "if_any_image":
            branches = step.setdefault("branches", {})
            keys = list(branches.keys())

            if not keys:
                templates = step.get("templates", [])

                if not templates:
                    return None

                for template in templates:
                    branches.setdefault(template, [])

                keys = list(branches.keys())

            key = keys[0] if direction == 1 else keys[-1]

            return branches[key]

        return None

    def get_sibling_branch(self, parent: list[dict], direction: int) -> list[dict] | None:
        """For if_image/if_any_image branches, return the next branch to traverse."""
        for s in self.flat_steps:
            if s.get("type") == "if_image":
                if direction == 1 and s.get("then") is parent:
                    return s.get("else")

                if direction == -1 and s.get("else") is parent:
                    return s.get("then")
            elif s.get("type") == "if_any_image":
                keys = list(s.get("branches", {}).keys())

                for i, key in enumerate(keys):
                    if s["branches"][key] is parent:
                        next_i = i + direction

                        if 0 <= next_i < len(keys):
                            return s["branches"][keys[next_i]]

                        return None

        return None

    def find_repeat_owner(self, child_list: list[dict]) -> tuple[dict, list[dict]] | None:
        """Find the block whose sub-list is child_list, and its parent list."""
        for i, s in enumerate(self.flat_steps):
            if s.get("type") == "repeat" and s.get("steps") is child_list:
                return s, self.flat_parents[i]

            if s.get("type") == "if_image" and (s.get("then") is child_list or s.get("else") is child_list):
                return s, self.flat_parents[i]

            if s.get("type") == "if_any_image" and any(
                branch is child_list for branch in s.get("branches", {}).values()
            ):
                return s, self.flat_parents[i]

        return None

    def on_step_context_menu(self, pos) -> None:
        if not self.current_runner:
            return

        menu = RoundMenu(parent=self)

        has_selection = bool(self.step_list.selectedIndexes())
        has_clipboard = bool(getattr(self, "step_clipboard", None))

        act_copy = Action(t("menu.edit.copy"), triggered=self.copy_steps, shortcut="Ctrl+C")
        act_copy.setEnabled(has_selection)
        menu.addAction(act_copy)

        act_cut = Action(t("menu.edit.cut"), triggered=self.cut_steps, shortcut="Ctrl+X")
        act_cut.setEnabled(has_selection)
        menu.addAction(act_cut)

        act_paste = Action(t("menu.edit.paste"), triggered=self.paste_steps, shortcut="Ctrl+V")
        act_paste.setEnabled(has_clipboard)
        menu.addAction(act_paste)

        menu.addSeparator()

        act_dup = Action(t("menu.edit.duplicate_step"), triggered=self.duplicate_steps, shortcut="Ctrl+D")
        act_dup.setEnabled(has_selection)
        menu.addAction(act_dup)

        act_del = Action(t("menu.edit.delete_step"), triggered=self.on_delete_step, shortcut="Delete")
        act_del.setEnabled(has_selection)
        menu.addAction(act_del)

        menu.addSeparator()

        act_wrap = Action(t("action.wrap_in_repeat"), triggered=self.wrap_in_repeat)
        act_wrap.setEnabled(has_selection)
        menu.addAction(act_wrap)

        menu.exec(self.step_list.mapToGlobal(pos))

    def wrap_in_repeat(self) -> None:
        if not self.current_runner:
            return

        rows = sorted(idx.row() for idx in self.step_list.selectedIndexes())

        if not rows:
            return

        parent = self.flat_parents[rows[0]]
        selected_steps = []

        for r in rows:
            if r >= len(self.flat_steps) or self.flat_parents[r] is not parent:
                return

            selected_steps.append(self.flat_steps[r])

        indices = [next(i for i, s in enumerate(parent) if s is step) for step in selected_steps]
        start, end = min(indices), max(indices)

        wrapped = parent[start : end + 1]
        repeat = {"type": "repeat", "count": 1, "steps": wrapped}
        parent[start : end + 1] = [repeat]

        self.save_current_macro()
        self.populate_steps()
        new_row = next((i for i, s in enumerate(self.flat_steps) if s is repeat), 0)
        self.step_list.setCurrentRow(new_row)

    def on_move_step(self, direction: int) -> None:
        row = self.step_list.currentRow()

        if row < 0 or row >= len(self.flat_steps):
            return

        step = self.flat_steps[row]
        parent = self.flat_parents[row]

        idx = next((i for i, s in enumerate(parent) if s is step), -1)
        if idx < 0:
            return

        new_idx = idx + direction
        moved = False

        if 0 <= new_idx < len(parent):
            neighbor = parent[new_idx]
            target_list = self.get_block_child_list(neighbor, direction)

            if target_list is not None:
                parent.pop(idx)

                if direction == -1:
                    target_list.append(step)
                else:
                    target_list.insert(0, step)

                moved = True
            else:
                parent[idx], parent[new_idx] = parent[new_idx], parent[idx]
                moved = True
        else:
            sibling = self.get_sibling_branch(parent, direction)

            if sibling is not None:
                parent.pop(idx)

                if direction == 1:
                    sibling.insert(0, step)
                else:
                    sibling.append(step)

                moved = True
            else:
                owner = self.find_repeat_owner(parent)

                if owner:
                    repeat_block, grandparent = owner
                    ri = next(i for i, s in enumerate(grandparent) if s is repeat_block)
                    parent.pop(idx)

                    if direction == -1:
                        grandparent.insert(ri, step)
                    else:
                        grandparent.insert(ri + 1, step)

                    moved = True

        if moved:
            self.save_current_macro()
            self.populate_steps()

            if any(s is step for s in self.flat_steps):
                new_row = next((i for i, s in enumerate(self.flat_steps) if s is step), -1)
                if new_row >= 0:
                    self.step_list.setCurrentRow(new_row)

    def on_run(self) -> None:
        if not self.current_runner:
            return

        runner = self.current_runner

        if runner.is_running():
            runner.stop()
            return

        if not runner.macro.get("meta", {}).get("enabled", True):
            return

        runner.conf = self.conf
        runner.start()

        self.start_refresh_timer()

    def start_refresh_timer(self) -> None:
        if not hasattr(self, "refresh_timer"):
            self.refresh_timer = QTimer(self)
            self.refresh_timer.setInterval(200)
            self.refresh_timer.timeout.connect(self.refresh_status)

        self.refresh_timer.start()

    def refresh_status(self) -> None:
        if not self.current_runner:
            return

        runner = self.current_runner
        status = runner.get_status()

        if status.running:
            self.btn_run.setText(f" {t('action.stop')}")
            self.btn_run.setIcon(icon("pause"))

            elapsed_str = ""

            if hasattr(runner, "start_time") and runner.start_time is not None:
                elapsed = int(time.monotonic() - runner.start_time)
                elapsed_str = f"{elapsed // 60:02d}:{elapsed % 60:02d} | "

            msg = f"{elapsed_str}{t('status.running', label=runner.label)}"

            if status.state and status.state not in ("-", "running"):
                msg = f"{elapsed_str}{status.state}"
            elif status.progress and status.repeat_total:
                msg += f" | {t('status.loop_progress', progress=status.progress, total=status.repeat_total)}"
            if status.score > 0:
                msg += f" | {t('status.similarity', score=int(status.score * 100))}"

            self.status_label.setText(msg)
            self.set_editing_locked(True)
            self.highlight_current_step(runner)
        else:
            self.btn_run.setText(f" {t('action.run')}")
            self.btn_run.setIcon(icon("play"))

            if status.last_reason:
                self.status_label.setText(f"{runner.label}: {status.message or status.last_reason}")

                if status.last_reason in ("error", "ui_unrecognized", "wrong_start_screen"):
                    pass
                else:
                    pass

                self.set_editing_locked(False)
                self.refresh_timer.stop()
            elif not runner.is_running():
                self.status_label.setText(t("status.macro_count", count=len(self.runners)))
                self.set_editing_locked(False)
                self.refresh_timer.stop()

    def set_editing_locked(self, locked: bool) -> None:
        self.btn_add_step.setEnabled(not locked)
        self.btn_del.setEnabled(not locked)
        self.btn_up.setEnabled(not locked)
        self.btn_down.setEnabled(not locked)
        self.macro_list.setEnabled(not locked)

    def highlight_current_step(self, runner: MacroRunner) -> None:
        current = getattr(runner, "current_step", None)

        if current is None or not hasattr(self, "flat_steps"):
            return
        try:
            idx = next(i for i, s in enumerate(self.flat_steps) if s is current)
            self.step_list.blockSignals(True)
            self.step_list.setCurrentRow(idx)
            self.step_list.blockSignals(False)
        except StopIteration:
            pass

    def open_settings(self) -> None:
        self.settings_page = SettingsPage(self, self.conf, on_save=self.apply_settings)
        self.addSubInterface(self.settings_page, "", "", isTransparent=True)
        self.stackedWidget.setCurrentWidget(self.settings_page)
        self.stackedWidget.setAnimationEnabled(False)

    def apply_settings(self, new_conf: cfg.Config) -> None:
        self.conf = new_conf

        for runner in self.runners:
            runner.conf = new_conf

        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, new_conf.general.always_on_top)
        theme_map = {"light": Theme.LIGHT, "dark": Theme.DARK, "system": Theme.AUTO}
        setTheme(theme_map.get(new_conf.general.theme, Theme.AUTO))

        self.show()

    def on_add_macro(self) -> None:
        dialog = MessageBoxBase(self)
        dialog.yesButton.setText(t("action.confirm"))
        dialog.cancelButton.setText(t("action.cancel"))
        dialog.viewLayout.addWidget(SubtitleLabel(t("dialog.new_macro")))
        name_edit = LineEdit()
        name_edit.setPlaceholderText(t("dialog.name_placeholder"))
        dialog.viewLayout.addWidget(name_edit)
        dialog.widget.setMinimumWidth(300)
        name_edit.setFocus()

        if not dialog.exec():
            return

        name = name_edit.text().strip()
        if not name:
            return

        macro_id = str(int(time.time()))
        path = cfg.macros_dir() / f"{macro_id}.json"

        macro = {
            "meta": {"name": macro_id, "label": name},
            "templates": {},
            "steps": [],
        }
        path.write_text(json.dumps(macro, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

        runner = MacroRunner(self.conf, macro, source_path=path)
        self.runners.append(runner)

        item = QListWidgetItem(runner.label)
        item.setData(Qt.ItemDataRole.UserRole, runner.name)
        self.macro_list.addItem(item)
        self.macro_list.setCurrentRow(self.macro_list.count() - 1)

    def on_duplicate_macro(self) -> None:
        if not self.current_runner:
            return

        runner = self.current_runner

        if not runner.source_path:
            return

        macro_id = str(int(time.time()))
        path = cfg.macros_dir() / f"{macro_id}.json"

        macro = copy.deepcopy(runner.macro)
        macro["meta"]["name"] = macro_id
        macro["meta"]["label"] = runner.label + " " + t("macro.duplicate_suffix")

        path.write_text(json.dumps(macro, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

        source_templates = cfg.templates_dir(runner.name)
        destination_template = cfg.templates_dir(macro_id)

        if source_templates.exists():
            shutil.copytree(source_templates, destination_template, dirs_exist_ok=True)

        new_runner = MacroRunner(self.conf, macro, source_path=path)
        self.runners.append(new_runner)

        item = QListWidgetItem(new_runner.label)
        self.macro_list.addItem(item)
        self.macro_list.setCurrentRow(self.macro_list.count() - 1)

    def on_export_json(self) -> None:
        if not self.current_runner:
            return

        runner = self.current_runner

        if not runner.source_path:
            return

        path, _ = QFileDialog.getSaveFileName(
            self, t("dialog.export_macro"), f"{runner.name}.zip", t("dialog.zip_filter")
        )

        if not path:
            return

        refs: set[str] = set()
        self.collect_template_refs(runner.macro.get("steps", []), refs)

        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("macro.json", json.dumps(runner.macro, indent=2, ensure_ascii=False))

            for name in refs:
                png_path = self.macro_templates_dir / f"{name}.png"
                if png_path.exists():
                    zf.write(png_path, f"templates/{name}.png")

                meta_path = self.macro_templates_dir / f"{name}.json"
                if meta_path.exists():
                    zf.write(meta_path, f"templates/{name}.json")

    def on_import_json(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, t("dialog.import_macro"), "", t("dialog.zip_filter"))

        if not path:
            return

        try:
            with zipfile.ZipFile(path, "r") as zf:
                if "macro.json" not in zf.namelist():
                    dialog = MessageBox(t("dialog.import_failed"), t("dialog.import_no_macro_json"), self)
                    dialog.cancelButton.hide()
                    dialog.exec()
                    return

                macro = json.loads(zf.read("macro.json"))

                if not isinstance(macro.get("meta"), dict) or not macro["meta"].get("name"):
                    dialog = MessageBox(t("dialog.import_failed"), t("dialog.import_invalid_meta"), self)
                    dialog.cancelButton.hide()
                    dialog.exec()
                    return

                if not isinstance(macro.get("steps"), list):
                    dialog = MessageBox(t("dialog.import_failed"), t("dialog.import_invalid_steps"), self)
                    dialog.cancelButton.hide()
                    dialog.exec()
                    return

                refs: set[str] = set()
                self.collect_template_refs(macro.get("steps", []), refs)

                missing = [n for n in refs if f"templates/{n}.png" not in zf.namelist()]

                if missing:
                    dialog = MessageBox(
                        t("dialog.import_failed"), t("dialog.import_missing_templates", names=", ".join(missing)), self
                    )
                    dialog.cancelButton.hide()
                    dialog.exec()
                    return

                name = macro["meta"]["name"]
                destination = cfg.macros_dir() / f"{name}.json"

                if destination.exists():
                    name = str(int(time.time()))
                    destination = cfg.macros_dir() / f"{name}.json"
                    macro["meta"]["name"] = name

                macro_name = macro["meta"]["name"]
                conflicts = [n for n in refs if (cfg.templates_dir(macro_name) / f"{n}.png").exists()]
                overwrite = False

                if conflicts:
                    overwrite = MessageBox(
                        t("dialog.template_conflict_title"),
                        t("dialog.template_conflict_msg", names=", ".join(conflicts)),
                        self,
                    ).exec()

                for n in refs:
                    png_destination = cfg.templates_dir(macro_name) / f"{n}.png"
                    if not png_destination.exists() or (overwrite and n in conflicts):
                        png_destination.write_bytes(zf.read(f"templates/{n}.png"))

                    meta_arc = f"templates/{n}.json"
                    if meta_arc in zf.namelist():
                        meta_destination = cfg.templates_dir(macro_name) / f"{n}.json"
                        if not meta_destination.exists() or (overwrite and n in conflicts):
                            meta_destination.write_bytes(zf.read(meta_arc))

                destination.write_text(json.dumps(macro, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        except zipfile.BadZipFile:
            dialog = MessageBox(t("dialog.import_failed"), t("dialog.import_bad_zip"), self)
            dialog.cancelButton.hide()
            dialog.exec()
            return

        new_runner = MacroRunner(self.conf, macro, source_path=destination)
        self.runners.append(new_runner)

        item = QListWidgetItem(new_runner.label)
        self.macro_list.addItem(item)
        self.macro_list.setCurrentRow(self.macro_list.count() - 1)

    def on_about(self) -> None:
        dialog = MessageBoxBase(self)
        dialog.yesButton.setText(t("action.close"))
        dialog.cancelButton.hide()
        dialog.viewLayout.addWidget(SubtitleLabel(f"Remaku v{__version__}"))
        dialog.viewLayout.addSpacing(4)
        dialog.viewLayout.addWidget(BodyLabel(t("dialog.about_description")))
        links = BodyLabel(
            '<a href="https://github.com/remaku/remaku">GitHub</a> · '
            '<a href="https://discord.gg/ncK4mhPkwt">Discord</a> · '
            f'<a href="https://remaku.com">{t("dialog.about_website")}</a>'
        )
        links.setOpenExternalLinks(True)
        dialog.viewLayout.addWidget(links)
        email = BodyLabel('<a href="mailto:hello@remaku.com">hello@remaku.com</a>')
        email.setOpenExternalLinks(True)
        dialog.viewLayout.addWidget(email)
        dialog.viewLayout.addSpacing(8)
        dialog.viewLayout.addWidget(BodyLabel(t("dialog.about_copyright")))
        sponsor = BodyLabel(
            '<a href="https://github.com/sponsors/nelsonlaidev">GitHub Sponsors</a> · '
            '<a href="https://buymeacoffee.com/nelsonlaidev">Buy Me A Coffee</a>'
        )
        sponsor.setOpenExternalLinks(True)
        dialog.viewLayout.addWidget(sponsor)
        dialog.widget.setMinimumWidth(350)
        dialog.exec()

    def on_sponsor(self) -> None:
        webbrowser.open("https://github.com/sponsors/nelsonlaidev")

    def on_open_logs(self) -> None:
        os.startfile(cfg.logs_dir())

    def on_check_update(self) -> None:
        def callback(result: "updater.CheckResult") -> None:
            if result.status == "available" and result.info is not None:
                updater.prompt_update(self, result.info)
            elif result.status == "up_to_date":
                dialog = MessageBox(t("updater.up_to_date_title"), t("updater.up_to_date_msg"), self)
                dialog.cancelButton.hide()
                dialog.exec()
            else:
                dialog = MessageBox(t("updater.check_failed_title"), result.error or "", self)
                dialog.cancelButton.hide()
                dialog.exec()

        updater.check_async(self, callback)

    def startup_check_update(self) -> None:
        def callback(result: "updater.CheckResult") -> None:
            if result.status == "available" and result.info is not None:
                if result.info.tag == self.conf.general.skipped_version:
                    return
                updater.prompt_update(self, result.info)

        updater.check_async(self, callback)

    def on_macro_context_menu(self, pos) -> None:
        item = self.macro_list.itemAt(pos)

        if item is None:
            return

        row = self.macro_list.row(item)

        if row < 0 or row >= len(self.runners):
            return

        menu = RoundMenu(parent=self)

        menu.addAction(Action(t("action.rename"), triggered=lambda: self.rename_macro(row)))
        menu.addAction(Action(t("action.delete"), triggered=lambda: self.delete_macro(row)))

        menu.exec(self.macro_list.mapToGlobal(pos))

    def on_macros_reordered(self) -> None:
        name_to_runner = {r.name: r for r in self.runners}
        self.runners = [
            name_to_runner[self.macro_list.item(i).data(Qt.ItemDataRole.UserRole)]
            for i in range(self.macro_list.count())
        ]
        self.conf.general.macro_order = [r.name for r in self.runners]
        cfg.save(self.conf)

    def rename_macro(self, row: int) -> None:
        runner = self.runners[row]

        dialog = MessageBoxBase(self)
        dialog.yesButton.setText(t("action.confirm"))
        dialog.cancelButton.setText(t("action.cancel"))
        dialog.viewLayout.addWidget(SubtitleLabel(t("dialog.rename")))
        name_edit = LineEdit()
        name_edit.setText(runner.label)
        dialog.viewLayout.addWidget(name_edit)
        dialog.widget.setMinimumWidth(300)
        name_edit.setFocus()
        name_edit.selectAll()

        if not dialog.exec():
            return

        name = name_edit.text().strip()
        if not name:
            return

        runner.macro["meta"]["label"] = name
        runner.label = name

        self.save_runner(runner)

        item = self.macro_list.item(row)

        if item:
            item.setText(runner.label)

    def delete_macro(self, row: int) -> None:
        runner = self.runners[row]

        templates_path = cfg.user_data_dir() / "templates" / runner.name
        has_templates = templates_path.exists() and any(templates_path.iterdir())

        dialog = MessageBoxBase(self)
        dialog.yesButton.setText(t("action.delete"))
        dialog.cancelButton.setText(t("action.cancel"))
        dialog.viewLayout.addWidget(SubtitleLabel(t("dialog.delete_macro")))
        dialog.viewLayout.addWidget(BodyLabel(t("dialog.delete_macro_confirm", label=runner.label)))

        checkbox = None

        if has_templates:
            checkbox = CheckBox(t("dialog.delete_templates_too"))
            dialog.viewLayout.addWidget(checkbox)

        dialog.widget.setMinimumWidth(300)

        if not dialog.exec():
            return

        if runner.source_path and runner.source_path.exists():
            runner.source_path.unlink()

        if checkbox and checkbox.isChecked():
            shutil.rmtree(templates_path, ignore_errors=True)

        self.runners.pop(row)
        self.macro_list.takeItem(row)

        if self.runners:
            self.macro_list.setCurrentRow(min(row, len(self.runners) - 1))
        else:
            self.current_runner = None
            self.step_list.clear()
            self.flat_steps = []
            self.flat_parents = []
            self.clear_props()

        self.update_empty_states()

    def save_runner(self, runner: MacroRunner) -> None:
        if runner.source_path:
            runner.source_path.write_text(
                json.dumps(runner.macro, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
