import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

import numpy as np
from loguru import logger

from remaku.core import capture, keys, vision, window
from remaku.core.event_bus import event_bus
from remaku.models.config_model import config_model
from remaku.models.macro_model import DEFAULT_TEMPLATE_MATCH_MODE

WINDOW_REFRESH_INTERVAL_S = 1.0
FAKE_FOCUS_INTERVAL_S = 1.0


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
    paused: bool = False
    state: str = "-"
    score: float = 0.0
    match_id: str = ""
    progress: int = 0
    repeat_total: int = 0
    last_reason: str = ""
    message: str = ""
    elapsed_s: float = 0.0


class Engine:
    engine_id: str = "step"
    label: str = "Step"
    target_window: str = ""
    background_input: bool = True
    keep_target_focused: bool = False

    def __init__(self) -> None:
        self.template_ids: list[str] = []
        self.stop_event = threading.Event()
        self.resume_event = threading.Event()
        self.control_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.status = Status()
        self.lock = threading.Lock()
        self.start_time: float | None = None
        self.paused_total_s = 0.0
        self.paused_started_at: float | None = None
        self.last_window_refresh_at = 0.0
        self.last_fake_focus_at = 0.0
        self.resume_event.set()

    def start(self) -> None:
        if self.thread and self.thread.is_alive():
            return

        self.stop_event.clear()
        self.resume_event.set()
        self.control_event.clear()
        self.start_time = time.monotonic()
        self.paused_total_s = 0.0
        self.paused_started_at = None

        with self.lock:
            self.status = Status(running=True)

        self.thread = threading.Thread(target=self.run_safe, name=f"step-{self.engine_id}", daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        was_paused = self.clear_paused_state()
        self.control_event.set()

        if was_paused:
            event_bus.macro_paused_changed.emit(False)

    def is_running(self) -> bool:
        return bool(self.thread and self.thread.is_alive())

    def is_paused(self) -> bool:
        with self.lock:
            return self.status.paused

    def pause(self) -> None:
        with self.lock:
            if not self.status.running or self.status.paused:
                return

            self.status.paused = True
            self.status.state = "paused"
            self.paused_started_at = time.monotonic()
            self.resume_event.clear()

        self.control_event.set()
        event_bus.macro_paused_changed.emit(True)

    def resume(self) -> None:
        if not self.clear_paused_state():
            return

        event_bus.macro_paused_changed.emit(False)

    def clear_paused_state(self) -> bool:
        changed = False

        with self.lock:
            if self.status.paused:
                now = time.monotonic()

                if self.paused_started_at is not None:
                    self.paused_total_s += now - self.paused_started_at

                self.paused_started_at = None
                self.status.paused = False

                if self.status.state == "paused":
                    self.status.state = "running"

                changed = True

        self.resume_event.set()
        self.control_event.set()
        return changed

    def active_monotonic(self) -> float:
        now = time.monotonic()

        with self.lock:
            paused_total_s = self.paused_total_s
            paused_started_at = self.paused_started_at

        if paused_started_at is not None:
            paused_total_s += now - paused_started_at

        return now - paused_total_s

    def get_status(self) -> Status:
        with self.lock:
            status = Status(**self.status.__dict__)
        if status.running and self.start_time is not None:
            status.elapsed_s = max(0.0, self.active_monotonic() - self.start_time)
        return status

    def run(self) -> None:
        if self.target_window:
            found_window = window.find_target_window(self.target_window)

            while found_window is None or self.should_wait_for_foreground(found_window):
                waiting_state = "waiting_window" if found_window is None else "waiting_foreground"

                self.update(state=waiting_state)
                self.checkpoint()

                self.sleep(1000)

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

        if self.template_ids:
            templates = vision.load_templates(self.template_ids, self.engine_id)

            if len(templates) != len(self.template_ids):
                missing = set(self.template_ids) - set(templates)
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
        self.last_window_refresh_at = time.monotonic()
        self.keep_target_focus_alive(force=True)

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
            logger.exception("{} unexpected error", self.engine_id)
            self.finish(StopReason.ERROR, f"Error: {error}")

    def update(self, **fields) -> None:
        with self.lock:
            for key, value in fields.items():
                setattr(self.status, key, value)

    def finish(self, reason: StopReason, message: str) -> None:
        logger.info("{} finished: {} ({})", self.engine_id, reason.value, message)

        elapsed_s = 0.0
        if self.start_time is not None:
            elapsed_s = max(0.0, self.active_monotonic() - self.start_time)

        with self.lock:
            self.status.running = False
            self.status.paused = False
            self.status.last_reason = reason.value
            self.status.message = message
            self.status.elapsed_s = elapsed_s
            was_paused = self.paused_started_at is not None
            self.paused_started_at = None

        self.resume_event.set()
        self.control_event.set()
        if was_paused:
            event_bus.macro_paused_changed.emit(False)
        event_bus.macro_running_changed.emit(False)

    def finish_user_stopped(self) -> None:
        self.finish(StopReason.USER, "user_stopped")

    def tap(self, key: str, hold_ms: int = 90) -> None:
        keys.tap(
            key,
            hold_ms=hold_ms,
            jitter_ms=config_model.config.input.jitter_ms,
            hwnd=self.input_hwnd(),
        )

    def target_hwnd(self) -> int | None:
        hwnd = getattr(getattr(self, "found_window", None), "_hWnd", None)
        return hwnd if isinstance(hwnd, int) else None

    def should_wait_for_foreground(self, found_window: object | None = None) -> bool:
        if self.background_input:
            return False

        target = found_window if found_window is not None else getattr(self, "found_window", None)
        return target is not None and not window.is_foreground(target)

    def input_hwnd(self) -> int | None:
        if not self.background_input:
            return None

        self.keep_target_focus_alive(force=True)
        return self.target_hwnd()

    def keep_target_focus_alive(self, force: bool = False) -> None:
        if not self.keep_target_focused:
            return

        found_window = getattr(self, "found_window", None)
        if found_window is None:
            return

        now = time.monotonic()
        if not force and now - self.last_fake_focus_at < FAKE_FOCUS_INTERVAL_S:
            return

        try:
            window.fake_focus(found_window)
            self.last_fake_focus_at = now
        except Exception:
            logger.warning("{}: failed to fake target focus", self.engine_id, exc_info=True)

    def checkpoint(
        self,
        pause_callback: Callable[[], None] | None = None,
        resume_callback: Callable[[], None] | None = None,
    ) -> None:
        if self.stop_event.is_set():
            raise Stopped

        if self.resume_event.is_set():
            return

        if pause_callback is not None:
            pause_callback()

        while not self.resume_event.is_set():
            self.control_event.clear()

            if self.stop_event.is_set():
                raise Stopped

            if self.resume_event.is_set():
                break

            self.control_event.wait()

        if self.stop_event.is_set():
            raise Stopped

        if resume_callback is not None:
            resume_callback()

    def sleep(
        self,
        ms: float,
        pause_callback: Callable[[], None] | None = None,
        resume_callback: Callable[[], None] | None = None,
    ) -> None:
        remaining = max(0.0, ms / 1000)

        while remaining > 0:
            self.control_event.clear()
            self.checkpoint(pause_callback, resume_callback)
            started_at = time.monotonic()

            if not self.control_event.wait(remaining):
                return

            elapsed = time.monotonic() - started_at
            remaining = max(0.0, remaining - elapsed)

            if self.stop_event.is_set():
                raise Stopped

            if not self.resume_event.is_set():
                self.checkpoint(pause_callback, resume_callback)

    def sleep_remaining(
        self,
        tick_start: float,
        period: float,
        pause_callback: Callable[[], None] | None = None,
        resume_callback: Callable[[], None] | None = None,
    ) -> None:
        elapsed = time.monotonic() - tick_start
        if elapsed < period:
            self.sleep((period - elapsed) * 1000, pause_callback, resume_callback)

    def refresh_found_window(self) -> bool:
        if not self.target_window:
            return False

        found = window.find_target_window(self.target_window)
        if found is not None:
            self.found_window = found
            self.capture_rect = window.client_rect(found)
            self.last_window_refresh_at = time.monotonic()
            return True

        return False

    def refresh_found_window_if_due(self) -> bool:
        if not self.target_window:
            return False

        now = time.monotonic()
        if now - self.last_window_refresh_at < WINDOW_REFRESH_INTERVAL_S:
            return False

        return self.refresh_found_window()

    def foreground_tick(self) -> None:
        if self.target_window:
            self.refresh_found_window()

        if self.should_wait_for_foreground():
            self.update(state="waiting_foreground")

        while self.should_wait_for_foreground():
            self.refresh_found_window()
            self.checkpoint()
            self.sleep(250)

        self.keep_target_focus_alive()
        self.update(state="running")

    def capture_tick(self):
        if self.target_window:
            self.refresh_found_window_if_due()

        if self.should_wait_for_foreground():
            self.update(state="waiting_foreground")
            self.sleep(250)
            return None

        self.keep_target_focus_alive()

        if self.status.state != "running":
            self.update(state="running")

        frame = self.grabber.grab(self.capture_rect)
        if frame is None:
            return None

        return frame

    def scale_template(self, template_id: str, template: np.ndarray, frame: np.ndarray) -> np.ndarray:
        capture_size = self.template_capture_sizes.get(template_id)

        if capture_size is None:
            return template

        return vision.scale_template(template, frame.shape, capture_size)

    def template_match_mode(self, template_id: str) -> str:
        return DEFAULT_TEMPLATE_MATCH_MODE

    def wait_for_template(self, template_id: str, timeout_ms: int, threshold: float) -> bool:
        period = 1.0 / max(1, config_model.config.capture.fps)
        template = self.templates[template_id]
        deadline = self.active_monotonic() + timeout_ms / 1000.0
        scaled_template: np.ndarray | None = None

        while True:
            self.checkpoint()
            if self.active_monotonic() >= deadline:
                return False

            tick_start = time.monotonic()
            frame = self.capture_tick()
            if frame is None:
                self.sleep_remaining(tick_start, period)
                continue

            if scaled_template is None:
                scaled_template = self.scale_template(template_id, template, frame)

            score, _ = vision.match_template(frame, scaled_template, self.template_match_mode(template_id))
            self.update(score=score, match_id=template_id)

            if score >= threshold:
                return True

            self.sleep_remaining(tick_start, period)

    def wait_for_any(self, template_ids: list[str], timeout_ms: int, threshold: float) -> str | None:
        period = 1.0 / max(1, config_model.config.capture.fps)
        template_list = [(template_id, self.templates[template_id]) for template_id in template_ids]
        deadline = self.active_monotonic() + timeout_ms / 1000.0
        scaled_list: list[tuple[str, np.ndarray]] | None = None

        while True:
            self.checkpoint()
            if self.active_monotonic() >= deadline:
                return None

            tick_start = time.monotonic()
            frame = self.capture_tick()
            if frame is None:
                self.sleep_remaining(tick_start, period)
                continue

            if scaled_list is None:
                scaled_list = [
                    (template_id, self.scale_template(template_id, template, frame))
                    for template_id, template in template_list
                ]

            best_template_id, best_score = template_ids[0], -1.0
            for template_id, scaled_template in scaled_list:
                score, _ = vision.match_template(frame, scaled_template, self.template_match_mode(template_id))
                if score > best_score:
                    best_score = score
                    best_template_id = template_id

            self.update(score=best_score, match_id=best_template_id)

            if best_score >= threshold:
                return best_template_id

            self.sleep_remaining(tick_start, period)

    def build_template_capture_sizes(self) -> dict[str, tuple[int, int] | None]:
        width, height = window.screen_resolution()
        return dict.fromkeys(self.templates, (width, height))
