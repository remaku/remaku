import contextlib
import logging
from collections.abc import Callable
from typing import Protocol

import win32api
import win32con
import win32gui

from remaku.core.keymap import key_to_vk as shared_key_to_vk
from remaku.models.config_model import config_model
from remaku.models.macro_model import Macro, MacroSummary

logger = logging.getLogger(__name__)
PAUSE_HOTKEY_ID = 0xBEFE


class HotkeyMacroModel(Protocol):
    def list_macros(self) -> list[MacroSummary]: ...

    def load(self, macro_id: str) -> Macro | None: ...


class HotkeyService:
    def __init__(
        self,
        macro_model: HotkeyMacroModel,
        window_id_provider: Callable[[], int],
    ) -> None:
        self.macro_model = macro_model
        self.window_id_provider = window_id_provider
        self.hotkey_ids: list[int] = []
        self.hotkey_map: dict[int, str] = {}

    def register_hotkeys(self) -> None:
        window_id = self.window_id_provider()

        for hid in self.hotkey_ids:
            with contextlib.suppress(OSError):
                logger.debug("Unregistering hotkey id=%d", hid)
                win32gui.UnregisterHotKey(window_id, hid)

        self.hotkey_ids = []
        self.hotkey_map = {}

        self.register_pause_hotkey(window_id)

        for index, summary in enumerate(self.macro_model.list_macros()):
            macro = self.macro_model.load(summary.id)
            if macro is None or not macro.meta.enabled or not macro.meta.hotkey:
                continue

            mods, vk = self.parse_hotkey(macro.meta.hotkey)
            if vk == 0:
                continue

            hid = 0xBF00 + index

            try:
                win32gui.RegisterHotKey(window_id, hid, mods, vk)
                self.hotkey_ids.append(hid)
                self.hotkey_map[hid] = summary.id
                logger.info("Registered hotkey: %s -> %s", macro.meta.hotkey, summary.label)
            except Exception:
                logger.warning("Hotkey registration failed: %s", macro.meta.hotkey)

    def register_pause_hotkey(self, window_id: int) -> None:
        hotkey = config_model.config.general.pause_hotkey.strip()
        if not hotkey:
            return

        mods, vk = self.parse_hotkey(hotkey)
        if vk == 0:
            return

        try:
            win32gui.RegisterHotKey(window_id, PAUSE_HOTKEY_ID, mods, vk)
            self.hotkey_ids.append(PAUSE_HOTKEY_ID)
            logger.info("Registered pause hotkey: %s", hotkey)
        except Exception:
            logger.warning("Pause hotkey registration failed: %s", hotkey)

    def parse_hotkey(self, hotkey: str) -> tuple[int, int]:
        mods = 0
        vk = 0
        parts = hotkey.lower().split("+")

        for part in parts:
            if part == "ctrl":
                mods |= win32con.MOD_CONTROL
            elif part == "alt":
                mods |= win32con.MOD_ALT
            elif part == "shift":
                mods |= win32con.MOD_SHIFT
            else:
                vk = self.key_to_vk(part)

        return mods, vk

    def key_to_vk(self, key: str) -> int:
        vk = shared_key_to_vk(key)
        if vk != 0:
            return vk

        if len(key) == 1:
            return win32api.VkKeyScan(key) & 0xFF

        return 0

    def macro_id_for_hotkey(self, hid: int) -> str | None:
        return self.hotkey_map.get(hid)

    def is_pause_hotkey(self, hid: int) -> bool:
        return hid == PAUSE_HOTKEY_ID
