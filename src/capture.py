"""Screen capture module.

Provides screen capture using BetterCam (DXGI Desktop Duplication).
"""

import contextlib

import bettercam
import numpy as np
from loguru import logger

from window import Rect


class Grabber:
    def __init__(self) -> None:
        self.cam = bettercam.create(output_color="BGR")
        self.last_frame: np.ndarray = np.empty((0, 0, 3), dtype=np.uint8)
        self.screen_width = self.cam.width
        self.screen_height = self.cam.height
        logger.debug("capture: screen={}x{}", self.screen_width, self.screen_height)

    def grab(self, rect: Rect) -> np.ndarray | None:
        region = (rect.left, rect.top, rect.right, rect.bottom)
        frame = self.cam.grab(region=region)

        if frame is not None:
            self.last_frame = frame
            return frame

        if self.last_frame.size == 0:
            return None

        return self.last_frame

    def close(self) -> None:
        with contextlib.suppress(Exception):
            del self.cam


def make_grabber() -> Grabber:
    return Grabber()
