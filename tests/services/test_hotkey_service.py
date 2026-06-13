from remaku.models.macro_model import Macro, MacroMeta, MacroModel, MacroSummary
from remaku.services import hotkey_service
from remaku.services.hotkey_service import HotkeyService


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
    service = HotkeyService(
        FakeMacroModel({"macro": Macro(meta=MacroMeta(id="macro", label="Macro", hotkey="ctrl+f1"))}),
        lambda: 99,
    )

    service.register_hotkeys()

    assert register_calls == [(99, 0xBF00, 0x0002, 0x70)]
    assert service.hotkey_ids == []
    assert service.hotkey_map == {}
