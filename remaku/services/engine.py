import threading
import time
from dataclasses import dataclass
from enum import StrEnum

import numpy as np
from loguru import logger

from remaku.core import capture, keys, vision, window
from remaku.core.event_bus import event_bus
from remaku.models.config_model import config_model


class Stopped(Exception):
    pass


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


class Engine:
    name: str = "step"
    label: str = "Step"
    target_window: str = ""

    def __init__(self) -> None:
        self.template_names: list[str] = []
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.status = Status()
        self.lock = threading.Lock()
        self.start_time: float | None = None

    def start(self) -> None:
        if self.thread and self.thread.is_alive():
            return

        self.stop_event.clear()
        self.start_time = time.monotonic()

        with self.lock:
            self.status = Status(running=True)

        self.thread = threading.Thread(target=self.run_safe, name=f"step-{self.name}", daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()

    def is_running(self) -> bool:
        return bool(self.thread and self.thread.is_alive())

    def get_status(self) -> Status:
        with self.lock:
            status = Status(**self.status.__dict__)
        if status.running and self.start_time is not None:
            status.elapsed_s = time.monotonic() - self.start_time
        return status

    def run(self) -> None:
        if self.target_window:
            found_window = window.find_target_window(self.target_window)

            while found_window is None or not window.is_foreground(found_window):
                waiting_state = "waiting_window" if found_window is None else "waiting_foreground"

                self.update(state=waiting_state)

                if self.stop_event.wait(1):
                    raise Stopped

                found_window = window.find_target_window(self.target_window)
        else:
            found_window = window.find_target_window()

            if found_window is None:
                self.finish(StopReason.NO_WINDOW, "window_not_found")
                return

        if window.check_elevation_mismatch(found_window):
            self.finish(StopReason.ERROR, "elevation_mismatch")
            return

        capture_rect = window.client_rect(found_window)
        logger.info("Target window found: {}x{}", capture_rect.width, capture_rect.height)

        if self.template_names:
            templates = vision.load_templates(self.template_names, self.name)

            if len(templates) != len(self.template_names):
                missing = set(self.template_names) - set(templates)
                self.finish(StopReason.STALE, f"missing_templates: {', '.join(sorted(missing))}")
                return
        else:
            templates = {}

        grabber = capture.make_grabber()

        self.found_window = found_window
        self.capture_rect = capture_rect
        self.templates = templates
        self.grabber = grabber
        self.template_capture_sizes = self.build_template_capture_sizes()

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
        except Exception as error:
            logger.exception("{} unexpected error", self.name)
            self.finish(StopReason.ERROR, f"Error: {error}")

    def update(self, **fields) -> None:
        with self.lock:
            for key, value in fields.items():
                setattr(self.status, key, value)

    def finish(self, reason: StopReason, message: str) -> None:
        logger.info("{} finished: {} ({})", self.name, reason.value, message)

        with self.lock:
            self.status.running = False
            self.status.last_reason = reason.value
            self.status.message = message
            if self.start_time is not None:
                self.status.elapsed_s = time.monotonic() - self.start_time

        event_bus.macro_running_changed.emit(False)

    def finish_user_stopped(self) -> None:
        self.finish(StopReason.USER, "user_stopped")

    def tap(self, key: str, hold_ms: int = 90) -> None:
        keys.tap(
            key,
            hold_ms=hold_ms,
            jitter_ms=config_model.config.input.jitter_ms,
        )

    def sleep(self, ms: float) -> None:
        if self.stop_event.wait(ms / 1000):
            raise Stopped

    def sleep_remaining(self, tick_start: float, period: float) -> None:
        elapsed = time.monotonic() - tick_start
        if elapsed < period and self.stop_event.wait(period - elapsed):
            raise Stopped

    def foreground_tick(self) -> None:
        if not window.is_foreground(self.found_window):
            self.update(state="waiting_foreground")

        while not window.is_foreground(self.found_window):
            self.sleep(250)

        self.update(state="running")

    def capture_tick(self):
        if not window.is_foreground(self.found_window):
            self.update(state="waiting_foreground")
            self.sleep(250)
            return None

        if self.status.state != "running":
            self.update(state="running")

        frame = self.grabber.grab(self.capture_rect)
        if frame is None:
            return None

        return vision.to_gray(frame)

    def scale_template(self, name: str, template: np.ndarray, frame: np.ndarray) -> np.ndarray:
        capture_size = self.template_capture_sizes.get(name)

        if capture_size is None:
            return template

        return vision.scale_template(template, frame.shape, capture_size)

    def wait_for_template(self, name: str, timeout_ms: int, threshold: float) -> bool:
        period = 1.0 / max(1, config_model.config.capture.fps)
        template = self.templates[name]
        deadline = time.monotonic() + timeout_ms / 1000.0
        scaled_template: np.ndarray | None = None

        while True:
            if self.stop_event.is_set():
                raise Stopped
            if time.monotonic() >= deadline:
                return False

            tick_start = time.monotonic()
            frame = self.capture_tick()
            if frame is None:
                self.sleep_remaining(tick_start, period)
                continue

            if scaled_template is None:
                scaled_template = self.scale_template(name, template, frame)

            score, _ = vision.match_template(frame, scaled_template)
            self.update(score=score, match_name=name)

            if score >= threshold:
                return True

            self.sleep_remaining(tick_start, period)

    def wait_for_any(self, names: list[str], timeout_ms: int, threshold: float) -> str | None:
        period = 1.0 / max(1, config_model.config.capture.fps)
        template_list = [(name, self.templates[name]) for name in names]
        deadline = time.monotonic() + timeout_ms / 1000.0
        scaled_list: list[tuple[str, np.ndarray]] | None = None

        while True:
            if self.stop_event.is_set():
                raise Stopped
            if time.monotonic() >= deadline:
                return None

            tick_start = time.monotonic()
            frame = self.capture_tick()
            if frame is None:
                self.sleep_remaining(tick_start, period)
                continue

            if scaled_list is None:
                scaled_list = [(name, self.scale_template(name, template, frame)) for name, template in template_list]

            best_name, best_score = names[0], -1.0
            for name, scaled_template in scaled_list:
                score, _ = vision.match_template(frame, scaled_template)
                if score > best_score:
                    best_score = score
                    best_name = name

            self.update(score=best_score, match_name=best_name)

            if best_score >= threshold:
                return best_name

            self.sleep_remaining(tick_start, period)

    def build_template_capture_sizes(self) -> dict[str, tuple[int, int] | None]:
        width, height = window.screen_resolution()
        return dict.fromkeys(self.templates, (width, height))
