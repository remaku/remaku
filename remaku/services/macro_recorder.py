import ctypes
import os
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import win32gui
import win32process
from loguru import logger

from remaku.core.keymap import vk_to_key
from remaku.core.window import Rect

HC_ACTION = 0
WH_KEYBOARD_LL = 13
WH_MOUSE_LL = 14
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
WM_MBUTTONDOWN = 0x0207
WM_MBUTTONUP = 0x0208
WM_MOUSEWHEEL = 0x020A
WM_QUIT = 0x0012
WHEEL_DELTA = 120

DELAY_THRESHOLD_MS = 50
SCROLL_MERGE_MS = 300
TEXT_MERGE_MS = 1000

MODIFIER_KEYS = {"ctrl", "alt", "shift", "win"}
MODIFIER_ORDER = ["ctrl", "alt", "shift", "win"]
TEXT_BLOCKING_MODIFIERS = {"ctrl", "alt", "win"}

SHIFT_TEXT_KEYS: dict[str, str] = {
    "1": "!",
    "2": "@",
    "3": "#",
    "4": "$",
    "5": "%",
    "6": "^",
    "7": "&",
    "8": "*",
    "9": "(",
    "0": ")",
    "-": "_",
    "=": "+",
    "[": "{",
    "]": "}",
    "\\": "|",
    ";": ":",
    "'": '"',
    ",": "<",
    ".": ">",
    "/": "?",
    "`": "~",
}

NUMPAD_TEXT_KEYS: dict[str, str] = {
    "num0": "0",
    "num1": "1",
    "num2": "2",
    "num3": "3",
    "num4": "4",
    "num5": "5",
    "num6": "6",
    "num7": "7",
    "num8": "8",
    "num9": "9",
    "decimal": ".",
    "divide": "/",
    "multiply": "*",
    "subtract": "-",
    "add": "+",
}


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", ctypes.c_void_p),
        ("message", ctypes.c_uint),
        ("wParam", ctypes.c_size_t),
        ("lParam", ctypes.c_size_t),
        ("time", ctypes.c_ulong),
        ("pt", POINT),
    ]


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", ctypes.c_ulong),
        ("scanCode", ctypes.c_ulong),
        ("flags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("pt", POINT),
        ("mouseData", ctypes.c_ulong),
        ("flags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


KeyboardProc = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_int, ctypes.c_size_t, ctypes.c_void_p)
MouseProc = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_int, ctypes.c_size_t, ctypes.c_void_p)


def round_delay_ms(ms: float) -> int:
    return int(round(ms / 10.0) * 10)


def signed_high_word(value: int) -> int:
    word = (value >> 16) & 0xFFFF

    if word >= 0x8000:
        word -= 0x10000

    return word


@dataclass(slots=True)
class PendingScroll:
    started_at: float
    last_at: float
    clicks: int
    gaps_ms: list[int] = field(default_factory=list)


@dataclass(slots=True)
class PendingText:
    started_at: float
    last_input_at: float
    last_at: float
    text: str
    gaps_ms: list[int] = field(default_factory=list)


class RecordedStepBuilder:
    def __init__(
        self,
        target_rect: Rect | None = None,
        *,
        time_provider: Callable[[], float] = time.monotonic,
    ) -> None:
        self.target_rect = target_rect
        self.time_provider = time_provider
        self.steps: list[dict[str, Any]] = []
        self.pressed_keys: dict[str, float] = {}
        self.pressed_key_combos: dict[str, list[str]] = {}
        self.emitted_key_presses: set[str] = set()
        self.text_key_presses: set[str] = set()
        self.pressed_buttons: dict[str, float] = {}
        self.pending_text: PendingText | None = None
        self.pending_scroll: PendingScroll | None = None
        self.last_action_at: float | None = None
        self.paused = False
        self.action_count = 0

    def set_paused(self, paused: bool) -> None:
        self.flush_text()
        self.flush_scroll()
        self.paused = paused
        self.pressed_keys.clear()
        self.pressed_key_combos.clear()
        self.emitted_key_presses.clear()
        self.text_key_presses.clear()
        self.pressed_buttons.clear()
        self.last_action_at = None

    def record_key(self, key: str, is_down: bool, timestamp: float | None = None, text: str = "") -> None:
        if self.paused or not key:
            return

        now = self.resolve_time(timestamp)

        if is_down:
            if key not in self.pressed_keys:
                self.pressed_keys[key] = now
                input_text = self.normalize_input_text(key, text)

                if input_text:
                    self.flush_pressed_non_text_keys(now)
                    self.text_key_presses.add(key)
                    self.append_text(input_text, now)
                elif key not in MODIFIER_KEYS:
                    self.flush_text()
                    self.flush_scroll()
                    self.pressed_key_combos[key] = [
                        modifier for modifier in MODIFIER_ORDER if modifier in self.pressed_keys
                    ]

            return

        started_at = self.pressed_keys.pop(key, None)
        combo_keys = self.pressed_key_combos.pop(key, [])

        if key in self.emitted_key_presses:
            self.emitted_key_presses.remove(key)
            return

        if started_at is None or key in MODIFIER_KEYS:
            return

        if key in self.text_key_presses:
            self.text_key_presses.remove(key)
            self.touch_text(now)
            return

        self.flush_text()
        self.flush_scroll()
        combo_keys.append(key)
        hold_ms = max(1, round((now - started_at) * 1000))
        self.add_action({"type": "key", "key": "+".join(combo_keys), "hold_ms": hold_ms}, now, delay_at=started_at)

    def record_mouse_button(self, button: str, is_down: bool, x: int, y: int, timestamp: float | None = None) -> None:
        if self.paused:
            return

        now = self.resolve_time(timestamp)

        if is_down:
            self.flush_pressed_non_text_keys(now)
            self.pressed_buttons[button] = now
            return

        started_at = self.pressed_buttons.pop(button, None)

        if started_at is None:
            return

        self.flush_text()
        self.flush_scroll()
        step = {"type": "mouse_click", "button": button, **self.mouse_position_fields(x, y)}
        self.add_action(step, now, delay_at=started_at)

    def record_mouse_wheel(self, clicks: int, timestamp: float | None = None) -> None:
        if self.paused or clicks == 0:
            return

        now = self.resolve_time(timestamp)
        self.flush_pressed_non_text_keys(now)
        self.flush_text()

        if self.pending_scroll is not None:
            gap_ms = round((now - self.pending_scroll.last_at) * 1000)

            if gap_ms <= SCROLL_MERGE_MS:
                self.pending_scroll.clicks += clicks
                self.pending_scroll.gaps_ms.append(round_delay_ms(gap_ms))
                self.pending_scroll.last_at = now
                return

            self.flush_scroll()

        self.pending_scroll = PendingScroll(started_at=now, last_at=now, clicks=clicks)

    def finish(self) -> list[dict[str, Any]]:
        self.flush_text()
        self.flush_scroll()
        return list(self.steps)

    def append_text(self, text: str, timestamp: float) -> None:
        self.flush_scroll()

        if self.pending_text is not None:
            gap_ms = round((timestamp - self.pending_text.last_input_at) * 1000)

            if gap_ms <= TEXT_MERGE_MS:
                self.pending_text.text += text
                self.pending_text.gaps_ms.append(round_delay_ms(gap_ms))
                self.pending_text.last_input_at = timestamp
                self.pending_text.last_at = timestamp
                return

            self.flush_text()

        self.pending_text = PendingText(started_at=timestamp, last_input_at=timestamp, last_at=timestamp, text=text)

    def flush_pressed_non_text_keys(self, timestamp: float) -> None:
        for key in list(self.pressed_key_combos):
            started_at = self.pressed_keys.get(key)

            if started_at is None:
                self.pressed_key_combos.pop(key, None)
                continue

            combo_keys = self.pressed_key_combos.pop(key)
            combo_keys.append(key)
            hold_ms = max(1, round((timestamp - started_at) * 1000))
            self.add_action(
                {"type": "key", "key": "+".join(combo_keys), "hold_ms": hold_ms}, timestamp, delay_at=started_at
            )
            self.emitted_key_presses.add(key)

    def flush_text(self) -> None:
        if self.pending_text is None:
            return

        pending = self.pending_text
        self.pending_text = None
        interval_ms = 0

        if pending.gaps_ms:
            interval_ms = round(sum(pending.gaps_ms) / len(pending.gaps_ms))

        self.add_action(
            {"type": "text_input", "text": pending.text, "interval_ms": interval_ms},
            pending.last_at,
            delay_at=pending.started_at,
        )

    def touch_text(self, timestamp: float) -> None:
        if self.pending_text is not None:
            self.pending_text.last_at = max(self.pending_text.last_at, timestamp)

    def flush_scroll(self) -> None:
        if self.pending_scroll is None:
            return

        pending = self.pending_scroll
        self.pending_scroll = None
        interval_ms = 0

        if pending.gaps_ms:
            interval_ms = round(sum(pending.gaps_ms) / len(pending.gaps_ms))

        self.add_action(
            {"type": "mouse_scroll", "clicks": pending.clicks, "interval_ms": interval_ms},
            pending.last_at,
            delay_at=pending.started_at,
        )

    def add_action(self, step: dict[str, Any], timestamp: float, *, delay_at: float | None = None) -> None:
        self.add_delay(delay_at if delay_at is not None else timestamp)
        self.steps.append(step)
        self.last_action_at = timestamp
        self.action_count += 1

    def add_delay(self, timestamp: float) -> None:
        if self.last_action_at is None:
            return

        delay_ms = (timestamp - self.last_action_at) * 1000

        if delay_ms < DELAY_THRESHOLD_MS:
            return

        self.steps.append({"type": "delay", "ms": max(DELAY_THRESHOLD_MS, round_delay_ms(delay_ms))})

    def mouse_position_fields(self, x: int, y: int) -> dict[str, Any]:
        if self.target_rect is None:
            return {"target": "coordinate", "x": x, "y": y, "relative": False}

        return {
            "target": "coordinate",
            "x": x - self.target_rect.left,
            "y": y - self.target_rect.top,
            "relative": True,
        }

    def text_for_key(self, key: str) -> str:
        if key in MODIFIER_KEYS or any(modifier in self.pressed_keys for modifier in TEXT_BLOCKING_MODIFIERS):
            return ""

        shifted = "shift" in self.pressed_keys

        if len(key) == 1:
            if key.isalpha():
                return key.upper() if shifted else key

            return SHIFT_TEXT_KEYS.get(key, key) if shifted else key

        if key == "space":
            return " "

        return NUMPAD_TEXT_KEYS.get(key, "")

    def normalize_input_text(self, key: str, text: str) -> str:
        if not text:
            return self.text_for_key(key)

        if any(modifier in self.pressed_keys for modifier in TEXT_BLOCKING_MODIFIERS):
            return ""

        if "shift" not in self.pressed_keys or len(text) != 1:
            return text

        if text.isalpha() and text.islower():
            return text.upper()

        if text == key and key in SHIFT_TEXT_KEYS:
            return SHIFT_TEXT_KEYS[key]

        return text

    def resolve_time(self, timestamp: float | None) -> float:
        if timestamp is not None:
            return timestamp

        return self.time_provider()


class WindowsHookBackend:
    def __init__(self, recorder: "MacroRecorder") -> None:
        self.recorder = recorder
        self.user32 = ctypes.WinDLL("user32", use_last_error=True)
        self.user32.CallNextHookEx.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_size_t, ctypes.c_void_p]
        self.user32.CallNextHookEx.restype = ctypes.c_ssize_t
        self.keyboard_hook = ctypes.c_void_p()
        self.mouse_hook = ctypes.c_void_p()
        self.thread: threading.Thread | None = None
        self.thread_id = 0
        self.keyboard_proc = KeyboardProc(self.handle_keyboard)
        self.mouse_proc = MouseProc(self.handle_mouse)
        self.ready = threading.Event()

    def start(self) -> None:
        self.thread = threading.Thread(target=self.run_message_loop, name="MacroRecorderHook", daemon=True)
        self.thread.start()

        if not self.ready.wait(timeout=2):
            raise RuntimeError("Macro recorder hook thread did not start.")

        if not self.keyboard_hook or not self.mouse_hook:
            self.stop()
            raise RuntimeError("Macro recorder hooks could not be installed.")

    def stop(self) -> None:
        if self.keyboard_hook:
            self.user32.UnhookWindowsHookEx(self.keyboard_hook)
            self.keyboard_hook = ctypes.c_void_p()

        if self.mouse_hook:
            self.user32.UnhookWindowsHookEx(self.mouse_hook)
            self.mouse_hook = ctypes.c_void_p()

        if self.thread_id:
            self.user32.PostThreadMessageW(self.thread_id, WM_QUIT, 0, 0)

        if self.thread is not None:
            self.thread.join(timeout=1)
            self.thread = None

    def run_message_loop(self) -> None:
        self.thread_id = ctypes.windll.kernel32.GetCurrentThreadId()
        self.keyboard_hook = self.user32.SetWindowsHookExW(WH_KEYBOARD_LL, self.keyboard_proc, None, 0)
        self.mouse_hook = self.user32.SetWindowsHookExW(WH_MOUSE_LL, self.mouse_proc, None, 0)
        self.ready.set()

        message = MSG()

        while self.user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
            self.user32.TranslateMessage(ctypes.byref(message))
            self.user32.DispatchMessageW(ctypes.byref(message))

    def handle_keyboard(self, code: int, wparam: int, lparam: int) -> int:
        if code == HC_ACTION:
            data = ctypes.cast(lparam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
            is_down = wparam in (WM_KEYDOWN, WM_SYSKEYDOWN)
            is_up = wparam in (WM_KEYUP, WM_SYSKEYUP)

            if is_down or is_up:
                text = ""

                if is_down:
                    text = self.text_for_keyboard_event(int(data.vkCode), int(data.scanCode))

                self.recorder.handle_key_event(int(data.vkCode), is_down, text=text)

        return self.user32.CallNextHookEx(None, code, wparam, lparam)

    def text_for_keyboard_event(self, vk_code: int, scan_code: int) -> str:
        try:
            keyboard_state = (ctypes.c_ubyte * 256)()

            if not self.user32.GetKeyboardState(keyboard_state):
                return ""

            buffer = ctypes.create_unicode_buffer(8)
            result = self.user32.ToUnicodeEx(
                vk_code,
                scan_code,
                keyboard_state,
                buffer,
                len(buffer),
                0,
                self.current_keyboard_layout(),
            )

            if result <= 0:
                return ""

            return "".join(char for char in buffer[:result] if char.isprintable())
        except Exception as error:
            logger.debug("recorder: failed to translate keyboard event text: {}", error)
            return ""

    def current_keyboard_layout(self) -> int:
        hwnd = self.user32.GetForegroundWindow()
        thread_id = 0

        if hwnd:
            thread_id = self.user32.GetWindowThreadProcessId(hwnd, None)

        return self.user32.GetKeyboardLayout(thread_id)

    def handle_mouse(self, code: int, wparam: int, lparam: int) -> int:
        if code == HC_ACTION:
            data = ctypes.cast(lparam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
            x = int(data.pt.x)
            y = int(data.pt.y)

            if wparam in (WM_LBUTTONDOWN, WM_LBUTTONUP):
                self.recorder.handle_mouse_button_event("left", wparam == WM_LBUTTONDOWN, x, y)
            elif wparam in (WM_RBUTTONDOWN, WM_RBUTTONUP):
                self.recorder.handle_mouse_button_event("right", wparam == WM_RBUTTONDOWN, x, y)
            elif wparam in (WM_MBUTTONDOWN, WM_MBUTTONUP):
                self.recorder.handle_mouse_button_event("middle", wparam == WM_MBUTTONDOWN, x, y)
            elif wparam == WM_MOUSEWHEEL:
                wheel_delta = signed_high_word(int(data.mouseData))
                clicks = int(wheel_delta / WHEEL_DELTA)
                self.recorder.handle_mouse_wheel_event(clicks, x, y)

        return self.user32.CallNextHookEx(None, code, wparam, lparam)


class MacroRecorder:
    def __init__(
        self,
        target_rect: Rect | None = None,
        *,
        backend_factory: Callable[["MacroRecorder"], Any] | None = None,
        time_provider: Callable[[], float] = time.monotonic,
        foreground_hwnd_provider: Callable[[], int] | None = None,
        hwnd_at_point_provider: Callable[[int, int], int] | None = None,
        process_id_provider: Callable[[int], int] | None = None,
        current_process_id: int | None = None,
    ) -> None:
        self.builder = RecordedStepBuilder(target_rect, time_provider=time_provider)
        self.backend_factory = backend_factory or WindowsHookBackend
        self.foreground_hwnd_provider = foreground_hwnd_provider or win32gui.GetForegroundWindow
        self.hwnd_at_point_provider = hwnd_at_point_provider or self.window_from_point
        self.process_id_provider = process_id_provider or self.process_id_for_hwnd
        self.current_process_id = current_process_id if current_process_id is not None else os.getpid()
        self.backend: Any | None = None
        self.started_at = 0.0
        self.elapsed_offset_s = 0.0
        self.pause_started_at: float | None = None
        self.running = False
        self.lock = threading.RLock()
        self.time_provider = time_provider

    def start(self) -> None:
        with self.lock:
            if self.running:
                return

            self.started_at = self.time_provider()
            self.elapsed_offset_s = 0.0
            self.pause_started_at = None
            self.running = True
            backend = self.backend_factory(self)
            self.backend = backend

        if backend is None:
            with self.lock:
                self.running = False
                self.backend = None

            raise RuntimeError("Macro recorder backend could not be created.")

        try:
            backend.start()
        except Exception:
            with self.lock:
                self.running = False
                self.backend = None

            raise

    def stop(self) -> list[dict[str, Any]]:
        with self.lock:
            if not self.running:
                return self.builder.finish()

            backend = self.backend
            self.running = False
            self.backend = None

        if backend is not None:
            backend.stop()

        with self.lock:
            return self.builder.finish()

    def cancel(self) -> None:
        with self.lock:
            backend = self.backend
            self.running = False
            self.backend = None
            self.builder = RecordedStepBuilder(self.builder.target_rect, time_provider=self.time_provider)

        if backend is not None:
            backend.stop()

    def pause(self) -> None:
        with self.lock:
            if self.builder.paused:
                return

            self.pause_started_at = self.time_provider()
            self.builder.set_paused(True)

    def resume(self) -> None:
        with self.lock:
            if not self.builder.paused:
                return

            now = self.time_provider()

            if self.pause_started_at is not None:
                self.elapsed_offset_s += now - self.pause_started_at

            self.pause_started_at = None
            self.builder.set_paused(False)

    def is_paused(self) -> bool:
        with self.lock:
            return self.builder.paused

    def is_running(self) -> bool:
        with self.lock:
            return self.running

    def elapsed_s(self) -> float:
        with self.lock:
            if not self.running:
                return 0.0

            now = self.pause_started_at if self.pause_started_at is not None else self.time_provider()
            return max(0.0, now - self.started_at - self.elapsed_offset_s)

    def event_count(self) -> int:
        with self.lock:
            count = self.builder.action_count

            if self.builder.pending_scroll is not None:
                count += 1

            if self.builder.pending_text is not None:
                count += 1

            return count

    def handle_key_event(
        self,
        vk_code: int,
        is_down: bool,
        timestamp: float | None = None,
        text: str = "",
    ) -> None:
        key = vk_to_key(vk_code)

        if not key and not text:
            logger.debug("recorder: ignoring unknown vk code {}", vk_code)
            return

        if not key:
            key = f"vk_{vk_code}"

        with self.lock:
            if not self.running or self.is_self_keyboard_event():
                return

            self.builder.record_key(key, is_down, timestamp, text=text)

    def handle_mouse_button_event(
        self,
        button: str,
        is_down: bool,
        x: int,
        y: int,
        timestamp: float | None = None,
    ) -> None:
        with self.lock:
            if not self.running or self.is_self_mouse_event(x, y):
                return

            self.builder.record_mouse_button(button, is_down, x, y, timestamp)

    def handle_mouse_wheel_event(self, clicks: int, x: int, y: int, timestamp: float | None = None) -> None:
        with self.lock:
            if not self.running or self.is_self_mouse_event(x, y):
                return

            self.builder.record_mouse_wheel(clicks, timestamp)

    def is_self_keyboard_event(self) -> bool:
        try:
            return self.is_self_hwnd(self.foreground_hwnd_provider())
        except Exception as error:
            logger.debug("recorder: failed to inspect foreground window: {}", error)
            return False

    def is_self_mouse_event(self, x: int, y: int) -> bool:
        try:
            return self.is_self_hwnd(self.hwnd_at_point_provider(x, y))
        except Exception as error:
            logger.debug("recorder: failed to inspect mouse window: {}", error)
            return False

    def is_self_hwnd(self, hwnd: int) -> bool:
        if not hwnd:
            return False

        return self.process_id_provider(hwnd) == self.current_process_id

    @staticmethod
    def window_from_point(x: int, y: int) -> int:
        return win32gui.WindowFromPoint((x, y))

    @staticmethod
    def process_id_for_hwnd(hwnd: int) -> int:
        _, process_id = win32process.GetWindowThreadProcessId(hwnd)
        return int(process_id)
