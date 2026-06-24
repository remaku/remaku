import time
from contextlib import AbstractContextManager
from pathlib import Path

import numpy as np
from loguru import logger

from remaku.core import keys, ocr, vision, window
from remaku.models.config_model import config_model
from remaku.models.macro_model import (
    DEFAULT_TEMPLATE_MATCH_MODE,
    NUMBER_OPERATORS,
    Macro,
    get_step_button,
    get_step_count,
    get_step_find_timeout,
    get_step_gone_grace,
    get_step_hard_timeout,
    get_step_hold_ms,
    get_step_interval_ms,
    get_step_key,
    get_step_load_delay,
    get_step_mouse_relative,
    get_step_mouse_target,
    get_step_mouse_x,
    get_step_mouse_y,
    get_step_ms,
    get_step_number_capture_height,
    get_step_number_capture_width,
    get_step_number_check_first,
    get_step_number_height,
    get_step_number_operator,
    get_step_number_relative,
    get_step_number_stable_reads,
    get_step_number_value,
    get_step_number_width,
    get_step_number_x,
    get_step_number_y,
    get_step_on_timeout,
    get_step_rows,
    get_step_scroll_clicks,
    get_step_start,
    get_step_template,
    get_step_templates,
    get_step_text,
    get_step_threshold,
    get_step_timeout,
)
from remaku.services.engine import Engine, StopReason

REQUIRED_FIELDS: dict[str, list[tuple[str, type | tuple[type, ...]]]] = {
    "key": [("key", str)],
    "delay": [("ms", (int, float))],
    "wait_image": [("template", str)],
    "if_image": [("template", str)],
    "if_any_image": [("templates", list)],
    "hold_key_until_gone": [("key", str), ("template", str)],
    "text_input": [("text", str)],
    "wait_number": [("width", (int, float)), ("height", (int, float)), ("operator", str), ("value", (int, float))],
    "if_number": [("width", (int, float)), ("height", (int, float)), ("operator", str), ("value", (int, float))],
    "repeat_until_number": [
        ("width", (int, float)),
        ("height", (int, float)),
        ("operator", str),
        ("value", (int, float)),
    ],
    "repeat": [],
    "grid_nav": [],
    "mouse_click": [("button", str)],
    "mouse_move": [],
    "mouse_scroll": [("clicks", (int, float))],
}


def validate_steps(steps: list[dict], template_root: Path | None = None, offset: int = 0) -> list[str]:
    errors = []

    for index, step in enumerate(steps, start=offset + 1):
        step_type = step.get("type")

        if not step_type:
            errors.append(f"Step {index}: missing type")
            continue

        if step_type not in REQUIRED_FIELDS:
            errors.append(f"Step {index}: unknown type '{step_type}'")
            continue

        for field, expected in REQUIRED_FIELDS[step_type]:
            value = step.get(field)

            if value is None:
                errors.append(f"Step {index} ({step_type}): missing field '{field}'")
            elif not isinstance(value, expected):
                errors.append(f"Step {index} ({step_type}): bad format for '{field}'")
            elif field == "key" and not keys.is_valid_key(value):
                errors.append(f"Step {index} ({step_type}): invalid key '{value}'")
            elif field == "template" and not value:
                errors.append(f"Step {index} ({step_type}): empty template")
            elif field == "template" and template_root is not None and not (template_root / f"{value}.png").exists():
                errors.append(f"Step {index} ({step_type}): template '{value}' not found on disk")
            elif field == "templates" and not value:
                errors.append(f"Step {index} ({step_type}): empty templates")
            elif field == "templates" and template_root is not None:
                for template_id in value:
                    if not (template_root / f"{template_id}.png").exists():
                        errors.append(f"Step {index} ({step_type}): template '{template_id}' not found on disk")

        if step_type == "text_input" and "interval_ms" in step:
            interval_ms = step.get("interval_ms")

            if not isinstance(interval_ms, int | float):
                errors.append(f"Step {index} ({step_type}): bad format for 'interval_ms'")

        if step_type in ("wait_number", "if_number", "repeat_until_number"):
            operator = step.get("operator")
            if operator not in NUMBER_OPERATORS:
                errors.append(f"Step {index} ({step_type}): invalid operator '{operator}'")

            for field in ("width", "height"):
                value = step.get(field)
                if isinstance(value, int | float) and value <= 0:
                    errors.append(f"Step {index} ({step_type}): '{field}' must be greater than 0")

            stable_reads = step.get("stable_reads")
            if stable_reads is not None and not isinstance(stable_reads, int | float):
                errors.append(f"Step {index} ({step_type}): bad format for 'stable_reads'")
            elif isinstance(stable_reads, int | float) and stable_reads <= 0:
                errors.append(f"Step {index} ({step_type}): 'stable_reads' must be greater than 0")

        if step_type in ("mouse_click", "mouse_move") and step.get("target") == "template":
            template_value = step.get("template")

            if not template_value:
                errors.append(f"Step {index} ({step_type}): empty template for template target")
            elif template_root is not None and not (template_root / f"{template_value}.png").exists():
                errors.append(f"Step {index} ({step_type}): template '{template_value}' not found on disk")

        for key in ("steps", "then", "else"):
            if sub := step.get(key):
                errors.extend(validate_steps(sub, template_root=template_root, offset=index))

    return errors


class MacroRunner(Engine):
    def __init__(self, macro: Macro, macro_path: Path | None = None) -> None:
        super().__init__()

        self.macro_path = macro_path

        self.macro_id = macro.meta.id or "macro"
        self.engine_id = self.macro_id
        self.label = macro.meta.label or "Macro"
        self.target_window = macro.meta.target_window or ""
        self.background_input = macro.background_input
        self.keep_target_focused = macro.keep_target_focused
        self.template_ids = list(macro.templates.keys())
        self.macro = macro.to_dict()
        self.current_step_path: tuple[tuple[str, int], ...] | None = None
        self.grid_counters: dict[int, int] = {}
        self.repeat_depth: int = 0

    def template_label(self, template_id: str) -> str:
        return self.macro.get("templates", {}).get(template_id, {}).get("label", template_id)

    def template_match_mode(self, template_id: str) -> str:
        return self.macro.get("templates", {}).get(template_id, {}).get("match_mode", DEFAULT_TEMPLATE_MATCH_MODE)

    def loop(self) -> None:
        from remaku.paths import templates_dir

        self.repeat_depth = 0
        self.grid_counters = {}
        steps = self.macro.get("steps", [])

        errors = validate_steps(steps, template_root=templates_dir(self.macro_id))
        if errors:
            self.finish(StopReason.STALE, f"macro_format: {';'.join(errors)}")
            return

        self.current_step: dict | None = None
        self.current_step_path = None
        self.update(state="running")
        self.exec_steps(steps)
        self.current_step = None
        self.current_step_path = None
        if self.status.running:
            self.finish(StopReason.DONE, "done")

    def build_template_capture_sizes(self) -> dict[str, tuple[int, int] | None]:
        if not self.macro.get("gaming_mode", True):
            return {}

        screen_width, screen_height = window.screen_resolution()
        templates_meta = self.macro.get("templates", {})
        result: dict[str, tuple[int, int] | None] = {}

        for template_id in self.templates:
            info = templates_meta.get(template_id, {})
            width = info.get("capture_width") or screen_width
            height = info.get("capture_height") or screen_height
            result[template_id] = (width, height)

        return result

    def exec_steps(
        self,
        steps: list[dict],
        parent_path: tuple[tuple[str, int], ...] = (),
        branch_key: str = "steps",
    ) -> None:
        for index, step in enumerate(steps):
            self.checkpoint()

            if not self.status.running:
                return

            step_path = (*parent_path, (branch_key, index))

            if step.get("type") not in ("repeat",):
                self.current_step = step
                self.current_step_path = step_path

            self.exec_step(step, step_path)

    def exec_step(self, step: dict, step_path: tuple[tuple[str, int], ...]) -> None:
        if step.get("skip"):
            return

        self.checkpoint()
        action = step["type"]

        details = ""

        if action == "key":
            details = get_step_key(step)
        elif action == "delay":
            details = f"{get_step_ms(step)}ms"
        elif action in ("wait_image", "if_image"):
            details = self.template_label(get_step_template(step))
        elif action == "if_any_image":
            details = str([self.template_label(template) for template in get_step_templates(step)])
        elif action == "grid_nav":
            counter = self.grid_counters.get(id(step), 0)
            details = f"pos={counter + get_step_start(step)}"
        elif action == "text_input":
            details = f"{len(get_step_text(step))} chars"
        elif action in ("wait_number", "if_number", "repeat_until_number"):
            details = self.number_condition_label(step)
        elif action == "mouse_click":
            details = get_step_button(step)
        elif action == "mouse_scroll":
            details = f"{get_step_scroll_clicks(step)} clicks"
        logger.info("{}: {} {}", self.engine_id, action, details)

        if action == "key":
            self.tap(get_step_key(step), hold_ms=get_step_hold_ms(step))
            self.checkpoint()

        elif action == "delay":
            self.sleep(get_step_ms(step))

        elif action == "text_input":
            self.checkpoint()
            keys.type_text(get_step_text(step), get_step_interval_ms(step), hwnd=self.input_hwnd())
            self.checkpoint()

        elif action == "wait_number":
            if not self.wait_for_number_condition(step):
                self.finish(StopReason.STALE, f"number_timeout: {self.number_condition_label(step)}")

                return

        elif action == "wait_image":
            timeout = get_step_timeout(step)
            template_id = get_step_template(step)
            threshold = get_step_threshold(step)

            if not self.wait_for_template(template_id, timeout, threshold):
                on_timeout = get_step_on_timeout(step)

                if on_timeout == "stop":
                    self.finish(StopReason.STALE, f"wait_timeout: {self.template_label(template_id)}")

                return

        elif action == "repeat":
            count = get_step_count(step)
            sub_steps = step.get("steps", [])

            for i in range(count):
                if self.repeat_depth == 0:
                    self.update(progress=i + 1, repeat_total=count)

                logger.info("{}: repeat {}/{}", self.engine_id, i + 1, count)

                self.repeat_depth += 1
                self.exec_steps(sub_steps, step_path, "steps")
                self.repeat_depth -= 1

                if not self.status.running:
                    return

        elif action == "repeat_until_number":
            self.do_repeat_until_number(step, step_path)

        elif action == "if_image":
            timeout = get_step_timeout(step)
            template_id = get_step_template(step)
            threshold = get_step_threshold(step)

            found = self.wait_for_template(template_id, timeout, threshold=threshold)

            if found:
                self.exec_steps(step.get("then", []), step_path, "then")
            else:
                self.exec_steps(step.get("else", []), step_path, "else")

        elif action == "if_number":
            if self.wait_for_number_condition(step):
                self.exec_steps(step.get("then", []), step_path, "then")
            else:
                self.exec_steps(step.get("else", []), step_path, "else")

        elif action == "if_any_image":
            timeout = get_step_timeout(step)
            template_ids = get_step_templates(step)

            matched_template_id = self.wait_for_any(template_ids, timeout, threshold=get_step_threshold(step))

            branches = step.get("branches", {})

            if matched_template_id is None:
                on_timeout = get_step_on_timeout(step)

                if on_timeout == "stop":
                    labels = [self.template_label(template_id) for template_id in template_ids]
                    self.finish(StopReason.STALE, f"wait_any_timeout: {labels}")

                return

            if matched_template_id in branches:
                self.exec_steps(branches[matched_template_id], step_path, matched_template_id)

        elif action == "grid_nav":
            rows = get_step_rows(step)
            step_id = id(step)
            counter = self.grid_counters.get(step_id, 0)
            position = counter + get_step_start(step)

            self.grid_counters[step_id] = counter + 1

            if (position + 1) % rows == 0:
                self.exec_steps(step.get("on_next_col", []), step_path, "on_next_col")
            else:
                self.exec_steps(step.get("on_next_row", []), step_path, "on_next_row")

        elif action == "hold_key_until_gone":
            self.do_hold_key_until_gone(step)

        elif action == "mouse_click":
            button = get_step_button(step)
            target = get_step_mouse_target(step)

            if target == "template":
                template_id = get_step_template(step)

                if not template_id:
                    logger.warning("{}: mouse_click template is empty", self.engine_id)
                    on_timeout = get_step_on_timeout(step)

                    if on_timeout == "stop":
                        self.finish(StopReason.STALE, "mouse_click: empty template")

                    return

                timeout = get_step_timeout(step)
                threshold = get_step_threshold(step)
                found, center_x, center_y = self.wait_for_template_position(template_id, timeout, threshold)

                if not found:
                    on_timeout = get_step_on_timeout(step)

                    if on_timeout == "stop":
                        self.finish(StopReason.STALE, f"mouse_click_timeout: {self.template_label(template_id)}")

                    return

                keys.mouse_click(button, center_x, center_y, hwnd=self.input_hwnd())
            else:
                position = self.resolve_mouse_position(step)

                if position is None:
                    logger.warning("{}: mouse_click could not resolve position", self.engine_id)
                    return

                keys.mouse_click(button, *position, hwnd=self.input_hwnd())

        elif action == "mouse_move":
            target = get_step_mouse_target(step)

            if target == "template":
                template_id = get_step_template(step)

                if not template_id:
                    logger.warning("{}: mouse_move template is empty", self.engine_id)
                    on_timeout = get_step_on_timeout(step)

                    if on_timeout == "stop":
                        self.finish(StopReason.STALE, "mouse_move: empty template")

                    return

                timeout = get_step_timeout(step)
                threshold = get_step_threshold(step)
                found, center_x, center_y = self.wait_for_template_position(template_id, timeout, threshold)

                if not found:
                    on_timeout = get_step_on_timeout(step)

                    if on_timeout == "stop":
                        self.finish(StopReason.STALE, f"mouse_move_timeout: {self.template_label(template_id)}")

                    return

                keys.mouse_move(center_x, center_y, hwnd=self.input_hwnd())
            else:
                position = self.resolve_mouse_position(step)

                if position is None:
                    logger.warning("{}: mouse_move could not resolve position", self.engine_id)
                    return

                keys.mouse_move(*position, hwnd=self.input_hwnd())

        elif action == "mouse_scroll":
            self.checkpoint()
            keys.mouse_scroll(get_step_scroll_clicks(step), get_step_interval_ms(step), hwnd=self.input_hwnd())
            self.checkpoint()

        else:
            logger.warning("macro: unknown action type '{}'", action)

    def do_repeat_until_number(self, step: dict, step_path: tuple[tuple[str, int], ...]) -> None:
        if get_step_number_check_first(step) and self.wait_for_number_condition(step):
            return

        count = get_step_count(step)
        sub_steps = step.get("steps", [])

        for i in range(count):
            if self.repeat_depth == 0:
                self.update(progress=i + 1, repeat_total=count)

            logger.info("{}: repeat_until_number {}/{}", self.engine_id, i + 1, count)

            self.repeat_depth += 1
            self.exec_steps(sub_steps, step_path, "steps")
            self.repeat_depth -= 1

            if not self.status.running:
                return

            if self.wait_for_number_condition(step):
                return

        if self.status.running:
            self.finish(StopReason.STALE, f"number_condition_timeout: {self.number_condition_label(step)}")

    def number_condition_label(self, step: dict) -> str:
        return f"{get_step_number_operator(step)} {get_step_number_value(step)}"

    def wait_for_number_condition(self, step: dict) -> bool:
        timeout_ms = get_step_timeout(step)
        deadline = self.active_monotonic() + timeout_ms / 1000.0
        period = 1.0 / max(1, config_model.config.capture.fps)
        required_stable_reads = max(1, get_step_number_stable_reads(step))
        last_value: int | None = None
        stable_reads = 0

        while True:
            self.checkpoint()
            if self.active_monotonic() >= deadline:
                return False

            tick_start = time.monotonic()
            frame = self.capture_tick()
            if frame is None:
                self.sleep_remaining(tick_start, period)
                continue

            try:
                value = self.read_number_from_step(frame, step)
            except ocr.OcrUnavailableError:
                self.finish(StopReason.ERROR, "ocr_unavailable")
                return False

            if value is None:
                logger.info("{}: number OCR unreadable for {}", self.engine_id, self.number_condition_label(step))
                last_value = None
                stable_reads = 0
                self.sleep_remaining(tick_start, period)
                continue

            if value == last_value:
                stable_reads += 1
            else:
                last_value = value
                stable_reads = 1

            self.update(message=str(value))
            logger.info(
                "{}: number OCR read {} for {} ({}/{})",
                self.engine_id,
                value,
                self.number_condition_label(step),
                stable_reads,
                required_stable_reads,
            )

            if stable_reads >= required_stable_reads and ocr.compare_number(
                value,
                get_step_number_operator(step),
                get_step_number_value(step),
            ):
                logger.info("{}: number condition met with {}", self.engine_id, value)
                return True

            self.sleep_remaining(tick_start, period)

    def read_number_from_step(self, frame: np.ndarray, step: dict) -> int | None:
        region = ocr.NumberRegion(
            x=get_step_number_x(step),
            y=get_step_number_y(step),
            width=get_step_number_width(step),
            height=get_step_number_height(step),
            relative=get_step_number_relative(step),
            capture_width=get_step_number_capture_width(step),
            capture_height=get_step_number_capture_height(step),
        )
        return ocr.read_number(frame, region, origin_left=self.capture_rect.left, origin_top=self.capture_rect.top)

    def do_hold_key_until_gone(self, step: dict) -> None:
        key = get_step_key(step)
        template_id = get_step_template(step)
        load_delay_ms = get_step_load_delay(step)
        find_timeout_ms = get_step_find_timeout(step)
        gone_grace_ms = get_step_gone_grace(step)
        hard_timeout_ms = get_step_hard_timeout(step)

        period = 1.0 / max(1, config_model.config.capture.fps)
        template = self.templates[template_id]
        threshold = get_step_threshold(step)
        scaled_template: np.ndarray | None = None

        self.sleep(load_delay_ms)

        drive_start = self.active_monotonic()
        last_seen_at: float | None = None

        logger.info(
            "{}: holding {}, waiting for {} to disappear", self.engine_id, key, self.template_label(template_id)
        )

        held_context: AbstractContextManager | None = None

        def press_key() -> None:
            nonlocal held_context

            if held_context is not None:
                return

            held_context = keys.held(key, hwnd=self.input_hwnd())
            held_context.__enter__()

        def release_key() -> None:
            nonlocal held_context

            if held_context is None:
                return

            held_context.__exit__(None, None, None)
            held_context = None

        press_key()

        try:
            while True:
                self.checkpoint(release_key, press_key)

                if not self.status.running:
                    return

                tick_start = time.monotonic()

                frame = self.capture_tick()
                if frame is None:
                    self.sleep(period * 1000, release_key, press_key)
                    continue

                if scaled_template is None:
                    capture_size = self.template_capture_sizes.get(template_id)
                    if capture_size is not None:
                        scaled_template = vision.scale_template(template, frame.shape, capture_size)
                    else:
                        scaled_template = template

                score, _ = vision.match_template(frame, scaled_template, self.template_match_mode(template_id))
                self.update(score=score, match_id=template_id)

                now = self.active_monotonic()
                elapsed_ms = (now - drive_start) * 1000

                if score >= threshold:
                    last_seen_at = now
                else:
                    if last_seen_at is None:
                        if elapsed_ms >= find_timeout_ms:
                            logger.warning(
                                "{}: waited {} ms but never saw {}, releasing {}",
                                self.engine_id,
                                int(elapsed_ms),
                                self.template_label(template_id),
                                key,
                            )
                            return
                    else:
                        gone_ms = (now - last_seen_at) * 1000
                        if gone_ms >= gone_grace_ms:
                            logger.info(
                                "{}: {} gone for {} ms, releasing {}",
                                self.engine_id,
                                self.template_label(template_id),
                                int(gone_ms),
                                key,
                            )
                            return

                if elapsed_ms >= hard_timeout_ms:
                    logger.warning(
                        "{}: hard timeout {} ms exceeded, releasing {}",
                        self.engine_id,
                        int(elapsed_ms),
                        key,
                    )
                    return

                self.sleep_remaining(tick_start, period, release_key, press_key)
        finally:
            release_key()

    def resolve_mouse_position(self, step: dict) -> tuple[int, int] | None:
        x = get_step_mouse_x(step)
        y = get_step_mouse_y(step)

        if get_step_mouse_relative(step):
            x += self.capture_rect.left
            y += self.capture_rect.top

        return x, y

    def wait_for_template_position(self, template_id: str, timeout_ms: int, threshold: float) -> tuple[bool, int, int]:
        period = 1.0 / max(1, config_model.config.capture.fps)
        template = self.templates[template_id]
        deadline = self.active_monotonic() + timeout_ms / 1000.0
        scaled_template: np.ndarray | None = None

        while True:
            self.checkpoint()
            if self.active_monotonic() >= deadline:
                return False, 0, 0

            tick_start = time.monotonic()
            frame = self.capture_tick()
            if frame is None:
                self.sleep_remaining(tick_start, period)
                continue

            if scaled_template is None:
                scaled_template = self.scale_template(template_id, template, frame)

            score, (match_x, match_y) = vision.match_template(
                frame,
                scaled_template,
                self.template_match_mode(template_id),
            )
            self.update(score=score, match_id=template_id)

            if score >= threshold:
                h, w = scaled_template.shape[:2]
                center_x = self.capture_rect.left + match_x + w // 2
                center_y = self.capture_rect.top + match_y + h // 2
                return True, center_x, center_y

            self.sleep_remaining(tick_start, period)
