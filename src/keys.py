"""Key and input simulation module.

Provides low-level keyboard and mouse input simulation.
"""

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


def tap(key: str, hold_ms: int = 90, gap_ms: int = 0, jitter_ms: int = 60) -> None:
    try:
        pdi.keyDown(key)
        logger.debug("keys: keyDown('{}') ok", key)
    except Exception as e:
        logger.error("keys: keyDown('{}') failed: {}", key, e)
        return
    sleep_ms(hold_ms, jitter_ms)
    try:
        pdi.keyUp(key)
        logger.debug("keys: keyUp('{}') ok (tap, hold={}ms)", key, hold_ms)
    except Exception as e:
        logger.error("keys: keyUp('{}') failed: {}", key, e)
    sleep_ms(gap_ms, jitter_ms)


@contextmanager
def held(key: str) -> Generator[None, None, None]:
    try:
        pdi.keyDown(key)
        logger.debug("keys: held('{}') start", key)
    except Exception as e:
        logger.error("keys: held('{}') keyDown failed: {}", key, e)
        raise
    try:
        yield
    finally:
        try:
            pdi.keyUp(key)
            logger.debug("keys: held('{}') end", key)
        except Exception as e:
            logger.error("keys: held('{}') keyUp failed: {}", key, e)
