import random
import time
from collections.abc import Generator
from contextlib import contextmanager

import pydirectinput as pdi
import win32api
import win32con
import win32gui
from loguru import logger

from remaku.core import keymap

pdi.PAUSE = 0
pdi.FAILSAFE = False

MODIFIER_KEY_ALIASES = {
    "control": "ctrl",
    "cmd": "win",
    "command": "win",
    "meta": "win",
}


def sleep_ms(ms: int, jitter_ms: int = 0) -> None:
    extra = random.uniform(0, jitter_ms) if jitter_ms > 0 else 0
    time.sleep((ms + extra) / 1000.0)


def normalize_key_name(key: str) -> str:
    normalized = key.strip().lower()
    return MODIFIER_KEY_ALIASES.get(normalized, normalized)


def parse_key_combo(key: str) -> list[str]:
    return [normalize_key_name(part) for part in key.split("+") if part.strip()]


def key_lparam(vk_code: int, *, key_up: bool = False) -> int:
    scan_code = win32api.MapVirtualKey(vk_code, 0)
    lparam = 1 | (scan_code << 16)

    if key_up:
        lparam |= 1 << 30
        lparam |= 1 << 31

    return lparam


def post_key(hwnd: int, key: str, is_down: bool) -> bool:
    vk_code = keymap.key_to_vk(key)

    if not vk_code and len(key) == 1 and "a" <= key.lower() <= "z":
        vk_code = ord(key.upper())

    if not vk_code and len(key) == 1 and "0" <= key <= "9":
        vk_code = ord(key)

    if not vk_code:
        return False

    message = win32con.WM_KEYDOWN if is_down else win32con.WM_KEYUP
    win32gui.PostMessage(hwnd, message, vk_code, key_lparam(vk_code, key_up=not is_down))
    return True


def tap_background(hwnd: int, key: str, hold_ms: int, jitter_ms: int) -> bool:
    keys = parse_key_combo(key)
    if not keys:
        return False

    pressed_keys: list[str] = []

    try:
        for combo_key in keys:
            if not post_key(hwnd, combo_key, True):
                release_background_keys(hwnd, pressed_keys)
                return False

            pressed_keys.append(combo_key)
            logger.debug("keys: PostMessage keyDown('{}') ok", combo_key)
    except Exception as error:
        logger.error("keys: PostMessage keyDown('{}') failed: {}", key, error)
        release_background_keys(hwnd, pressed_keys)
        return False

    sleep_ms(hold_ms, jitter_ms)
    release_background_keys(hwnd, pressed_keys)
    return True


def release_background_keys(hwnd: int, pressed_keys: list[str]) -> None:
    for key in reversed(pressed_keys):
        try:
            post_key(hwnd, key, False)
            logger.debug("keys: PostMessage keyUp('{}') ok", key)
        except Exception as error:
            logger.error("keys: PostMessage keyUp('{}') failed: {}", key, error)


def tap(key: str, hold_ms: int = 90, jitter_ms: int = 60, hwnd: int | None = None) -> None:
    if hwnd is not None:
        tap_background(hwnd, key, hold_ms, jitter_ms)
        return

    keys = parse_key_combo(key)
    pressed_keys: list[str] = []

    try:
        for combo_key in keys:
            pdi.keyDown(combo_key)
            pressed_keys.append(combo_key)
            logger.debug("keys: keyDown('{}') ok", combo_key)
    except Exception as error:
        logger.error("keys: keyDown('{}') failed: {}", key, error)
        release_pressed_keys(pressed_keys)
        return

    sleep_ms(hold_ms, jitter_ms)
    release_pressed_keys(pressed_keys)


def release_pressed_keys(pressed_keys: list[str]) -> None:
    for key in reversed(pressed_keys):
        try:
            pdi.keyUp(key)
            logger.debug("keys: keyUp('{}') ok", key)
        except Exception as error:
            logger.error("keys: keyUp('{}') failed: {}", key, error)


def type_text(text: str, interval_ms: int = 0, hwnd: int | None = None) -> None:
    safe_interval_ms = max(0, interval_ms)
    interval_seconds = safe_interval_ms / 1000
    normalized_text = text.replace("\r\n", "\n").replace("\r", "\n")

    try:
        for index, char in enumerate(normalized_text):
            if index > 0 and interval_seconds > 0:
                time.sleep(interval_seconds)

            if char == "\n":
                if hwnd is not None:
                    post_key(hwnd, "enter", True)
                    post_key(hwnd, "enter", False)
                else:
                    pdi.press("enter", _pause=False)
            elif hwnd is not None:
                win32gui.PostMessage(hwnd, win32con.WM_CHAR, ord(char), 1)
            else:
                pdi.unicode_press(char, _pause=False)

        logger.debug("keys: type_text ok (chars={}, interval={}ms)", len(normalized_text), safe_interval_ms)
    except Exception as error:
        logger.error("keys: type_text failed: {}", error)


@contextmanager
def held(key: str, hwnd: int | None = None) -> Generator[None, None, None]:
    if hwnd is not None:
        keys = parse_key_combo(key)
        pressed_keys: list[str] = []

        try:
            for combo_key in keys:
                if not post_key(hwnd, combo_key, True):
                    release_background_keys(hwnd, pressed_keys)
                    raise RuntimeError(f"unsupported background key: {combo_key}")

                pressed_keys.append(combo_key)
                logger.debug("keys: held('{}') PostMessage keyDown ok", combo_key)
        except Exception as error:
            logger.error("keys: held('{}') PostMessage keyDown failed: {}", key, error)
            release_background_keys(hwnd, pressed_keys)
            raise

        try:
            yield
        finally:
            release_background_keys(hwnd, pressed_keys)
            logger.debug("keys: held('{}') PostMessage end", key)

        return

    keys = parse_key_combo(key)
    pressed_keys: list[str] = []

    try:
        for combo_key in keys:
            pdi.keyDown(combo_key)
            pressed_keys.append(combo_key)
            logger.debug("keys: held('{}') keyDown ok", combo_key)
    except Exception as error:
        logger.error("keys: held('{}') keyDown failed: {}", key, error)
        release_pressed_keys(pressed_keys)
        raise

    try:
        yield
    finally:
        release_pressed_keys(pressed_keys)
        logger.debug("keys: held('{}') end", key)


def is_valid_key(key: str) -> bool:
    keys = parse_key_combo(key)
    return bool(keys) and all(pdi.isValidKey(combo_key) for combo_key in keys)


def screen_to_client_lparam(hwnd: int, x: int, y: int) -> int:
    client_x, client_y = win32gui.ScreenToClient(hwnd, (x, y))
    return win32api.MAKELONG(client_x, client_y)


def post_mouse_click(hwnd: int, button: str, x: int, y: int) -> bool:
    messages = {
        "left": (win32con.WM_LBUTTONDOWN, win32con.WM_LBUTTONUP, win32con.MK_LBUTTON),
        "right": (win32con.WM_RBUTTONDOWN, win32con.WM_RBUTTONUP, win32con.MK_RBUTTON),
        "middle": (win32con.WM_MBUTTONDOWN, win32con.WM_MBUTTONUP, win32con.MK_MBUTTON),
    }
    message_pair = messages.get(button)

    if message_pair is None:
        return False

    down_message, up_message, wparam = message_pair
    lparam = screen_to_client_lparam(hwnd, x, y)
    win32gui.PostMessage(hwnd, win32con.WM_MOUSEMOVE, 0, lparam)
    win32gui.PostMessage(hwnd, down_message, wparam, lparam)
    win32gui.PostMessage(hwnd, up_message, 0, lparam)
    return True


def mouse_click(button: str, x: int, y: int, hwnd: int | None = None, down_up_delay_ms: int = 0) -> None:
    if hwnd is not None:
        try:
            if post_mouse_click(hwnd, button, x, y):
                logger.debug("keys: PostMessage {} click ok", button)
        except Exception as error:
            logger.error("keys: PostMessage {} click failed: {}", button, error)

        return

    try:
        pdi.moveTo(x, y)
        logger.debug("keys: moveTo({}, {}) ok", x, y)
    except Exception as error:
        logger.error("keys: moveTo({}, {}) failed: {}", x, y, error)
        return

    try:
        if button == "left":
            pdi.mouseDown(button="left")
            sleep_ms(down_up_delay_ms)
            pdi.mouseUp(button="left")
        elif button == "right":
            pdi.mouseDown(button="right")
            sleep_ms(down_up_delay_ms)
            pdi.mouseUp(button="right")
        elif button == "middle":
            pdi.mouseDown(button="middle")
            sleep_ms(down_up_delay_ms)
            pdi.mouseUp(button="middle")
        logger.debug("keys: {} click ok", button)
    except Exception as error:
        logger.error("keys: {} click failed: {}", button, error)


def mouse_move(x: int, y: int, hwnd: int | None = None) -> None:
    if hwnd is not None:
        try:
            win32gui.PostMessage(hwnd, win32con.WM_MOUSEMOVE, 0, screen_to_client_lparam(hwnd, x, y))
            logger.debug("keys: PostMessage moveTo({}, {}) ok", x, y)
        except Exception as error:
            logger.error("keys: PostMessage moveTo({}, {}) failed: {}", x, y, error)

        return

    try:
        pdi.moveTo(x, y)
        logger.debug("keys: moveTo({}, {}) ok", x, y)
    except Exception as error:
        logger.error("keys: moveTo({}, {}) failed: {}", x, y, error)


def mouse_scroll(clicks: int, interval_ms: int = 0, hwnd: int | None = None) -> None:
    step = 1 if clicks > 0 else -1
    remaining = abs(clicks)

    for _ in range(remaining):
        try:
            if hwnd is not None:
                delta = win32con.WHEEL_DELTA * step
                win32gui.PostMessage(hwnd, win32con.WM_MOUSEWHEEL, delta << 16, 0)
            else:
                pdi.scroll(step)
        except Exception as error:
            logger.error("keys: scroll({}) failed: {}", step, error)
            return

        if interval_ms > 0:
            sleep_ms(interval_ms)

    logger.debug("keys: scroll({} clicks, interval={}ms) ok", clicks, interval_ms)
