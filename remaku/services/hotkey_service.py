import contextlib
import logging
from collections.abc import Callable
from typing import Protocol

import win32api
import win32con
import win32gui

from remaku.models.macro_model import Macro, MacroSummary

logger = logging.getLogger(__name__)


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
            return win32api.VkKeyScan(key) & 0xFF

        return 0

    def macro_id_for_hotkey(self, hid: int) -> str | None:
        return self.hotkey_map.get(hid)
