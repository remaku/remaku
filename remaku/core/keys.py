import random
import time
from collections.abc import Generator
from contextlib import contextmanager

import pydirectinput as pdi
from loguru import logger

pdi.PAUSE = 0
pdi.FAILSAFE = False


def sleep_ms(ms: int, jitter_ms: int = 0) -> None:
    extra = random.uniform(0, jitter_ms) if jitter_ms > 0 else 0
    time.sleep((ms + extra) / 1000.0)


def tap(key: str, hold_ms: int = 90, jitter_ms: int = 60) -> None:
    try:
        pdi.keyDown(key)
        logger.debug("keys: keyDown('{}') ok", key)
    except Exception as error:
        logger.error("keys: keyDown('{}') failed: {}", key, error)
        return

    sleep_ms(hold_ms, jitter_ms)

    try:
        pdi.keyUp(key)
        logger.debug("keys: keyUp('{}') ok (tap, hold={}ms)", key, hold_ms)
    except Exception as error:
        logger.error("keys: keyUp('{}') failed: {}", key, error)


def type_text(text: str, interval_ms: int = 0) -> None:
    safe_interval_ms = max(0, interval_ms)
    interval_seconds = safe_interval_ms / 1000
    normalized_text = text.replace("\r\n", "\n").replace("\r", "\n")

    try:
        for index, char in enumerate(normalized_text):
            if index > 0 and interval_seconds > 0:
                time.sleep(interval_seconds)

            if char == "\n":
                pdi.press("enter", _pause=False)
            else:
                pdi.unicode_press(char, _pause=False)

        logger.debug("keys: type_text ok (chars={}, interval={}ms)", len(normalized_text), safe_interval_ms)
    except Exception as error:
        logger.error("keys: type_text failed: {}", error)


@contextmanager
def held(key: str) -> Generator[None, None, None]:
    try:
        pdi.keyDown(key)
        logger.debug("keys: held('{}') start", key)
    except Exception as error:
        logger.error("keys: held('{}') keyDown failed: {}", key, error)
        raise

    try:
        yield
    finally:
        try:
            pdi.keyUp(key)
            logger.debug("keys: held('{}') end", key)
        except Exception as error:
            logger.error("keys: held('{}') keyUp failed: {}", key, error)


def is_valid_key(key: str) -> bool:
    return pdi.isValidKey(key)


def mouse_click(button: str, x: int, y: int) -> None:
    try:
        pdi.moveTo(x, y)
        logger.debug("keys: moveTo({}, {}) ok", x, y)
    except Exception as error:
        logger.error("keys: moveTo({}, {}) failed: {}", x, y, error)
        return

    try:
        if button == "left":
            pdi.leftClick()
        elif button == "right":
            pdi.rightClick()
        elif button == "middle":
            pdi.middleClick()
        logger.debug("keys: {} click ok", button)
    except Exception as error:
        logger.error("keys: {} click failed: {}", button, error)


def mouse_move(x: int, y: int) -> None:
    try:
        pdi.moveTo(x, y)
        logger.debug("keys: moveTo({}, {}) ok", x, y)
    except Exception as error:
        logger.error("keys: moveTo({}, {}) failed: {}", x, y, error)


def mouse_scroll(clicks: int, interval_ms: int = 0) -> None:
    step = 1 if clicks > 0 else -1
    remaining = abs(clicks)

    for _ in range(remaining):
        try:
            pdi.scroll(step)
        except Exception as error:
            logger.error("keys: scroll({}) failed: {}", step, error)
            return

        if interval_ms > 0:
            sleep_ms(interval_ms)

    logger.debug("keys: scroll({} clicks, interval={}ms) ok", clicks, interval_ms)
