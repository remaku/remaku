VK_TO_NAME: dict[int, str] = {
    0x03: "break",
    0x08: "backspace",
    0x09: "tab",
    0x0D: "enter",
    0x10: "shift",
    0x11: "ctrl",
    0x12: "alt",
    0x13: "pause",
    0x14: "capslock",
    0x1B: "esc",
    0x20: "space",
    0x21: "pageup",
    0x22: "pagedown",
    0x23: "end",
    0x24: "home",
    0x25: "left",
    0x26: "up",
    0x27: "right",
    0x28: "down",
    0x2D: "insert",
    0x2E: "delete",
    0x5B: "win",
    0x5C: "win",
    0x60: "num0",
    0x61: "num1",
    0x62: "num2",
    0x63: "num3",
    0x64: "num4",
    0x65: "num5",
    0x66: "num6",
    0x67: "num7",
    0x68: "num8",
    0x69: "num9",
    0x6A: "multiply",
    0x6B: "add",
    0x6D: "subtract",
    0x6E: "decimal",
    0x6F: "divide",
    0xBA: ";",
    0xBB: "=",
    0xBC: ",",
    0xBD: "-",
    0xBE: ".",
    0xBF: "/",
    0xC0: "`",
    0xDB: "[",
    0xDC: "\\",
    0xDD: "]",
    0xDE: "'",
    0xE2: "\\",
    0xA0: "shift",
    0xA1: "shift",
    0xA2: "ctrl",
    0xA3: "ctrl",
    0xA4: "alt",
    0xA5: "alt",
}

for index in range(12):
    VK_TO_NAME[0x70 + index] = f"f{index + 1}"

_SYNONYMS: dict[str, str] = {
    "escape": "esc",
    "return": "enter",
}

_NAME_TO_VK: dict[str, int] = {
    "shift": 0x10,
    "ctrl": 0x11,
    "alt": 0x12,
    "win": 0x5B,
    "\\": 0xDC,
}

for vk_code, name in VK_TO_NAME.items():
    if name not in _NAME_TO_VK:
        _NAME_TO_VK[name] = vk_code


def vk_to_key(vk_code: int) -> str:
    if 0x30 <= vk_code <= 0x39:
        return chr(vk_code).lower()

    if 0x41 <= vk_code <= 0x5A:
        return chr(vk_code).lower()

    return VK_TO_NAME.get(vk_code, "")


def key_to_vk(key: str) -> int:
    canonical = _SYNONYMS.get(key, key.lower())

    return _NAME_TO_VK.get(canonical, 0)
