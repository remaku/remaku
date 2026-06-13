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

        self.init_backend()

        logger.debug("capture: backend={}", self.backend)
        logger.debug("capture: screen={}x{}", self.screen_width, self.screen_height)

    def init_backend(self) -> None:
        try:
            self.cam = bettercam.create(output_color="BGR", device_idx=0)
            frame = self.cam.grab(region=(0, 0, self.cam.width, self.cam.height))

            if frame is None:
                raise RuntimeError("initial grab returned None")

            self.screen_width = self.cam.width
            self.screen_height = self.cam.height
            self.backend = CaptureBackend.BETTERCAM
            return
        except Exception as error:
            logger.warning("capture: bettercam unavailable, falling back to mss: {}", error)
            self.cam = None

        sct = mss.mss()
        monitor = sct.monitors[0]
        self.sct = sct
        self.screen_width = monitor["width"]
        self.screen_height = monitor["height"]
        self.backend = CaptureBackend.MSS

    def grab(self, rect: Rect) -> np.ndarray | None:
        left = max(0, rect.left)
        top = max(0, rect.top)
        right = min(self.screen_width, rect.right)
        bottom = min(self.screen_height, rect.bottom)

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
        if self.backend == CaptureBackend.BETTERCAM:
            if self.cam is None:
                return None

            return self.cam.grab(region=(left, top, right, bottom))

        if self.sct is None:
            return None

        screenshot = self.sct.grab({"left": left, "top": top, "width": right - left, "height": bottom - top})
        return np.asarray(screenshot)[:, :, :3]

    def close(self) -> None:
        with contextlib.suppress(Exception):
            if self.cam is not None:
                del self.cam

        with contextlib.suppress(Exception):
            if self.sct is not None:
                self.sct.close()


def make_grabber() -> Grabber:
    return Grabber()
