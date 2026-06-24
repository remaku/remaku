import re
from collections.abc import Callable
from dataclasses import dataclass
from threading import Lock

import cv2
import numpy as np
from rapidocr_onnxruntime import RapidOCR


class OcrUnavailableError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class NumberRegion:
    x: int
    y: int
    width: int
    height: int
    relative: bool = True
    capture_width: int = 0
    capture_height: int = 0


NumberOcrAdapter = Callable[[np.ndarray], str]
rapidocr_engine: RapidOCR | None = None
rapidocr_engine_lock = Lock()


def compare_number(value: int, operator: str, expected: int) -> bool:
    if operator == "=":
        return value == expected

    if operator == "≠":
        return value != expected

    if operator == ">":
        return value > expected

    if operator == "≥":
        return value >= expected

    if operator == "<":
        return value < expected

    if operator == "≤":
        return value <= expected

    return False


def resolve_region(
    region: NumberRegion, frame_shape: tuple[int, ...], origin_left: int = 0, origin_top: int = 0
) -> NumberRegion:
    frame_height, frame_width = frame_shape[:2]
    x = region.x if region.relative else region.x - origin_left
    y = region.y if region.relative else region.y - origin_top
    width = region.width
    height = region.height

    if region.capture_width > 0 and region.capture_height > 0:
        scale_x = frame_width / region.capture_width
        scale_y = frame_height / region.capture_height
        x = int(x * scale_x)
        y = int(y * scale_y)
        width = int(width * scale_x)
        height = int(height * scale_y)

    left = max(0, min(frame_width, x))
    top = max(0, min(frame_height, y))
    right = max(left, min(frame_width, x + width))
    bottom = max(top, min(frame_height, y + height))

    return NumberRegion(left, top, right - left, bottom - top, True, frame_width, frame_height)


def crop_region(frame: np.ndarray, region: NumberRegion) -> np.ndarray:
    if region.width <= 0 or region.height <= 0:
        return np.empty((0, 0), dtype=np.uint8)

    return frame[region.y : region.y + region.height, region.x : region.x + region.width]


def preprocess_number_image(image: np.ndarray) -> np.ndarray:
    if image.size == 0:
        return image

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image

    scale = max(2, int(96 / max(1, gray.shape[0])))
    resized = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    blurred = cv2.GaussianBlur(resized, (3, 3), 0)
    _, threshold = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)

    return threshold


def parse_digits(text: str) -> int | None:
    digits = "".join(re.findall(r"\d+", text))
    if not digits:
        return None

    return int(digits)


def rapidocr_digits(image: np.ndarray) -> str:
    global rapidocr_engine

    if rapidocr_engine is None:
        with rapidocr_engine_lock:
            if rapidocr_engine is None:
                try:
                    rapidocr_engine = RapidOCR()
                except Exception as error:
                    raise OcrUnavailableError("rapidocr_unavailable") from error

    result, _ = rapidocr_engine(image, use_det=False, use_cls=False)
    return rapidocr_result_text(result)


def rapidocr_result_text(result) -> str:
    if not result:
        return ""

    parts = []
    for item in result:
        if not isinstance(item, list | tuple) or len(item) < 2:
            continue

        if isinstance(item[0], str):
            parts.append((0.0, item[0]))
            continue

        if isinstance(item[1], str):
            parts.append((box_left(item[0]), item[1]))

    return "".join(text for _, text in sorted(parts, key=lambda part: part[0]))


def box_left(box) -> float:
    try:
        return min(float(point[0]) for point in box)
    except (TypeError, ValueError, IndexError):
        return 0.0


def read_number(
    frame: np.ndarray,
    region: NumberRegion,
    adapter: NumberOcrAdapter | None = None,
    origin_left: int = 0,
    origin_top: int = 0,
) -> int | None:
    resolved = resolve_region(region, frame.shape, origin_left, origin_top)
    cropped = crop_region(frame, resolved)
    processed = preprocess_number_image(cropped)

    if processed.size == 0:
        return None

    ocr_adapter = adapter or rapidocr_digits
    return parse_digits(ocr_adapter(processed))
