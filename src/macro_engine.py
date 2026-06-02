"""JSON macro engine.

Parses JSON macro scripts and converts them into executable steps.
"""

import copy
import json
import time
from pathlib import Path

import numpy as np
import pydirectinput as pdi
from loguru import logger

import config
import keys
import vision
import window
from i18n import t
from runner import StepRunner, Stopped, StopReason


def load_macro(path: Path) -> dict:
    """Load a JSON macro file."""
    return json.loads(path.read_text(encoding="utf-8"))


REQUIRED_FIELDS: dict[str, list[tuple[str, type | tuple[type, ...]]]] = {
    "key": [("key", str)],
    "delay": [("ms", (int, float))],
    "wait_image": [("template", str)],
    "if_image": [("template", str)],
    "if_any_image": [("templates", list)],
    "hold_key_until_gone": [("key", str), ("template", str)],
    "repeat": [],
    "foreground": [],
    "grid_nav": [],
}


def validate_steps(steps: list[dict], offset: int = 0) -> list[str]:
    """Validate step structure, return a list of error messages."""
    errors = []
    for i, step in enumerate(steps, start=offset + 1):
        stype = step.get("type")
        if not stype:
            errors.append(t("error.validate_missing_type", index=i))
            continue
        if stype not in REQUIRED_FIELDS:
            errors.append(t("error.validate_unknown_type", index=i, type=stype))
            continue
        for field, expected in REQUIRED_FIELDS[stype]:
            val = step.get(field)
            if val is None:
                errors.append(t("error.validate_missing_field", index=i, type=stype, field=field))
            elif not isinstance(val, expected):
                errors.append(t("error.validate_bad_format", index=i, type=stype, field=field))
            elif field == "key" and not pdi.isValidKey(val):
                errors.append(t("error.validate_bad_key", index=i, type=stype, key=val))
        for key in ("steps", "then", "else"):
            if sub := step.get(key):
                errors.extend(validate_steps(sub, offset=i))
    return errors


class MacroRunner(StepRunner):
    """Generic JSON macro executor.

    Usage:
        macro = load_macro(Path("macros/buy_car.json"))
        runner = MacroRunner(conf, macro)
        runner.start(target=50)
    """

    def __init__(self, conf, macro: dict, source_path: Path | None = None) -> None:
        super().__init__(conf)
        self.source_path = source_path
        meta = macro.get("meta", {})
        self.name = meta.get("name", "macro")
        self.label = meta.get("label", "Macro")
        self.target_window = meta.get("target_window", "")
        self.template_names = list(macro.get("templates", {}).keys())
        self.macro = macro
        self.last_snapshot: dict = copy.deepcopy(macro)
        self.undo_stack: list[dict] = []
        self.redo_stack: list[dict] = []
        self.grid_counters: dict[int, int] = {}
        self.repeat_depth: int = 0

    def template_label(self, name: str) -> str:
        """Convert a template ID to the user-configured label name."""
        return self.macro.get("templates", {}).get(name, {}).get("label", name)

    def loop(self) -> None:
        self.repeat_depth = 0
        self.grid_counters = {}
        steps = self.macro.get("steps", [])

        errors = validate_steps(steps)
        if errors:
            self.finish(StopReason.STALE, t("error.macro_format", errors="；".join(errors)))
            return

        missing = self.find_empty_templates(steps)
        if missing:
            self.finish(StopReason.STALE, t("error.missing_template", steps=", ".join(str(i) for i in missing)))
            return

        self.current_step: dict | None = None
        self.update(state="running")
        self.exec_steps(steps)
        self.current_step = None
        # If loop completed without finish(), it ended normally
        if self.status.running:
            self.finish(StopReason.DONE, t("error.done"))

    def find_empty_templates(self, steps: list[dict], offset: int = 0) -> list[int]:
        """Return step numbers (1-based) that are missing templates."""
        result = []
        for i, step in enumerate(steps, start=offset + 1):
            stype = step.get("type", "")
            if stype in ("wait_image", "if_image", "hold_key_until_gone") and not step.get("template"):
                result.append(i)
            for key in ("steps", "then", "else"):
                if sub := step.get(key):
                    result.extend(self.find_empty_templates(sub, offset=i))
        return result

    def exec_steps(self, steps: list[dict]) -> None:
        for step in steps:
            if self.stop_evt.is_set():
                raise Stopped
            if not self.status.running:
                return
            # Only set current_step for non-container steps (avoid flickering)
            if step.get("type") not in ("repeat",):
                self.current_step = step
            self.exec_step(step)

    def exec_step(self, step: dict) -> None:
        if step.get("skip"):
            return

        action = step["type"]

        details = ""
        if action == "key":
            details = step["key"]
        elif action == "delay":
            details = f"{step['ms']}ms"
        elif action == "wait_image" or action == "if_image":
            details = self.template_label(step["template"])
        elif action == "if_any_image":
            details = str([self.template_label(template) for template in step["templates"]])
        elif action == "grid_nav":
            counter = self.grid_counters.get(id(step), 0)
            details = f"pos={counter + step.get('start', 0)}"
        logger.info("{}: {} {}", self.name, action, details)

        if action == "key":
            self.tap(step["key"], hold_ms=step.get("hold_ms", 90))

        elif action == "delay":
            self.sleep(step["ms"])

        elif action == "wait_image":
            timeout = step.get("timeout_ms", 5000)
            template = step["template"]
            threshold = step.get("threshold")
            if not self.wait_for_template(template, timeout, threshold=threshold):
                on_timeout = step.get("on_timeout", "stop")
                if on_timeout == "stop":
                    self.finish(StopReason.STALE, t("error.wait_timeout", template=self.template_label(template)))
                return

        elif action == "foreground":
            self.foreground_tick()

        elif action == "repeat":
            count = int(step.get("count", 1))
            sub_steps = step.get("steps", [])
            for i in range(count):
                if self.repeat_depth == 0:
                    self.update(progress=i + 1, repeat_total=count)
                logger.info("{}: repeat {}/{}", self.name, i + 1, count)
                self.repeat_depth += 1
                self.exec_steps(sub_steps)
                self.repeat_depth -= 1
                if not self.status.running:
                    return

        elif action == "if_image":
            timeout = step.get("timeout_ms", 1000)
            template = step["template"]
            found = self.wait_for_template(template, timeout)
            if found:
                self.exec_steps(step.get("then", []))
            else:
                self.exec_steps(step.get("else", []))

        elif action == "if_any_image":
            timeout = step.get("timeout_ms", 5000)
            templates = step["templates"]
            result = self.wait_for_any(templates, timeout)
            branches = step.get("branches", {})
            if result is None:
                on_timeout = step.get("on_timeout", "stop")
                if on_timeout == "stop":
                    labels = [self.template_label(template) for template in templates]
                    self.finish(StopReason.STALE, t("error.wait_any_timeout", templates=labels))
                return
            if result in branches:
                self.exec_steps(branches[result])

        elif action == "grid_nav":
            rows = step.get("rows", 3)
            step_id = id(step)
            counter = self.grid_counters.get(step_id, 0)
            pos = counter + step.get("start", 0)
            self.grid_counters[step_id] = counter + 1
            if (pos + 1) % rows == 0:
                self.exec_steps(step.get("on_next_col", []))
            else:
                self.exec_steps(step.get("on_next_row", []))

        elif action == "hold_key_until_gone":
            self.do_hold_key_until_gone(step)

        else:
            logger.warning("macro: unknown action type '{}'", action)

    def do_hold_key_until_gone(self, step: dict) -> None:
        """Hold a key down, wait for a template to appear then disappear before releasing.

        Parameters:
          key: the key to hold
          template: the template name to monitor
          load_delay_ms: delay before starting detection (allow screen to load)
          find_timeout_ms: max time to wait for template to first appear
          gone_grace_ms: how long template must be gone to consider it truly disappeared
          hard_timeout_ms: absolute timeout to release regardless
        """
        key = step["key"]
        template_name = step["template"]
        load_delay_ms = step.get("load_delay_ms", 2000)
        find_timeout_ms = step.get("find_timeout_ms", 15000)
        gone_grace_ms = step.get("gone_grace_ms", 1500)
        hard_timeout_ms = step.get("hard_timeout_ms", 180000)

        conf = self.conf
        period = 1.0 / max(1, conf.capture.fps)
        template = self.templates[template_name]
        threshold = config.DEFAULT_THRESHOLD
        scaled_template: np.ndarray | None = None

        self.sleep(load_delay_ms)

        drive_start = time.monotonic()
        last_seen_at: float | None = None

        logger.info("{}: holding {}, waiting for {} to disappear", self.name, key, self.template_label(template_name))

        with keys.held(key):
            while True:
                if self.stop_evt.is_set():
                    raise Stopped

                tick_start = time.monotonic()

                if not window.is_foreground(self.win):
                    logger.warning("{}: window lost foreground, releasing {}", self.name, key)
                    return

                frame = self.grabber.grab(self.rect)
                if frame is None:
                    self.sleep(period * 1000)
                    continue

                frame = vision.to_gray(frame)

                if scaled_template is None:
                    cap_size = self.template_capture_sizes.get(template_name)

                    if cap_size is not None:
                        scaled_template = vision.scale_template(template, frame.shape, cap_size)
                    else:
                        scaled_template = template

                score, _ = vision.match_one(frame, scaled_template)
                self.update(score=score, match_name=template_name)

                now = time.monotonic()
                elapsed_ms = (now - drive_start) * 1000

                if score >= threshold:
                    last_seen_at = now
                else:
                    if last_seen_at is None:
                        if elapsed_ms >= find_timeout_ms:
                            logger.warning(
                                "{}: waited {} ms but never saw {}, releasing {}",
                                self.name,
                                int(elapsed_ms),
                                self.template_label(template_name),
                                key,
                            )
                            return
                    else:
                        gone_ms = (now - last_seen_at) * 1000
                        if gone_ms >= gone_grace_ms:
                            logger.info(
                                "{}: {} gone for {} ms, releasing {}",
                                self.name,
                                self.template_label(template_name),
                                int(gone_ms),
                                key,
                            )
                            return

                if elapsed_ms >= hard_timeout_ms:
                    logger.warning(
                        "{}: hard timeout {} ms exceeded, releasing {}",
                        self.name,
                        int(elapsed_ms),
                        key,
                    )
                    return

                self.sleep_remaining(tick_start, period)
