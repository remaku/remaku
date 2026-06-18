import contextlib
from enum import StrEnum

import bettercam
import mss
import numpy as np
from loguru import logger
from mss.base import MSSBase

from remaku.core.window import Rect


class CaptureBackend(StrEnum):
    BETTERCAM = "bettercam"
    MSS = "mss"


class Grabber:
    def __init__(self) -> None:
        self.backend = CaptureBackend.BETTERCAM
        self.cam: bettercam.BetterCam | None = None
        self.sct: MSSBase | None = None
        self.last_frame: np.ndarray = np.empty((0, 0, 3), dtype=np.uint8)
        self.screen_left = 0
        self.screen_top = 0

        self.init_backend()

        logger.debug("capture: backend={}", self.backend)
        logger.debug("capture: screen={}x{}", self.screen_width, self.screen_height)

    def init_backend(self) -> None:
        try:
            self.sct = mss.mss()
            monitor = self.sct.monitors[0]
            self.screen_left = int(monitor.get("left", 0))
            self.screen_top = int(monitor.get("top", 0))
            self.screen_width = int(monitor["width"])
            self.screen_height = int(monitor["height"])
        except Exception as error:
            logger.warning("capture: mss unavailable: {}", error)
            self.sct = None
            self.screen_width = 0
            self.screen_height = 0

        try:
            self.cam = bettercam.create(output_color="BGR", device_idx=0)
            frame = self.cam.grab(region=(0, 0, self.cam.width, self.cam.height))

            if frame is None:
                raise RuntimeError("initial grab returned None")

            self.backend = CaptureBackend.BETTERCAM
            return
        except Exception as error:
            logger.warning("capture: bettercam unavailable, falling back to mss: {}", error)
            self.cam = None

        if self.sct is None:
            raise RuntimeError("No capture backend is available")

        self.backend = CaptureBackend.MSS

    def grab(self, rect: Rect) -> np.ndarray | None:
        left = max(self.screen_left, rect.left)
        top = max(self.screen_top, rect.top)
        right = min(self.screen_left + self.screen_width, rect.right)
        bottom = min(self.screen_top + self.screen_height, rect.bottom)

        if right <= left or bottom <= top:
            return None

        frame = self.grab_frame(left, top, right, bottom)

        if frame is not None:
            self.last_frame = frame
            return frame

        if self.last_frame.size == 0:
            return None

        return self.last_frame

    def grab_frame(self, left: int, top: int, right: int, bottom: int) -> np.ndarray | None:
        if self.backend == CaptureBackend.BETTERCAM and self.bettercam_supports_region(left, top, right, bottom):
            if self.cam is None:
                return None

            return self.cam.grab(region=(left, top, right, bottom))

        if self.sct is None:
            return None

        screenshot = self.sct.grab({"left": left, "top": top, "width": right - left, "height": bottom - top})
        return np.asarray(screenshot)[:, :, :3]

    def bettercam_supports_region(self, left: int, top: int, right: int, bottom: int) -> bool:
        if self.cam is None:
            return False

        return left >= 0 and top >= 0 and right <= self.cam.width and bottom <= self.cam.height

    def close(self) -> None:
        with contextlib.suppress(Exception):
            if self.cam is not None:
                del self.cam

        with contextlib.suppress(Exception):
            if self.sct is not None:
                self.sct.close()


def make_grabber() -> Grabber:
    return Grabber()
