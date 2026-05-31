"""StepRunner execution engine.

Provides the base runner class implementation, managing threads, pause, and stop states.
"""

import threading
import time
from dataclasses import dataclass
from enum import StrEnum

import numpy as np
from loguru import logger

import capture
import keys
import vision
import window
from i18n import t


class Stopped(Exception):
    """Raised when user presses stop, to immediately end the flow."""


class StopReason(StrEnum):
    USER = "user_stopped"
    DONE = "done"
    STALE = "ui_unrecognized"
    STUCK = "screen_stuck"
    NO_WINDOW = "window_not_found"
    NO_START_SCREEN = "wrong_start_screen"
    ERROR = "error"


@dataclass
class Status:
    running: bool = False
    state: str = "-"
    score: float = 0.0
    match_name: str = ""
    progress: int = 0
    repeat_total: int = 0
    last_reason: str = ""
    message: str = ""
    elapsed_s: float = 0.0


class StepRunner:
    """Common base class for all step runners.

    Subclasses must override `loop()`, accessing the execution environment
    via `self.win`, `self.rect`, `self.templates`, and `self.grabber`.

    If steps require templates, set `self.template_names` in `__init__`.
    """

    name: str = "step"
    label: str = "Step"
    target_window: str = ""

    def __init__(self, conf) -> None:
        self.conf = conf
        self.template_names: list[str] = []
        self.stop_evt = threading.Event()
        self.thread: threading.Thread | None = None
        self.status = Status()
        self.lock = threading.Lock()
        self.start_time: float | None = None

    def start(self) -> None:
        if self.thread and self.thread.is_alive():
            return

        self.stop_evt.clear()
        self.start_time = time.monotonic()

        with self.lock:
            self.status = Status(running=True)

        self.thread = threading.Thread(target=self.run_safe, name=f"step-{self.name}", daemon=True)

        self.thread.start()

    def stop(self) -> None:
        self.stop_evt.set()

    def is_running(self) -> bool:
        return bool(self.thread and self.thread.is_alive())

    def get_status(self) -> Status:
        with self.lock:
            status = Status(**self.status.__dict__)
        if status.running and self.start_time is not None:
            status.elapsed_s = time.monotonic() - self.start_time
        return status

    def run(self) -> None:
        conf = self.conf
        target_title = self.target_window or conf.general.target_window

        if target_title:
            win = window.find_target_window(target_title)

            while win is None:
                self.update(state=t("status.waiting_window"))

                if self.stop_evt.wait(1):
                    raise Stopped

                win = window.find_target_window(target_title)
        else:
            win = window.find_target_window()

            if win is None:
                self.finish(StopReason.NO_WINDOW, t("error.window_not_found_foreground"))
                return

        if window.check_elevation_mismatch(win):
            self.finish(
                StopReason.ERROR,
                t("error.elevation_mismatch"),
            )
            return

        rect = window.client_rect(win)
        logger.info("Target window found: {}x{}", rect.width, rect.height)

        if self.template_names:
            templates = vision.load_templates(self.template_names, self.name)

            if len(templates) != len(self.template_names):
                missing = set(self.template_names) - set(templates)
                self.finish(StopReason.STALE, t("error.missing_templates", names=", ".join(sorted(missing))))
                return
        else:
            templates = {}

        grabber = capture.make_grabber()

        self.win = win
        self.rect = rect
        self.templates = templates
        self.template_capture_sizes: dict[str, tuple[int, int] | None] = {
            name: vision.get_template_capture_size(name, self.name) for name in templates
        }
        self.grabber = grabber

        try:
            self.loop()
        finally:
            grabber.close()

    def loop(self) -> None:
        raise NotImplementedError

    def run_safe(self) -> None:
        try:
            self.run()
        except Stopped:
            self.finish_user_stopped()
        except Exception as e:
            logger.exception("{} unexpected error", self.name)
            self.finish(StopReason.ERROR, f"Error: {e}")

    def update(self, **fields) -> None:
        with self.lock:
            for k, v in fields.items():
                setattr(self.status, k, v)

    def finish(self, reason: StopReason, message: str) -> None:
        logger.info("{} finished: {} ({})", self.name, reason.value, message)

        with self.lock:
            self.status.running = False
            self.status.last_reason = reason.value
            self.status.message = message
            if self.start_time is not None:
                self.status.elapsed_s = time.monotonic() - self.start_time

    def finish_user_stopped(self) -> None:
        self.finish(StopReason.USER, t("error.user_stopped"))

    def tap(self, key: str, hold_ms: int = 90) -> None:
        conf = self.conf
        keys.tap(
            key,
            hold_ms=hold_ms,
            jitter_ms=conf.input.jitter_ms,
        )

    def sleep(self, ms: float) -> None:
        if self.stop_evt.wait(ms / 1000):
            raise Stopped

    def sleep_remaining(self, tick_start: float, period: float) -> None:
        elapsed = time.monotonic() - tick_start
        if elapsed < period and self.stop_evt.wait(period - elapsed):
            raise Stopped

    def foreground_tick(self) -> None:
        if not window.is_foreground(self.win):
            self.update(state=t("status.waiting_foreground"))

        while not window.is_foreground(self.win):
            self.sleep(250)

        self.update(state="running")

    def capture_tick(self):
        """Capture one frame, handling foreground check. Returns grayscale frame or None (should continue)."""
        if not window.is_foreground(self.win):
            self.update(state=t("status.waiting_foreground"))
            self.sleep(250)
            return None

        if self.status.state != "running":
            self.update(state="running")

        frame = self.grabber.grab(self.rect)
        if frame is None:
            return None

        return vision.to_gray(frame)

    def scale_tpl(self, name: str, template: np.ndarray, frame: np.ndarray) -> np.ndarray:
        """Scale a template if it was captured at a different resolution than the current frame."""
        cap_size = self.template_capture_sizes.get(name)

        if cap_size is None:
            return template

        return vision.scale_template(template, frame.shape, cap_size)

    def wait_for_template(self, name: str, timeout_ms: int, threshold: float | None = None) -> bool:
        """Wait until template appears (score >= threshold). Returns False on timeout, raises Stopped if aborted."""
        conf = self.conf
        period = 1.0 / max(1, conf.capture.fps)
        template = self.templates[name]
        effective_threshold = threshold if threshold is not None else 0.95
        deadline = time.monotonic() + timeout_ms / 1000.0
        scaled_template: np.ndarray | None = None

        while True:
            if self.stop_evt.is_set():
                raise Stopped
            if time.monotonic() >= deadline:
                return False

            tick_start = time.monotonic()
            frame = self.capture_tick()
            if frame is None:
                self.sleep_remaining(tick_start, period)
                continue

            if scaled_template is None:
                scaled_template = self.scale_tpl(name, template, frame)

            score, _ = vision.match_one(frame, scaled_template)
            self.update(score=score, match_name=name)

            if score >= effective_threshold:
                return True

            self.sleep_remaining(tick_start, period)

    def wait_for_any(self, names: list[str], timeout_ms: int) -> str | None:
        """Wait until any template appears, return its name. Returns None on timeout, raises Stopped if aborted."""
        conf = self.conf
        period = 1.0 / max(1, conf.capture.fps)
        template_list = [(name, self.templates[name]) for name in names]
        deadline = time.monotonic() + timeout_ms / 1000.0
        scaled_list: list[tuple[str, np.ndarray]] | None = None

        while True:
            if self.stop_evt.is_set():
                raise Stopped
            if time.monotonic() >= deadline:
                return None

            tick_start = time.monotonic()
            frame = self.capture_tick()
            if frame is None:
                self.sleep_remaining(tick_start, period)
                continue

            if scaled_list is None:
                scaled_list = [(name, self.scale_tpl(name, tpl, frame)) for name, tpl in template_list]

            best_name, best_score = names[0], -1.0
            for name, template in scaled_list:
                score, _ = vision.match_one(frame, template)
                if score > best_score:
                    best_score = score
                    best_name = name

            self.update(score=best_score, match_name=best_name)

            if best_score >= 0.95:
                return best_name

            self.sleep_remaining(tick_start, period)
