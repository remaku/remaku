import cv2
import numpy as np
from loguru import logger

from remaku.models.macro_model import DEFAULT_TEMPLATE_MATCH_MODE
from remaku.paths import template_path


def load_templates(template_ids: list[str], macro_id: str = "") -> dict[str, np.ndarray]:
    out: dict[str, np.ndarray] = {}

    for template_id in template_ids:
        path = template_path(macro_id, template_id)

        if not path.exists():
            logger.warning("vision: template file not found: {}", template_id)
            continue

        image = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_UNCHANGED)

        if image is None:
            logger.warning("vision: failed to read template: {}", path)
            continue

        out[template_id] = image

    return out


def to_gray(frame: np.ndarray) -> np.ndarray:
    if frame.ndim == 2:
        return frame

    return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)


def to_bgr(frame: np.ndarray) -> np.ndarray:
    if frame.ndim == 3 and frame.shape[2] == 3:
        return frame

    if frame.ndim == 3 and frame.shape[2] == 4:
        return cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

    return cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)


def prepare_match_inputs(
    frame: np.ndarray,
    template: np.ndarray,
    match_mode: str = DEFAULT_TEMPLATE_MATCH_MODE,
) -> tuple[np.ndarray, np.ndarray]:
    if match_mode == "color" and frame.ndim == 3 and template.ndim == 3:
        return to_bgr(frame), to_bgr(template)

    return to_gray(frame), to_gray(template)


def scale_template(template: np.ndarray, frame_shape: tuple[int, ...], capture_size: tuple[int, int]) -> np.ndarray:
    frame_height, frame_width = frame_shape[:2]
    capture_width, capture_height = capture_size

    if frame_width == capture_width and frame_height == capture_height:
        return template

    scale = min(frame_width / capture_width, frame_height / capture_height)
    new_width = max(1, int(template.shape[1] * scale))
    new_height = max(1, int(template.shape[0] * scale))

    return cv2.resize(template, (new_width, new_height))


def match_template(
    frame: np.ndarray,
    template: np.ndarray,
    match_mode: str = DEFAULT_TEMPLATE_MATCH_MODE,
) -> tuple[float, tuple[int, int]]:
    frame, template = prepare_match_inputs(frame, template, match_mode)

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
