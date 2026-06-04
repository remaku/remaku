"""Image recognition module.

Provides OpenCV-based template matching for finding specific images on screen.
"""

import cv2
import numpy as np
from loguru import logger

import config


def load_templates(names: list[str], macro_name: str = "") -> dict[str, np.ndarray]:
    """Load template images by name from the user templates directory."""
    templates_dir = config.templates_dir(macro_name)
    out: dict[str, np.ndarray] = {}

    for name in names:
        path = templates_dir / f"{name}.png"

        if not path.exists():
            logger.warning("vision: template file not found: {}", name)
            continue

        img = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_GRAYSCALE)

        if img is None:
            logger.warning("vision: failed to read template: {}", path)
            continue

        out[name] = img

    return out


def to_gray(frame: np.ndarray) -> np.ndarray:
    if frame.ndim == 2:
        return frame

    return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)


def scale_template(template: np.ndarray, frame_shape: tuple[int, ...], capture_size: tuple[int, int]) -> np.ndarray:
    """Scale template if the current frame size differs from the capture-time size."""
    frame_h, frame_w = frame_shape[:2]
    cap_w, cap_h = capture_size

    if frame_w == cap_w and frame_h == cap_h:
        return template

    scale = min(frame_w / cap_w, frame_h / cap_h)
    new_w = max(1, int(template.shape[1] * scale))
    new_h = max(1, int(template.shape[0] * scale))

    return cv2.resize(template, (new_w, new_h))


def match_one(frame: np.ndarray, template: np.ndarray) -> tuple[float, tuple[int, int]]:
    frame = to_gray(frame)

    frame_height, frame_width = frame.shape[:2]
    template_height, template_width = template.shape[:2]

    if template_height > frame_height or template_width > frame_width:
        scale = min(frame_height / template_height, frame_width / template_width) * 0.95
        template = cv2.resize(
            template,
            (max(1, int(template_width * scale)), max(1, int(template_height * scale))),
        )

    res = cv2.matchTemplate(frame, template, cv2.TM_CCOEFF_NORMED)

    _, max_val, _, max_loc = cv2.minMaxLoc(res)

    return float(max_val), (int(max_loc[0]), int(max_loc[1]))
