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
from typing import Any

import pydirectinput as pdi
from loguru import logger
from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QCursor, QIcon, QKeyEvent, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QListWidgetItem,
    QSplitter,
    QTreeWidgetItem,
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
    TreeWidget,
    qrouter,
    setTheme,
)

import capture
import config as cfg
import updater
import window
from i18n import t
from icons import icon
from macro_engine import MacroRunner, load_macro
from overlay import OverlayWidget
from region_selector import RegionSelector
from settings import SettingsPage
from step_node import StepNode
from step_tree import StepTree
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
        self.overlay = OverlayWidget()
        self.overlay.toggle_run.connect(self.on_run)
        pos = self.conf.general.overlay_position
        self.overlay.move(pos[0], pos[1])

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

        self.step_list = TreeWidget()
        self.step_list.setHeaderHidden(True)
        self.step_list.setIconSize(QSize(18, 18))
        self.step_list.setSelectionMode(TreeWidget.SelectionMode.ExtendedSelection)
        self.step_list.currentItemChanged.connect(self.on_step_selected)
        self.step_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.step_list.customContextMenuRequested.connect(self.on_step_context_menu)
        center_layout.addWidget(self.step_list, 1)

        self.step_empty_label = BodyLabel(t("step.empty_hint"))
        self.step_empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.step_empty_label.setWordWrap(True)
        center_layout.addWidget(self.step_empty_label, 1)

        self.center_panel.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.center_panel.customContextMenuRequested.connect(self.on_step_context_menu)

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

        has_steps = self.step_list.topLevelItemCount() > 0
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
        self.step_list.clearSelection()
        self.show_macro_props()
        self.update_undo_redo_state()

    def on_step_selected(self, current: QTreeWidgetItem | None, previous: QTreeWidgetItem | None) -> None:
        self.commit_field_edits()

        if not self.current_runner:
            return

        if current is None:
            self.show_macro_props()
            return

        node = self.item_to_node.get(current)
        if node is None:
            self.show_macro_props()
            return

        self.show_props(node.step)

    def show_macro_props(self) -> None:
        self.clear_props()

        if not self.current_runner:
            return

        self.prop_title.setText(t("prop.macro_props"))

        lbl = BodyLabel(t("prop.target_window"))
        self.prop_fields_layout.addWidget(lbl)

        combo = ComboBox()
        combo.blockSignals(True)
        combo.addItem(t("prop.target_window_foreground"), userData="")

        for title in window.list_visible_windows():
            combo.addItem(title, userData=title)

        current = self.current_runner.target_window
        idx = combo.findData(current)

        if idx < 0 and current:
            combo.addItem(current, userData=current)
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

    def on_key_step_capture(self, event: QKeyEvent, edit: LineEdit, step: dict) -> None:
        key = event.key()

        if key in (Qt.Key.Key_Escape,):
            edit.blockSignals(True)
            edit.setText("")
            edit.blockSignals(False)
            step["key"] = ""
            self.mutate_steps(select_step=step)
            return

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
        step["key"] = key_name
        self.mutate_steps(select_step=step)

    def on_key_step_cleared(self, step: dict) -> None:
        step["key"] = ""
        self.mutate_steps(select_step=step)

    def refresh_step_list(self, *, select_step=None, select_row=None) -> None:
        self.step_list.blockSignals(True)
        self.populate_steps()

        item = None
        if select_step is not None and self.step_tree:
            node = self.step_tree.find_node(select_step)
            if node is not None:
                item = self.node_to_item.get(node)
        elif select_row is not None:
            flat = getattr(self, "flat_nodes", [])
            if 0 <= select_row < len(flat):
                item = self.node_to_item.get(flat[select_row])

        if item is not None:
            self.step_list.setCurrentItem(item)
            self.expand_item_ancestors(item)

        self.step_list.blockSignals(False)

        node = self.item_to_node.get(self.step_list.currentItem()) if self.step_list.currentItem() else None
        if node is not None:
            self.show_props(node.step)
        else:
            self.show_macro_props()

    def mutate_steps(self, mutation_fn=None, *, select_step=None) -> None:
        """Apply a step mutation, save, push undo, and refresh the UI atomically."""
        if not self.current_runner:
            return

        if mutation_fn is not None:
            mutation_fn(self.current_runner)

        self.save_current_macro()
        self.refresh_step_list(select_step=select_step)

    def capture_step_list_collapsed_state(self) -> set[int]:
        """Capture collapsed container steps by raw step identity."""
        collapsed_steps: set[int] = set()

        for item, node in self.item_to_node.items():
            if not node.is_container:
                continue

            if not item.isExpanded():
                collapsed_steps.add(id(node.step))

        return collapsed_steps

    def apply_step_list_collapsed_state(self, collapsed_steps: set[int]) -> None:
        """Restore collapsed container steps after rebuilding the tree."""
        for item, node in self.item_to_node.items():
            if not node.is_container:
                continue

            item.setExpanded(id(node.step) not in collapsed_steps)

    def expand_item_ancestors(self, item: QTreeWidgetItem) -> None:
        """Expand all ancestors of *item* so the selection remains visible."""
        current = item
        while current is not None:
            self.step_list.expandItem(current)
            current = current.parent()

    def populate_steps_and_keep_row(self) -> None:
        item = self.step_list.currentItem()
        node = self.item_to_node.get(item) if item else None
        self.refresh_step_list(select_step=node.step if node else None)

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
        collapsed_steps = self.capture_step_list_collapsed_state() if hasattr(self, "item_to_node") else set()

        self.step_list.clear()
        self.item_to_node: dict[QTreeWidgetItem, StepNode] = {}
        self.node_to_item: dict[StepNode, QTreeWidgetItem] = {}

        if not self.current_runner:
            self.step_tree = None
            self.flat_nodes: list[StepNode] = []
            self.update_empty_states()
            return

        steps = self.current_runner.macro.get("steps", [])
        self.step_tree = StepTree(steps)
        self.flat_nodes = self.step_tree.flatten()

        for node in self.step_tree.root_nodes:
            self.build_tree_item(node, None)

        self.step_list.expandAll()

        if collapsed_steps:
            self.apply_step_list_collapsed_state(collapsed_steps)

        self.update_empty_states()

    def build_tree_item(self, node: StepNode, parent_item: QTreeWidgetItem | None) -> QTreeWidgetItem:
        step_icon, summary = self.step_display(node.step)
        item = QTreeWidgetItem([summary])
        if step_icon:
            item.setIcon(0, step_icon)
        self.apply_step_note(item, node.step)
        self.item_to_node[item] = node
        self.node_to_item[node] = item

        if parent_item is None:
            self.step_list.addTopLevelItem(item)
        else:
            parent_item.addChild(item)

        for _branch_name, child_nodes in node.child_lists():
            for child_node in child_nodes:
                self.build_tree_item(child_node, item)

        return item

    def apply_step_note(self, item: QTreeWidgetItem, step: dict) -> None:
        note = step.get("note", "").strip()
        if note:
            item.setToolTip(0, note)
            item.setText(0, item.text(0) + f" ({note})")

    def step_display(self, step: dict) -> tuple[QIcon | None, str]:
        step_type = step.get("type", "?")

        icons = {
            "wait_image": icon("image"),
            "key": icon("keyboard"),
            "delay": icon("timer"),
            "repeat": icon("repeat"),
            "hold_key_until_gone": icon("keyboard"),
            "if_image": icon("git-branch"),
            "if_any_image": icon("git-merge"),
            "grid_nav": icon("layout-grid"),
        }

        summaries = {
            "key": lambda s: t("step.summary.key", key=s.get("key", "")),
            "delay": lambda s: t("step.summary.delay", ms=s.get("ms", 0)),
            "wait_image": lambda s: t("step.summary.wait_image", template=self.template_label(s.get("template", ""))),
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
        if self.is_child_of_skipped_repeat(step):
            skip_checkbox.setEnabled(False)
        self.prop_fields_layout.addWidget(skip_checkbox)

        note_lbl = BodyLabel(t("prop.note"))
        self.prop_fields_layout.addWidget(note_lbl)

        note_edit = LineEdit()
        note_edit.setText(step.get("note", ""))
        note_edit.setPlaceholderText(t("prop.note_placeholder"))
        note_edit.editingFinished.connect(lambda: self.on_prop_edit(step, "note", note_edit))
        self.prop_fields_layout.addWidget(note_edit)

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
            "key": [("hold_ms", t("prop.hold_ms"))],
            "delay": [("ms", t("prop.delay_ms"))],
            "repeat": [("count", t("prop.count"))],
        }

        if step_type == "key":
            key_lbl = BodyLabel(t("prop.key"))
            self.prop_fields_layout.addWidget(key_lbl)

            key_edit = LineEdit()
            key_edit.setText(str(step.get("key", "")))
            key_edit.setReadOnly(True)
            key_edit.setClearButtonEnabled(True)
            key_edit.textChanged.connect(lambda txt, s=step: self.on_key_step_cleared(s) if not txt else None)
            key_edit.keyPressEvent = lambda e: self.on_key_step_capture(e, key_edit, step)
            self.prop_fields_layout.addWidget(key_edit)

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

        if template_name:
            self.add_template_resolution_fields(template_name, layout)

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

        if template_name:
            self.add_template_resolution_fields(template_name, layout)

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

            self.add_template_resolution_fields(name, content_layout)

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

            if self.current_runner:
                macro_templates = self.current_runner.macro.get("templates", {})
                macro_templates.pop(old_name, None)

        step["templates"][idx] = name
        self.sync_macro_templates()
        self.showNormal()
        self.any_image_expand_idx = idx
        self.mutate_steps(select_step=step)
        self.step_list.setFocus()

    def on_pick_any_template(self, step: dict, idx: int) -> None:
        """Pick an image file as the specified template in if_any_image."""
        path, _ = QFileDialog.getOpenFileName(self, t("dialog.select_image"), "", t("dialog.png_filter"))

        if not path:
            return

        template_name = f"{int(time.time())}"
        destination = self.macro_templates_dir / f"{template_name}.png"
        shutil.copy2(path, destination)
        self.write_template_meta(template_name)
        step["templates"][idx] = template_name

        self.sync_macro_templates()
        self.any_image_expand_idx = idx
        self.mutate_steps(select_step=step)

    def on_rename_any_template(self, step: dict, idx: int, edit: LineEdit) -> None:
        """Rename the label of a specified template in if_any_image."""
        templates = step.get("templates", [])
        name = templates[idx] if idx < len(templates) else ""
        new_label = edit.text().strip()

        if not new_label or not name:
            return

        macro_templates = self.current_runner.macro.get("templates", {}) if self.current_runner else {}
        macro_templates.setdefault(name, {})["label"] = new_label

        self.any_image_expand_idx = idx
        self.mutate_steps(select_step=step)

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
        self.mutate_steps(select_step=step)

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
        if not self.step_tree:
            return
        parent_node = self.step_tree.find_node(parent_step)
        if not parent_node:
            return
        new_node = self.step_tree.add_step_to_any_branch(parent_node, template_name, step)

        self.sync_macro_templates()

        idx = parent_step.get("templates", []).index(template_name)

        self.any_image_expand_idx = idx
        self.mutate_steps(select_step=new_node.step)

    def on_add_any_template(self, step: dict) -> None:
        """Add an empty template to if_any_image."""
        placeholder = f"{int(time.time())}"
        step.setdefault("templates", []).append(placeholder)

        self.sync_macro_templates()
        self.any_image_expand_idx = len(step["templates"]) - 1
        self.mutate_steps(select_step=step)

    def refresh_current_step(self) -> None:
        item = self.step_list.currentItem()
        node = self.item_to_node.get(item) if item else None
        self.refresh_step_list(select_step=node.step if node else None)

    def show_hold_key_props(self, step: dict) -> None:
        """hold_key_until_gone property panel."""
        layout = self.prop_fields_layout
        template_name = step.get("template", "")

        key_lbl = BodyLabel(t("prop.key"))
        layout.addWidget(key_lbl)

        key_edit = LineEdit()
        key_edit.setText(str(step.get("key", "")))
        key_edit.setReadOnly(True)
        key_edit.setClearButtonEnabled(True)
        key_edit.textChanged.connect(lambda txt, s=step: self.on_key_step_cleared(s) if not txt else None)
        key_edit.keyPressEvent = lambda e: self.on_key_step_capture(e, key_edit, step)
        layout.addWidget(key_edit)

        lbl = BodyLabel(t("prop.template"))
        layout.addWidget(lbl)

        preview = self.template_preview(template_name)
        layout.addWidget(preview)

        self.template_controls(step, template_name, layout)

        if template_name:
            self.add_template_resolution_fields(template_name, layout)

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
            if self.current_runner:
                macro_templates = self.current_runner.macro.get("templates", {})
                macro_templates.pop(old_name, None)

        step["template"] = name
        self.sync_macro_templates()
        self.showNormal()
        self.mutate_steps(select_step=step)
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
        self.write_template_meta(template_name)

        self.sync_macro_templates()
        self.mutate_steps(select_step=step)

    def on_rename_template(self, step: dict, edit: LineEdit) -> None:
        name = step.get("template", "")
        new_label = edit.text().strip()
        if not new_label or not name:
            return

        templates = self.current_runner.macro.get("templates", {}) if self.current_runner else {}
        templates.setdefault(name, {})["label"] = new_label
        self.mutate_steps(select_step=step)

    def on_delete_template(self, step: dict) -> None:
        name = step.get("template", "")

        if not name:
            return

        path = self.macro_templates_dir / f"{name}.png"
        if path.exists():
            path.unlink()

        step["template"] = ""

        self.sync_macro_templates()
        self.mutate_steps(select_step=step)

    def template_label(self, name: str) -> str:
        """Get the display name of a template."""
        if not self.current_runner:
            return name

        template = self.current_runner.macro.get("templates", {}).get(name, {})

        return template.get("label", name)

    def write_template_meta(self, name: str) -> None:
        """Write capture-resolution metadata for a template into macro["templates"][name].

        Stores capture_width and capture_height from the current screen resolution
        into the macro JSON structure (not separate files).
        """
        if not self.current_runner:
            return

        grabber = capture.Grabber()
        entry = self.current_runner.macro.get("templates", {}).get(name, {"label": name})
        entry["capture_width"] = grabber.screen_width
        entry["capture_height"] = grabber.screen_height
        grabber.close()

        self.current_runner.macro.setdefault("templates", {})[name] = entry

    @staticmethod
    def has_valid_template_meta(entry: dict[str, Any]) -> bool:
        """Return True when capture metadata exists and contains positive integer dimensions."""
        width = entry.get("capture_width")
        height = entry.get("capture_height")
        return isinstance(width, int) and width > 0 and isinstance(height, int) and height > 0

    @staticmethod
    def read_legacy_template_meta_file(meta_path) -> dict[str, int] | None:
        """Read a legacy template metadata file and return validated capture dimensions."""
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            return None

        width = meta.get("capture_width")
        height = meta.get("capture_height")

        if not isinstance(width, int) or width <= 0 or not isinstance(height, int) or height <= 0:
            return None

        return {"capture_width": width, "capture_height": height}

    def migrate_template_meta(self, name: str, entry: dict[str, Any]) -> bool:
        """Migrate legacy separate .json metadata file into macro["templates"][name].

        Backward compatibility: older versions stored capture resolution in a separate
        <name>.json file alongside the template .png. This method reads that file,
        merges validated capture_width/capture_height into the macro JSON entry, and
        deletes the legacy file. Returns True only when a valid migration occurred.
        """
        if self.has_valid_template_meta(entry):
            return False

        meta_path = self.macro_templates_dir / f"{name}.json"
        if not meta_path.exists():
            return False

        meta = self.read_legacy_template_meta_file(meta_path)
        if meta is None:
            return False

        entry["capture_width"] = meta["capture_width"]
        entry["capture_height"] = meta["capture_height"]
        meta_path.unlink(missing_ok=True)
        return True

    def ensure_template_meta(self, name: str) -> bool:
        """Ensure the template has capture resolution metadata in macro["templates"][name].

        Returns True when valid metadata already exists or legacy metadata was migrated.
        Returns False when metadata is still missing; in that case the caller may decide
        whether writing the current screen resolution is appropriate.
        """
        if not self.current_runner:
            return False

        entry = self.current_runner.macro.get("templates", {}).get(name, {})
        if self.has_valid_template_meta(entry):
            return True

        migrated = self.migrate_template_meta(name, entry)
        self.current_runner.macro.setdefault("templates", {})[name] = entry
        return migrated or self.has_valid_template_meta(entry)

    def get_template_meta(self, name: str) -> dict:
        """Read template metadata from macro["templates"][name].

        Backward compatibility: if the macro JSON entry doesn't have capture
        resolution yet, falls back to reading the legacy separate .json file
        and migrates the data into the macro JSON (deleting the legacy file).
        Returns the template entry dict containing label, capture_width, capture_height.
        Returns an empty dict if the runner or template entry doesn't exist.
        """
        if not self.current_runner:
            return {}

        templates = self.current_runner.macro.get("templates", {})
        entry = templates.get(name)
        if entry is None:
            return {}

        if self.has_valid_template_meta(entry):
            return entry

        if self.migrate_template_meta(name, entry):
            templates[name] = entry
            self.save_current_macro()

        return entry

    def on_template_resolution_edit(self, name: str, key: str, edit: LineEdit) -> None:
        """Update a capture resolution field in macro["templates"][name]."""
        if not self.current_runner:
            return

        try:
            value = int(edit.text())
        except ValueError:
            return

        entry = self.current_runner.macro.get("templates", {}).get(name, {"label": name})
        entry[key] = value
        self.current_runner.macro.setdefault("templates", {})[name] = entry

    def add_template_resolution_fields(self, template_name: str, layout: QVBoxLayout) -> None:
        """Add capture width and height edit fields for the given template."""
        meta = self.get_template_meta(template_name)
        width = str(meta.get("capture_width", ""))
        height = str(meta.get("capture_height", ""))

        width_lbl = BodyLabel(t("prop.capture_width"))
        layout.addWidget(width_lbl)

        width_edit = LineEdit()
        width_edit.setText(width)
        width_edit.editingFinished.connect(
            lambda n=template_name, e=width_edit: self.on_template_resolution_edit(n, "capture_width", e)
        )
        layout.addWidget(width_edit)

        height_lbl = BodyLabel(t("prop.capture_height"))
        layout.addWidget(height_lbl)

        height_edit = LineEdit()
        height_edit.setText(height)
        height_edit.editingFinished.connect(
            lambda n=template_name, e=height_edit: self.on_template_resolution_edit(n, "capture_height", e)
        )
        layout.addWidget(height_edit)

    def sync_macro_templates(self) -> None:
        """Rebuild macro["templates"] to only keep template names actually referenced by steps.

        Each template entry in macro["templates"] stores:
        - label: display name for the template
        - capture_width: screen width when the template was captured (for runtime scaling)
        - capture_height: screen height when the template was captured (for runtime scaling)

        Backward compatibility: if separate .json metadata files exist alongside template .png
        files (legacy format), they are migrated into macro["templates"] and deleted.
        Missing metadata is preserved as-is here; callers that create or recapture templates
        are responsible for writing fresh capture dimensions.
        """
        if not self.current_runner:
            return

        macro = self.current_runner.macro
        used: set[str] = set()

        self.collect_template_refs(macro.get("steps", []), used)

        existing = macro.get("templates", {})
        migrated: dict[str, dict] = {}
        did_migrate = False

        for name in used:
            entry = existing.get(name, {"label": name})
            did_migrate = self.migrate_template_meta(name, entry) or did_migrate
            migrated[name] = entry

        macro["templates"] = migrated
        self.current_runner.template_names = list(used)

        if did_migrate:
            self.save_current_macro()

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

    def is_child_of_skipped_repeat(self, step: dict) -> bool:
        if self.step_tree is not None:
            node = self.step_tree.find_node(step)
            if node is not None and node.parent is not None:
                parent = node.parent
                return parent.step_type == "repeat" and parent.step.get("skip", False)
            return False
        return False

    def on_prop_bool(self, step: dict, key: str, checked: bool) -> None:
        step[key] = checked
        if key == "skip" and step.get("type") == "repeat":
            for child in step.get("steps", []):
                child["skip"] = checked
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
        elif key != "note":
            try:
                value = int(value)
            except ValueError:
                with contextlib.suppress(ValueError):
                    value = float(value)

        step[key] = value
        self.mutate_steps(select_step=step)

    def on_grid_nav_start_edit(self, step: dict, edit: LineEdit) -> None:
        try:
            val = int(edit.text()) - 1
        except ValueError:
            return

        step["start"] = max(0, val)
        self.mutate_steps(select_step=step)

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

        item = self.step_list.currentItem()
        node = self.item_to_node.get(item) if item else None
        select_index = -1
        if node is not None:
            flat = getattr(self, "flat_nodes", [])
            try:
                select_index = flat.index(node)
            except ValueError:
                select_index = -1

        self.current_runner.redo_stack.append(copy.deepcopy(self.current_runner.macro))
        self.current_runner.macro = self.current_runner.undo_stack.pop()
        self.current_runner.last_snapshot = copy.deepcopy(self.current_runner.macro)
        self.save_runner(self.current_runner)
        self.on_macro_selected(self.macro_list.currentRow())

        if select_index >= 0:
            flat = getattr(self, "flat_nodes", [])
            if select_index < len(flat):
                new_item = self.node_to_item.get(flat[select_index])
                if new_item:
                    self.step_list.setCurrentItem(new_item)

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
        if not self.step_tree:
            return
        parent_node = self.step_tree.find_node(parent_step)
        if not parent_node:
            return
        new_node = self.step_tree.add_step_to_branch(parent_node, branch, step)
        self.mutate_steps(select_step=new_node.step)

    def do_add_step(self, step: dict) -> None:
        if not self.current_runner or not self.step_tree:
            return

        item = self.step_list.currentItem()
        node = self.item_to_node.get(item) if item else None

        new_node = self.step_tree.add_step(node, step)
        self.mutate_steps(select_step=new_node.step)

    def on_delete_step(self) -> None:
        if not self.current_runner or not self.step_tree:
            return

        selected_items = self.step_list.selectedItems()

        if not selected_items:
            return

        nodes_to_delete = [self.item_to_node[item] for item in selected_items if item in self.item_to_node]

        for node in reversed(nodes_to_delete):
            self.step_tree.delete_node(node)

        self.sync_macro_templates()
        self.save_current_macro()
        self.populate_steps()

        if self.step_list.topLevelItemCount() > 0:
            first_item = self.step_list.topLevelItem(0)
            if first_item is not None:
                self.step_list.setCurrentItem(first_item)
        else:
            self.step_list.clearSelection()

    def copy_steps(self) -> None:
        if not self.current_runner or not self.step_tree:
            return

        selected_items = self.step_list.selectedItems()

        if not selected_items:
            return

        selected_nodes = [self.item_to_node[item] for item in selected_items if item in self.item_to_node]
        top_level = self.step_tree.get_top_level(selected_nodes)
        steps = [copy.deepcopy(n.step) for n in top_level]

        if not steps:
            return

        refs: set[str] = set()
        self.collect_template_refs(steps, refs)

        templates_dir = self.macro_templates_dir
        template_data: dict[str, bytes] = {}

        for name in refs:
            png_path = templates_dir / f"{name}.png"
            if png_path.exists():
                template_data[name] = png_path.read_bytes()

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

        if not self.step_tree:
            return

        item = self.step_list.currentItem()
        node = self.item_to_node.get(item) if item else None

        nodes = self.step_tree.insert_steps_after(node, steps_to_paste)

        templates_dir = self.macro_templates_dir

        for name, data in clipboard["templates"].items():
            dest = templates_dir / f"{name}.png"
            if not dest.exists():
                dest.write_bytes(data)

        macro_templates = self.current_runner.macro.setdefault("templates", {})

        for name, meta in clipboard.get("template_meta", {}).items():
            if name not in macro_templates:
                macro_templates[name] = copy.deepcopy(meta)
            else:
                for key in ("capture_width", "capture_height", "label"):
                    if key in meta and key not in macro_templates[name]:
                        macro_templates[name][key] = meta[key]

        self.sync_macro_templates()
        self.mutate_steps(select_step=nodes[0].step if nodes else None)

    def duplicate_steps(self) -> None:
        if not self.current_runner or not self.step_tree:
            return

        selected_items = self.step_list.selectedItems()

        if not selected_items:
            return

        selected_nodes = [self.item_to_node[item] for item in selected_items if item in self.item_to_node]

        duplicates = self.step_tree.duplicate_nodes(selected_nodes)

        self.sync_macro_templates()
        self.save_current_macro()
        self.populate_steps()

        if duplicates:
            dup_step = duplicates[-1].step
            new_node = self.step_tree.find_node(dup_step) if self.step_tree else None
            if new_node:
                new_item = self.node_to_item.get(new_node)
                if new_item:
                    self.step_list.setCurrentItem(new_item)

    def on_step_context_menu(self, pos) -> None:
        if not self.current_runner:
            return

        menu = RoundMenu(parent=self)

        has_selection = bool(self.step_list.selectedItems())
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

        source = self.step_list if self.step_list.isVisible() else self.center_panel
        menu.exec(source.mapToGlobal(pos))

    def wrap_in_repeat(self) -> None:
        if not self.current_runner or not self.step_tree:
            return

        selected_items = self.step_list.selectedItems()

        if not selected_items:
            return

        selected_nodes = [self.item_to_node[item] for item in selected_items if item in self.item_to_node]
        top_level = self.step_tree.get_top_level(selected_nodes)

        if not top_level:
            return

        repeat_node = self.step_tree.wrap_in_repeat(top_level)
        repeat_step = repeat_node.step

        self.save_current_macro()
        self.populate_steps()
        if self.step_tree:
            new_repeat_node = self.step_tree.find_node(repeat_step)
            if new_repeat_node:
                repeat_item = self.node_to_item.get(new_repeat_node)
                if repeat_item:
                    self.step_list.setCurrentItem(repeat_item)
                    self.step_list.expandItem(repeat_item)

    def on_move_step(self, direction: int) -> None:
        if not self.step_tree:
            return

        item = self.step_list.currentItem()
        if item is None:
            return

        node = self.item_to_node.get(item)
        if node is None:
            return

        moved_step = node.step
        moved = self.step_tree.move_step(node, direction)

        if moved:
            self.save_current_macro()
            self.populate_steps()

            new_node = self.step_tree.find_node(moved_step) if self.step_tree else None
            if new_node:
                new_item = self.node_to_item.get(new_node)
                if new_item:
                    self.step_list.setCurrentItem(new_item)
                    self.expand_item_ancestors(new_item)

    def on_run(self) -> None:
        if not self.current_runner:
            return

        runner = self.current_runner

        if runner.is_running():
            runner.stop()
            return

        if not runner.macro.get("meta", {}).get("enabled", True):
            return

        self.sync_macro_templates()
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
            else:
                if status.progress and status.repeat_total:
                    msg += f" | {t('status.loop_progress', progress=status.progress, total=status.repeat_total)}"

                current = getattr(runner, "current_step", None)

                if current:
                    flat = getattr(self, "flat_nodes", [])
                    try:
                        idx = next(i for i, n in enumerate(flat) if n.step is current)
                        _, summary = self.step_display(current)
                        msg += f" | #{idx + 1} {summary}"
                    except StopIteration:
                        pass

                if status.score > 0:
                    match_label = runner.template_label(status.match_name) if status.match_name else ""
                    msg += f" | {match_label} {int(status.score * 100)}%"

            self.status_label.setText(msg)
            self.set_editing_locked(True)
            self.highlight_current_step(runner)

            if self.conf.general.overlay_enabled:
                self.overlay.set_text(msg)
                self.overlay.set_running(True)

                if not self.overlay.isVisible():
                    self.overlay.show()
        else:
            self.btn_run.setText(f" {t('action.run')}")
            self.btn_run.setIcon(icon("play"))

            if self.overlay.isVisible():
                self.overlay.set_running(False)
                self.save_overlay_position()
                self.overlay.hide()

            if status.last_reason:
                elapsed_str = ""
                if status.elapsed_s:
                    e = int(status.elapsed_s)
                    elapsed_str = f" ({e // 60:02d}:{e % 60:02d})"
                self.status_label.setText(f"{runner.label}: {status.message or status.last_reason}{elapsed_str}")

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

    def save_overlay_position(self) -> None:
        """Save current overlay position to config."""
        pos = self.overlay.pos()
        self.conf.general.overlay_position = [pos.x(), pos.y()]
        cfg.save(self.conf)

    def set_editing_locked(self, locked: bool) -> None:
        self.btn_add_step.setEnabled(not locked)
        self.btn_del.setEnabled(not locked)
        self.btn_up.setEnabled(not locked)
        self.btn_down.setEnabled(not locked)
        self.macro_list.setEnabled(not locked)

    def highlight_current_step(self, runner: MacroRunner) -> None:
        current = getattr(runner, "current_step", None)

        if current is None:
            return

        if not self.step_tree:
            return

        node = self.step_tree.find_node(current)
        if node is None:
            return

        item = self.node_to_item.get(node)
        if item is None:
            return

        self.step_list.blockSignals(True)
        self.step_list.setCurrentItem(item)
        self.step_list.expandItem(item)
        self.step_list.scrollToItem(item)
        self.step_list.blockSignals(False)

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
        """Export macro as ZIP.

        The macro JSON already contains template metadata (label, capture_width,
        capture_height) inside macro["templates"], so no separate .json files
        are exported. Only the macro JSON and template PNGs are included.

        Backward compatibility: when importing old ZIPs that have separate
        templates/<name>.json files, the metadata is migrated into macro["templates"].
        """
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

    def on_import_json(self) -> None:
        """Import macro from ZIP.

        Backward compatibility: old ZIPs may contain separate templates/<name>.json
        metadata files. These are migrated into macro["templates"][name] during import
        so the macro JSON becomes the single source of truth.
        """
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

                macro_templates = macro.setdefault("templates", {})

                for n in refs:
                    png_destination = cfg.templates_dir(macro_name) / f"{n}.png"
                    if not png_destination.exists() or (overwrite and n in conflicts):
                        png_destination.write_bytes(zf.read(f"templates/{n}.png"))

                    meta_arc = f"templates/{n}.json"
                    if meta_arc in zf.namelist():
                        try:
                            legacy_meta = json.loads(zf.read(meta_arc))
                            entry = macro_templates.get(n, {"label": n})
                            for key in ("capture_width", "capture_height"):
                                if key in legacy_meta and key not in entry:
                                    entry[key] = legacy_meta[key]
                            macro_templates[n] = entry
                        except (ValueError, OSError):
                            pass

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
            '<a href="https://discord.gg/MZfks29yTA">Discord</a> · '
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
            self.step_tree = None
            self.flat_nodes = []
            self.item_to_node = {}
            self.node_to_item = {}
            self.clear_props()

        self.update_empty_states()

    def save_runner(self, runner: MacroRunner) -> None:
        if runner.source_path:
            runner.source_path.write_text(
                json.dumps(runner.macro, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
