import cv2
import numpy as np
from loguru import logger

from remaku.paths import template_path


def load_templates(names: list[str], macro_name: str = "") -> dict[str, np.ndarray]:
    out: dict[str, np.ndarray] = {}

    for name in names:
        path = template_path(macro_name, name)

        if not path.exists():
            logger.warning("vision: template file not found: {}", name)
            continue

        image = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_GRAYSCALE)

        if image is None:
            logger.warning("vision: failed to read template: {}", path)
            continue

        out[name] = image

    return out


def to_gray(frame: np.ndarray) -> np.ndarray:
    if frame.ndim == 2:
        return frame

    return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)


def scale_template(template: np.ndarray, frame_shape: tuple[int, ...], capture_size: tuple[int, int]) -> np.ndarray:
    frame_height, frame_width = frame_shape[:2]
    capture_width, capture_height = capture_size

    if frame_width == capture_width and frame_height == capture_height:
        return template

    scale = min(frame_width / capture_width, frame_height / capture_height)
    new_width = max(1, int(template.shape[1] * scale))
    new_height = max(1, int(template.shape[0] * scale))

    return cv2.resize(template, (new_width, new_height))


def match_template(frame: np.ndarray, template: np.ndarray) -> tuple[float, tuple[int, int]]:
    frame = to_gray(frame)

    frame_height, frame_width = frame.shape[:2]
    template_height, template_width = template.shape[:2]

    if template_height > frame_height or template_width > frame_width:
        scale = min(frame_height / template_height, frame_width / template_width) * 0.95
        template = cv2.resize(
            template,
            (max(1, int(template_width * scale)), max(1, int(template_height * scale))),
        )

    result = cv2.matchTemplate(frame, template, cv2.TM_CCOEFF_NORMED)
    _, max_value, _, max_location = cv2.minMaxLoc(result)

    return float(max_value), (int(max_location[0]), int(max_location[1]))
