from remaku.models.config_model import AppConfig
from remaku.models.macro_model import Macro, MacroMeta, MacroModel, MacroSummary
from remaku.services import hotkey_service
from remaku.services.hotkey_service import PAUSE_HOTKEY_ID, HotkeyService


class FakeMacroModel:
    def __init__(self, macros: dict[str, Macro]) -> None:
        self.macros = macros

    def list_macros(self) -> list[MacroSummary]:
        return [MacroSummary(id=macro_id, label=macro_id.upper(), path=f"{macro_id}.json") for macro_id in self.macros]

    def load(self, macro_id: str) -> Macro | None:
        return self.macros.get(macro_id)


def test_parse_hotkey_handles_modifiers_and_named_key() -> None:
    service = HotkeyService(MacroModel(), lambda: 99)

    assert service.parse_hotkey("CTRL+Alt+enter") == (0x0002 | 0x0001, 0x0D)
    assert service.parse_hotkey("shift+f1") == (0x0004, 0x70)
    assert service.parse_hotkey("ctrl+break") == (0x0002, 0x03)


def test_key_to_vk_uses_vk_key_scan_for_single_character(monkeypatch) -> None:
    monkeypatch.setattr(hotkey_service.win32api, "VkKeyScan", lambda key: ord(key))
    service = HotkeyService(MacroModel(), lambda: 99)

    assert service.key_to_vk("a") == ord("a")


def test_register_hotkeys_unregisters_previous_and_skips_invalid(monkeypatch) -> None:
    register_calls: list[tuple[int, int, int, int]] = []
    unregister_calls: list[tuple[int, int]] = []

    def fake_register(hwnd: int, hid: int, mods: int, vk: int) -> None:
        register_calls.append((hwnd, hid, mods, vk))

    def fake_unregister(hwnd: int, hid: int) -> None:
        unregister_calls.append((hwnd, hid))

    monkeypatch.setattr(hotkey_service.win32gui, "RegisterHotKey", fake_register)
    monkeypatch.setattr(hotkey_service.win32gui, "UnregisterHotKey", fake_unregister)
    config = AppConfig()
    config.general.pause_hotkey = ""
    monkeypatch.setattr(hotkey_service.config_model, "config", config)
    macros = {
        "enabled": Macro(meta=MacroMeta(id="enabled", label="Enabled", hotkey="ctrl+f1", enabled=True)),
        "disabled": Macro(meta=MacroMeta(id="disabled", label="Disabled", hotkey="ctrl+f2", enabled=False)),
        "invalid": Macro(meta=MacroMeta(id="invalid", label="Invalid", hotkey="ctrl+unknown", enabled=True)),
        "empty": Macro(meta=MacroMeta(id="empty", label="Empty", hotkey="", enabled=True)),
    }
    service = HotkeyService(FakeMacroModel(macros), lambda: 99)
    service.hotkey_ids = [0xBF99]
    service.hotkey_map = {0xBF99: "old"}

    service.register_hotkeys()

    assert unregister_calls == [(99, 0xBF99)]
    assert register_calls == [(99, 0xBF00, 0x0002, 0x70)]
    assert service.hotkey_ids == [0xBF00]
    assert service.hotkey_map == {0xBF00: "enabled"}


def test_register_hotkeys_does_not_store_failed_registration(monkeypatch) -> None:
    register_calls: list[tuple[int, int, int, int]] = []

    def fake_register(hwnd: int, hid: int, mods: int, vk: int) -> None:
        register_calls.append((hwnd, hid, mods, vk))
        raise Exception("failed")

    monkeypatch.setattr(hotkey_service.win32gui, "RegisterHotKey", fake_register)
    monkeypatch.setattr(hotkey_service.win32gui, "UnregisterHotKey", lambda hwnd, hid: None)
    config = AppConfig()
    config.general.pause_hotkey = ""
    monkeypatch.setattr(hotkey_service.config_model, "config", config)
    service = HotkeyService(
        FakeMacroModel({"macro": Macro(meta=MacroMeta(id="macro", label="Macro", hotkey="ctrl+f1"))}),
        lambda: 99,
    )

    service.register_hotkeys()

    assert register_calls == [(99, 0xBF00, 0x0002, 0x70)]
    assert service.hotkey_ids == []
    assert service.hotkey_map == {}


def test_register_hotkeys_registers_pause_hotkey(monkeypatch) -> None:
    register_calls: list[tuple[int, int, int, int]] = []
    config = AppConfig()
    config.general.pause_hotkey = "ctrl+alt+p"

    monkeypatch.setattr(hotkey_service.config_model, "config", config)
    monkeypatch.setattr(hotkey_service.win32gui, "RegisterHotKey", lambda *args: register_calls.append(args))
    monkeypatch.setattr(hotkey_service.win32gui, "UnregisterHotKey", lambda hwnd, hid: None)
    monkeypatch.setattr(hotkey_service.win32api, "VkKeyScan", lambda key: ord(key.upper()))
    service = HotkeyService(FakeMacroModel({}), lambda: 99)

    service.register_hotkeys()

    assert register_calls == [(99, PAUSE_HOTKEY_ID, 0x0002 | 0x0001, ord("P"))]
    assert service.hotkey_ids == [PAUSE_HOTKEY_ID]
    assert service.is_pause_hotkey(PAUSE_HOTKEY_ID)


def test_macro_hotkey_id_near_pause_id_is_not_treated_as_pause(monkeypatch) -> None:
    register_calls: list[tuple[int, int, int, int]] = []
    config = AppConfig()
    config.general.pause_hotkey = ""
    macros = {
        str(index): Macro(
            meta=MacroMeta(
                id=str(index),
                label=str(index),
                hotkey="ctrl+f1" if index == 254 else "",
                enabled=True,
            )
        )
        for index in range(255)
    }

    monkeypatch.setattr(hotkey_service.config_model, "config", config)
    monkeypatch.setattr(hotkey_service.win32gui, "RegisterHotKey", lambda *args: register_calls.append(args))
    monkeypatch.setattr(hotkey_service.win32gui, "UnregisterHotKey", lambda hwnd, hid: None)
    service = HotkeyService(FakeMacroModel(macros), lambda: 99)

    service.register_hotkeys()

    macro_hotkey_id = 0xBF00 + 254
    assert register_calls == [(99, macro_hotkey_id, 0x0002, 0x70)]
    assert not service.is_pause_hotkey(macro_hotkey_id)
    assert service.macro_id_for_hotkey(macro_hotkey_id) == "254"
