import time
from pathlib import Path

import numpy as np
from loguru import logger

from remaku.core import keys, vision, window
from remaku.models.config_model import config_model
from remaku.models.macro_model import (
    Macro,
    get_step_count,
    get_step_find_timeout,
    get_step_gone_grace,
    get_step_hard_timeout,
    get_step_hold_ms,
    get_step_interval_ms,
    get_step_key,
    get_step_load_delay,
    get_step_ms,
    get_step_on_timeout,
    get_step_rows,
    get_step_start,
    get_step_template,
    get_step_templates,
    get_step_text,
    get_step_threshold,
    get_step_timeout,
)
from remaku.services.engine import Engine, Stopped, StopReason

REQUIRED_FIELDS: dict[str, list[tuple[str, type | tuple[type, ...]]]] = {
    "key": [("key", str)],
    "delay": [("ms", (int, float))],
    "wait_image": [("template", str)],
    "if_image": [("template", str)],
    "if_any_image": [("templates", list)],
    "hold_key_until_gone": [("key", str), ("template", str)],
    "text_input": [("text", str)],
    "repeat": [],
    "grid_nav": [],
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
        self.template_ids = list(macro.templates.keys())
        self.macro = macro.to_dict()
        self.current_step_path: tuple[tuple[str, int], ...] | None = None
        self.grid_counters: dict[int, int] = {}
        self.repeat_depth: int = 0

    def template_label(self, template_id: str) -> str:
        return self.macro.get("templates", {}).get(template_id, {}).get("label", template_id)

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
            if self.stop_event.is_set():
                raise Stopped
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
        logger.info("{}: {} {}", self.engine_id, action, details)

        if action == "key":
            self.tap(get_step_key(step), hold_ms=get_step_hold_ms(step))

        elif action == "delay":
            self.sleep(get_step_ms(step))

        elif action == "text_input":
            keys.type_text(get_step_text(step), get_step_interval_ms(step))

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

        elif action == "if_image":
            timeout = get_step_timeout(step)
            template_id = get_step_template(step)
            threshold = get_step_threshold(step)

            found = self.wait_for_template(template_id, timeout, threshold=threshold)

            if found:
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

        else:
            logger.warning("macro: unknown action type '{}'", action)

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

        drive_start = time.monotonic()
        last_seen_at: float | None = None

        logger.info(
            "{}: holding {}, waiting for {} to disappear", self.engine_id, key, self.template_label(template_id)
        )

        with keys.held(key):
            while True:
                if self.stop_event.is_set():
                    raise Stopped

                if not self.status.running:
                    return

                tick_start = time.monotonic()

                if not window.is_foreground(self.found_window):
                    logger.warning("{}: window lost foreground, releasing {}", self.engine_id, key)
                    return

                frame = self.grabber.grab(self.capture_rect)
                if frame is None:
                    self.sleep(period * 1000)
                    continue

                frame = vision.to_gray(frame)

                if scaled_template is None:
                    capture_size = self.template_capture_sizes.get(template_id)
                    if capture_size is not None:
                        scaled_template = vision.scale_template(template, frame.shape, capture_size)
                    else:
                        scaled_template = template

                score, _ = vision.match_template(frame, scaled_template)
                self.update(score=score, match_id=template_id)

                now = time.monotonic()
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

                self.sleep_remaining(tick_start, period)
