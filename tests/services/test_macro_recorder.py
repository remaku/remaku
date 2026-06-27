import ctypes
from typing import Any, cast

import pytest

from remaku.core.keymap import vk_to_key
from remaku.core.window import Rect
from remaku.services import macro_recorder
from remaku.services.macro_recorder import (
    HC_ACTION,
    KBDLLHOOKSTRUCT,
    MSLLHOOKSTRUCT,
    POINT,
    WH_KEYBOARD_LL,
    WH_MOUSE_LL,
    WM_KEYDOWN,
    WM_KEYUP,
    WM_LBUTTONDOWN,
    WM_LBUTTONUP,
    WM_MBUTTONDOWN,
    WM_MOUSEWHEEL,
    WM_QUIT,
    WM_RBUTTONUP,
    MacroRecorder,
    RecordedStepBuilder,
    WindowsHookBackend,
    signed_high_word,
)


class FakeBackend:
    def __init__(self, recorder: MacroRecorder) -> None:
        self.recorder = recorder
        self.started = False
        self.stopped = False

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True


class RaisingBackend(FakeBackend):
    def start(self) -> None:
        raise RuntimeError("backend failed")


class FakeReady:
    def __init__(self, should_wait: bool = True) -> None:
        self.should_wait = should_wait
        self.was_set = False

    def wait(self, timeout: int) -> bool:
        return self.should_wait

    def set(self) -> None:
        self.was_set = True


class FakeThread:
    def __init__(self, target, name: str, daemon: bool) -> None:
        self.target = target
        self.name = name
        self.daemon = daemon
        self.started = False
        self.joined = False

    def start(self) -> None:
        self.started = True

    def join(self, timeout: int) -> None:
        self.joined = True


class FakeUser32:
    def __init__(self) -> None:
        self.unhooked = []
        self.posted_messages = []
        self.next_result = 321
        self.installed_hooks = []
        self.message_results = [0]
        self.translated = 0
        self.dispatched = 0
        self.keyboard_text = ""
        self.keyboard_state_available = True
        self.foreground_hwnd = 99
        self.keyboard_thread_id = 88
        self.keyboard_layout = 77

    def UnhookWindowsHookEx(self, hook) -> None:
        self.unhooked.append(hook)

    def PostThreadMessageW(self, thread_id: int, message: int, wparam: int, lparam: int) -> None:
        self.posted_messages.append((thread_id, message, wparam, lparam))

    def CallNextHookEx(self, hook, code: int, wparam: int, lparam: int) -> int:
        return self.next_result

    def SetWindowsHookExW(self, hook_type: int, proc, module, thread_id: int) -> ctypes.c_void_p:
        self.installed_hooks.append((hook_type, proc, module, thread_id))
        return ctypes.c_void_p(hook_type)

    def GetMessageW(self, message, hwnd, minimum: int, maximum: int) -> int:
        return self.message_results.pop(0)

    def TranslateMessage(self, message) -> None:
        self.translated += 1

    def DispatchMessageW(self, message) -> None:
        self.dispatched += 1

    def GetKeyboardState(self, keyboard_state) -> bool:
        return self.keyboard_state_available

    def ToUnicodeEx(
        self,
        vk_code: int,
        scan_code: int,
        keyboard_state,
        buffer,
        buffer_size: int,
        flags: int,
        keyboard_layout: int,
    ) -> int:
        for index, char in enumerate(self.keyboard_text[:buffer_size]):
            buffer[index] = char

        return len(self.keyboard_text[:buffer_size])

    def GetForegroundWindow(self) -> int:
        return self.foreground_hwnd

    def GetWindowThreadProcessId(self, hwnd: int, process_id) -> int:
        return self.keyboard_thread_id

    def GetKeyboardLayout(self, thread_id: int) -> int:
        return self.keyboard_layout


class FakeKernel32:
    def GetCurrentThreadId(self) -> int:
        return 77


class FakeWindll:
    kernel32 = FakeKernel32()


class HookRecorder:
    def __init__(self) -> None:
        self.keys = []
        self.buttons = []
        self.wheels = []

    def handle_key_event(self, vk_code: int, is_down: bool, text: str = "") -> None:
        self.keys.append((vk_code, is_down, text))

    def handle_mouse_button_event(self, button: str, is_down: bool, x: int, y: int) -> None:
        self.buttons.append((button, is_down, x, y))

    def handle_mouse_wheel_event(self, clicks: int, x: int, y: int) -> None:
        self.wheels.append((clicks, x, y))


def make_recorder(*, foreground_hwnd: int = 10, mouse_hwnd: int = 20, self_pid: int = 99) -> MacroRecorder:
    return MacroRecorder(
        Rect(100, 200, 800, 600),
        backend_factory=FakeBackend,
        foreground_hwnd_provider=lambda: foreground_hwnd,
        hwnd_at_point_provider=lambda x, y: mouse_hwnd,
        process_id_provider=lambda hwnd: self_pid if hwnd in (foreground_hwnd, mouse_hwnd) else 1,
        current_process_id=self_pid,
    )


def make_backend() -> Any:
    backend: Any = WindowsHookBackend.__new__(WindowsHookBackend)
    backend.recorder = HookRecorder()
    backend.user32 = FakeUser32()
    backend.keyboard_hook = ctypes.c_void_p()
    backend.mouse_hook = ctypes.c_void_p()
    backend.thread = None
    backend.thread_id = 0
    backend.keyboard_proc = object()
    backend.mouse_proc = object()
    backend.ready = FakeReady()
    return backend


def test_recorded_step_builder_inserts_rounded_delays_and_key_hold() -> None:
    builder = RecordedStepBuilder()

    builder.record_key("enter", True, 1.0)
    builder.record_key("enter", False, 1.09)
    builder.record_key("tab", True, 1.134)
    builder.record_key("tab", False, 1.2)
    builder.record_key("esc", True, 1.251)
    builder.record_key("esc", False, 1.3)

    assert builder.finish() == [
        {"type": "key", "key": "enter", "hold_ms": 90},
        {"type": "key", "key": "tab", "hold_ms": 66},
        {"type": "delay", "ms": 50},
        {"type": "key", "key": "esc", "hold_ms": 49},
    ]


def test_recorded_step_builder_ignores_auto_repeat_and_records_combo() -> None:
    builder = RecordedStepBuilder()

    builder.record_key("ctrl", True, 1.0)
    builder.record_key("a", True, 1.1)
    builder.record_key("a", True, 1.2)
    builder.record_key("a", False, 1.3)
    builder.record_key("ctrl", False, 1.4)

    assert builder.finish() == [{"type": "key", "key": "ctrl+a", "hold_ms": 200}]


def test_recorded_step_builder_records_plain_text_as_text_input() -> None:
    builder = RecordedStepBuilder()

    builder.record_key("h", True, 1.0)
    builder.record_key("e", True, 1.08)
    builder.record_key("h", False, 1.09)
    builder.record_key("e", False, 1.12)
    builder.record_key("l", True, 1.16)
    builder.record_key("l", False, 1.2)

    assert builder.finish() == [{"type": "text_input", "text": "hel", "interval_ms": 80}]


def test_recorded_step_builder_prefers_layout_text_over_vk_name() -> None:
    builder = RecordedStepBuilder()

    builder.record_key("a", True, 1.0, text="q")
    builder.record_key("a", False, 1.1)

    assert builder.finish() == [{"type": "text_input", "text": "q", "interval_ms": 0}]


def test_recorded_step_builder_preserves_fast_typing_press_order() -> None:
    builder = RecordedStepBuilder()

    builder.record_key("a", True, 1.0)
    builder.record_key("b", True, 1.01)
    builder.record_key("b", False, 1.02)
    builder.record_key("a", False, 1.03)

    assert builder.finish() == [{"type": "text_input", "text": "ab", "interval_ms": 10}]


def test_recorded_step_builder_records_shifted_text() -> None:
    builder = RecordedStepBuilder()

    builder.record_key("shift", True, 1.0)
    builder.record_key("a", True, 1.01)
    builder.record_key("a", False, 1.02)
    builder.record_key("1", True, 1.03)
    builder.record_key("1", False, 1.04)
    builder.record_key("shift", False, 1.05)

    assert builder.finish() == [{"type": "text_input", "text": "A!", "interval_ms": 20}]


def test_recorded_step_builder_corrects_unshifted_hook_text() -> None:
    builder = RecordedStepBuilder()

    builder.record_key("shift", True, 1.0)
    builder.record_key("a", True, 1.01, text="a")
    builder.record_key("a", False, 1.02)
    builder.record_key("1", True, 1.03, text="1")
    builder.record_key("1", False, 1.04)
    builder.record_key("shift", False, 1.05)

    assert builder.finish() == [{"type": "text_input", "text": "A!", "interval_ms": 20}]


def test_recorded_step_builder_splits_text_around_special_keys() -> None:
    builder = RecordedStepBuilder()

    builder.record_key("a", True, 1.0)
    builder.record_key("a", False, 1.05)
    builder.record_key("enter", True, 1.1)
    builder.record_key("enter", False, 1.15)
    builder.record_key("b", True, 1.2)
    builder.record_key("b", False, 1.25)

    assert builder.finish() == [
        {"type": "text_input", "text": "a", "interval_ms": 0},
        {"type": "delay", "ms": 50},
        {"type": "key", "key": "enter", "hold_ms": 50},
        {"type": "delay", "ms": 50},
        {"type": "text_input", "text": "b", "interval_ms": 0},
    ]


def test_recorded_step_builder_keeps_fast_enter_between_text_runs() -> None:
    builder = RecordedStepBuilder()

    builder.record_key("a", True, 1.00)
    builder.record_key("s", True, 1.01)
    builder.record_key("d", True, 1.02)
    builder.record_key("a", False, 1.03)
    builder.record_key("s", False, 1.04)
    builder.record_key("enter", True, 1.05)
    builder.record_key("d", False, 1.06)
    builder.record_key("a", True, 1.07)
    builder.record_key("enter", False, 1.08)
    builder.record_key("s", True, 1.09)
    builder.record_key("d", True, 1.10)
    builder.record_key("a", False, 1.11)
    builder.record_key("s", False, 1.12)
    builder.record_key("enter", True, 1.13)
    builder.record_key("d", False, 1.14)
    builder.record_key("a", True, 1.15)
    builder.record_key("enter", False, 1.16)
    builder.record_key("s", True, 1.17)
    builder.record_key("d", True, 1.18)
    builder.record_key("a", False, 1.19)
    builder.record_key("s", False, 1.20)
    builder.record_key("enter", True, 1.21)
    builder.record_key("d", False, 1.22)
    builder.record_key("enter", False, 1.24)

    assert builder.finish() == [
        {"type": "text_input", "text": "asd", "interval_ms": 10},
        {"type": "key", "key": "enter", "hold_ms": 20},
        {"type": "text_input", "text": "asd", "interval_ms": 15},
        {"type": "key", "key": "enter", "hold_ms": 20},
        {"type": "text_input", "text": "asd", "interval_ms": 15},
        {"type": "key", "key": "enter", "hold_ms": 30},
    ]


def test_recorded_step_builder_pause_excludes_events_and_delay() -> None:
    builder = RecordedStepBuilder()

    builder.record_key("a", True, 1.0)
    builder.record_key("a", False, 1.1)
    builder.set_paused(True)
    builder.record_key("b", True, 5.0)
    builder.record_key("b", False, 5.1)
    builder.set_paused(False)
    builder.record_key("c", True, 9.0)
    builder.record_key("c", False, 9.1)

    assert builder.finish() == [
        {"type": "text_input", "text": "a", "interval_ms": 0},
        {"type": "text_input", "text": "c", "interval_ms": 0},
    ]


def test_recorded_step_builder_ignores_events_while_paused() -> None:
    builder = RecordedStepBuilder()

    builder.set_paused(True)
    builder.record_key("a", True, 1.0)
    builder.record_mouse_button("left", True, 10, 20, 1.0)
    builder.record_mouse_wheel(1, 1.0)

    assert builder.finish() == []


def test_recorded_step_builder_ignores_empty_key_and_unmatched_mouse_up() -> None:
    builder = RecordedStepBuilder()

    builder.record_key("", True, 1.0)
    builder.record_mouse_button("left", False, 10, 20, 1.0)

    assert builder.finish() == []


def test_recorded_step_builder_records_relative_click_coordinates() -> None:
    builder = RecordedStepBuilder(Rect(100, 200, 300, 400))

    builder.record_mouse_button("left", True, 140, 260, 1.0)
    builder.record_mouse_button("left", False, 150, 270, 1.1)

    assert builder.finish() == [
        {"type": "mouse_click", "button": "left", "target": "coordinate", "x": 50, "y": 70, "relative": True}
    ]


def test_recorded_step_builder_records_absolute_click_without_target_rect() -> None:
    builder = RecordedStepBuilder()

    builder.record_mouse_button("right", True, 140, 260, 1.0)
    builder.record_mouse_button("right", False, 140, 260, 1.1)

    assert builder.finish() == [
        {"type": "mouse_click", "button": "right", "target": "coordinate", "x": 140, "y": 260, "relative": False}
    ]


def test_recorded_step_builder_merges_fast_scroll_events() -> None:
    builder = RecordedStepBuilder()

    builder.record_mouse_wheel(1, 1.0)
    builder.record_mouse_wheel(1, 1.12)
    builder.record_mouse_wheel(-1, 1.24)

    assert builder.finish() == [{"type": "mouse_scroll", "clicks": 1, "interval_ms": 120}]


def test_recorded_step_builder_splits_slow_scroll_events() -> None:
    builder = RecordedStepBuilder()

    builder.record_mouse_wheel(1, 1.0)
    builder.record_mouse_wheel(1, 1.5)

    assert builder.finish() == [
        {"type": "mouse_scroll", "clicks": 1, "interval_ms": 0},
        {"type": "delay", "ms": 500},
        {"type": "mouse_scroll", "clicks": 1, "interval_ms": 0},
    ]


def test_recorded_step_builder_splits_slow_text_events() -> None:
    builder = RecordedStepBuilder()

    builder.record_key("a", True, 1.0)
    builder.record_key("a", False, 1.05)
    builder.record_key("b", True, 2.2)
    builder.record_key("b", False, 2.25)

    assert builder.finish() == [
        {"type": "text_input", "text": "a", "interval_ms": 0},
        {"type": "delay", "ms": 1150},
        {"type": "text_input", "text": "b", "interval_ms": 0},
    ]


def test_recorded_step_builder_flushes_stale_non_text_key_state() -> None:
    builder = RecordedStepBuilder()
    builder.pressed_key_combos["enter"] = []

    builder.record_key("a", True, 1.0)
    builder.record_key("a", False, 1.1)

    assert builder.finish() == [{"type": "text_input", "text": "a", "interval_ms": 0}]


def test_recorded_step_builder_records_space_numpad_and_time_provider() -> None:
    times = iter([1.0, 1.1, 1.2, 1.3])
    builder = RecordedStepBuilder(time_provider=lambda: next(times))

    builder.record_key("space", True)
    builder.record_key("space", False)
    builder.record_key("num1", True)
    builder.record_key("num1", False)

    assert builder.finish() == [{"type": "text_input", "text": " 1", "interval_ms": 200}]


def test_recorded_step_builder_ctrl_blocks_text_input() -> None:
    builder = RecordedStepBuilder()

    builder.record_key("ctrl", True, 1.0)
    builder.record_key("a", True, 1.1)
    builder.record_key("a", False, 1.2)
    builder.record_key("ctrl", False, 1.3)

    assert builder.finish() == [{"type": "key", "key": "ctrl+a", "hold_ms": 100}]


def test_macro_recorder_filters_self_keyboard_and_mouse_events() -> None:
    recorder = make_recorder(foreground_hwnd=10, mouse_hwnd=20)
    recorder.start()

    recorder.handle_key_event(0x41, True, 1.0)
    recorder.handle_key_event(0x41, False, 1.1)
    recorder.handle_mouse_button_event("left", True, 150, 250, 1.2)
    recorder.handle_mouse_button_event("left", False, 150, 250, 1.3)

    assert recorder.stop() == []


def test_macro_recorder_accepts_non_self_events() -> None:
    recorder = MacroRecorder(
        backend_factory=FakeBackend,
        foreground_hwnd_provider=lambda: 10,
        hwnd_at_point_provider=lambda x, y: 20,
        process_id_provider=lambda hwnd: 2,
        current_process_id=1,
    )
    recorder.start()

    recorder.handle_key_event(0x41, True, 1.0)
    recorder.handle_key_event(0x41, False, 1.1)
    recorder.handle_mouse_button_event("left", True, 150, 250, 1.2)
    recorder.handle_mouse_button_event("left", False, 150, 250, 1.3)

    assert recorder.stop() == [
        {"type": "text_input", "text": "a", "interval_ms": 0},
        {"type": "delay", "ms": 100},
        {"type": "mouse_click", "button": "left", "target": "coordinate", "x": 150, "y": 250, "relative": False},
    ]


def test_macro_recorder_records_layout_text_from_keyboard_event() -> None:
    recorder = MacroRecorder(
        backend_factory=FakeBackend,
        foreground_hwnd_provider=lambda: 10,
        process_id_provider=lambda hwnd: 2,
        current_process_id=1,
    )
    recorder.start()

    recorder.handle_key_event(0x41, True, 1.0, text="q")
    recorder.handle_key_event(0x41, False, 1.1)

    assert recorder.stop() == [{"type": "text_input", "text": "q", "interval_ms": 0}]


def test_macro_recorder_records_shift_letter_as_uppercase_when_hook_text_is_unshifted() -> None:
    recorder = MacroRecorder(
        backend_factory=FakeBackend,
        foreground_hwnd_provider=lambda: 10,
        process_id_provider=lambda hwnd: 2,
        current_process_id=1,
    )
    recorder.start()

    recorder.handle_key_event(0xA0, True, 1.0)
    recorder.handle_key_event(0x41, True, 1.01, text="a")
    recorder.handle_key_event(0x41, False, 1.02)
    recorder.handle_key_event(0xA0, False, 1.03)

    assert recorder.stop() == [{"type": "text_input", "text": "A", "interval_ms": 0}]


def test_macro_recorder_can_record_text_for_unknown_vk() -> None:
    recorder = MacroRecorder(
        backend_factory=FakeBackend,
        foreground_hwnd_provider=lambda: 10,
        process_id_provider=lambda hwnd: 2,
        current_process_id=1,
    )
    recorder.start()

    recorder.handle_key_event(0xFF, True, 1.0, text="é")
    recorder.handle_key_event(0xFF, False, 1.1, text="")

    assert recorder.stop() == [{"type": "text_input", "text": "é", "interval_ms": 0}]


def test_macro_recorder_start_is_idempotent() -> None:
    recorder = make_recorder(foreground_hwnd=10, mouse_hwnd=20)

    recorder.start()
    backend = recorder.backend
    recorder.start()

    assert recorder.backend is backend


def test_macro_recorder_start_handles_missing_backend() -> None:
    recorder = MacroRecorder(backend_factory=lambda current_recorder: None)

    with pytest.raises(RuntimeError, match="backend could not be created"):
        recorder.start()

    assert not recorder.is_running()
    assert recorder.backend is None


def test_macro_recorder_start_resets_state_when_backend_fails() -> None:
    recorder = MacroRecorder(backend_factory=RaisingBackend)

    with pytest.raises(RuntimeError, match="backend failed"):
        recorder.start()

    assert not recorder.is_running()
    assert recorder.backend is None


def test_macro_recorder_stop_when_not_running_finishes_pending_steps() -> None:
    recorder = MacroRecorder()
    recorder.builder.record_key("a", True, 1.0)
    recorder.builder.record_key("a", False, 1.1)

    assert recorder.stop() == [{"type": "text_input", "text": "a", "interval_ms": 0}]


def test_macro_recorder_cancel_stops_backend_and_resets_builder() -> None:
    recorder = MacroRecorder(backend_factory=FakeBackend)
    recorder.start()
    backend = recorder.backend
    recorder.builder.record_key("a", True, 1.0)

    recorder.cancel()

    assert isinstance(backend, FakeBackend)
    assert backend.stopped
    assert not recorder.is_running()
    assert recorder.stop() == []


def test_macro_recorder_pause_resume_elapsed_and_event_count() -> None:
    times = iter([10.0, 11.0, 12.5, 13.0, 13.5])
    recorder = MacroRecorder(
        backend_factory=FakeBackend,
        time_provider=lambda: next(times),
        foreground_hwnd_provider=lambda: 10,
        process_id_provider=lambda hwnd: 2,
        current_process_id=1,
    )

    assert recorder.elapsed_s() == 0.0
    recorder.start()
    assert recorder.is_running()
    recorder.handle_key_event(0x41, True, 10.2)
    assert recorder.event_count() == 1
    recorder.pause()
    recorder.pause()
    assert recorder.is_paused()
    assert recorder.elapsed_s() == 1.0
    recorder.resume()
    recorder.resume()
    assert not recorder.is_paused()
    assert recorder.elapsed_s() == 1.5


def test_macro_recorder_ignores_mouse_wheel_when_not_running() -> None:
    recorder = MacroRecorder(backend_factory=FakeBackend)

    recorder.handle_mouse_wheel_event(1, 10, 20, 1.0)

    assert recorder.stop() == []


def test_macro_recorder_records_mouse_wheel_and_counts_pending_scroll() -> None:
    recorder = MacroRecorder(
        backend_factory=FakeBackend,
        foreground_hwnd_provider=lambda: 10,
        hwnd_at_point_provider=lambda x, y: 20,
        process_id_provider=lambda hwnd: 2,
        current_process_id=1,
    )

    recorder.start()
    recorder.handle_mouse_wheel_event(1, 10, 20, 1.0)

    assert recorder.event_count() == 1
    assert recorder.stop() == [{"type": "mouse_scroll", "clicks": 1, "interval_ms": 0}]


def test_macro_recorder_filter_failures_are_non_fatal(monkeypatch) -> None:
    messages = []
    recorder = MacroRecorder(
        backend_factory=FakeBackend,
        foreground_hwnd_provider=lambda: (_ for _ in ()).throw(RuntimeError("foreground failed")),
        hwnd_at_point_provider=lambda x, y: (_ for _ in ()).throw(RuntimeError("mouse failed")),
        process_id_provider=lambda hwnd: 2,
        current_process_id=1,
    )
    monkeypatch.setattr(macro_recorder.logger, "debug", lambda message, error: messages.append((message, str(error))))

    assert not recorder.is_self_keyboard_event()
    assert not recorder.is_self_mouse_event(10, 20)
    assert messages == [
        ("recorder: failed to inspect foreground window: {}", "foreground failed"),
        ("recorder: failed to inspect mouse window: {}", "mouse failed"),
    ]


def test_macro_recorder_self_hwnd_and_static_window_helpers(monkeypatch) -> None:
    recorder = MacroRecorder(process_id_provider=lambda hwnd: 1, current_process_id=1)
    monkeypatch.setattr(macro_recorder.win32gui, "WindowFromPoint", lambda point: point[0] + point[1])
    monkeypatch.setattr(macro_recorder.win32process, "GetWindowThreadProcessId", lambda hwnd: (7, hwnd + 1))

    assert not recorder.is_self_hwnd(0)
    assert recorder.is_self_hwnd(10)
    assert MacroRecorder.window_from_point(3, 4) == 7
    assert MacroRecorder.process_id_for_hwnd(8) == 9


def test_vk_to_key_maps_letters_digits_modifiers_and_function_keys() -> None:
    assert vk_to_key(0x41) == "a"
    assert vk_to_key(0x35) == "5"
    assert vk_to_key(0xA2) == "ctrl"
    assert vk_to_key(0x70) == "f1"


def test_vk_to_key_maps_common_punctuation_keys() -> None:
    assert vk_to_key(0xBA) == ";"
    assert vk_to_key(0xBB) == "="
    assert vk_to_key(0xBC) == ","
    assert vk_to_key(0xBD) == "-"
    assert vk_to_key(0xBE) == "."
    assert vk_to_key(0xBF) == "/"
    assert vk_to_key(0xC0) == "`"
    assert vk_to_key(0xDB) == "["
    assert vk_to_key(0xDC) == "\\"
    assert vk_to_key(0xDD) == "]"
    assert vk_to_key(0xDE) == "'"


def test_macro_recorder_logs_unknown_vk_code(monkeypatch) -> None:
    messages = []
    recorder = make_recorder(foreground_hwnd=10, mouse_hwnd=20)
    recorder.start()
    monkeypatch.setattr(macro_recorder.logger, "debug", lambda message, value: messages.append((message, value)))

    recorder.handle_key_event(0xFF, True, 1.0)

    assert messages == [("recorder: ignoring unknown vk code {}", 0xFF)]


def test_signed_high_word_returns_wheel_delta() -> None:
    assert signed_high_word(0x00780000) == 120
    assert signed_high_word(0xFF880000) == -120


def test_windows_hook_backend_initializes_callbacks(monkeypatch) -> None:
    monkeypatch.setattr(macro_recorder.ctypes, "WinDLL", lambda name, use_last_error: FakeUser32())

    backend: Any = WindowsHookBackend(cast(Any, HookRecorder()))

    assert isinstance(backend.user32, FakeUser32)
    assert not backend.keyboard_hook
    assert not backend.mouse_hook
    assert backend.thread is None
    assert backend.thread_id == 0


def test_windows_hook_backend_configures_call_next_hook_signature(monkeypatch) -> None:
    class FakeCallNextHook:
        argtypes = None
        restype = None

        def __call__(self, hook, code: int, wparam: int, lparam: int) -> int:
            return 0

    class FakeUser32WithSignatureHook(FakeUser32):
        def __init__(self) -> None:
            super().__init__()
            self.CallNextHookEx = FakeCallNextHook()

    user32 = FakeUser32WithSignatureHook()
    monkeypatch.setattr(macro_recorder.ctypes, "WinDLL", lambda name, use_last_error: user32)

    WindowsHookBackend(cast(Any, HookRecorder()))

    assert cast(Any, user32.CallNextHookEx).argtypes == [
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_size_t,
        ctypes.c_void_p,
    ]
    assert cast(Any, user32.CallNextHookEx).restype is ctypes.c_ssize_t


def test_windows_hook_backend_start_timeout(monkeypatch) -> None:
    backend = make_backend()
    backend.ready = FakeReady(False)
    monkeypatch.setattr(macro_recorder.threading, "Thread", FakeThread)

    with pytest.raises(RuntimeError, match="hook thread did not start"):
        backend.start()

    assert backend.thread.started


def test_windows_hook_backend_start_missing_hooks_stops(monkeypatch) -> None:
    backend = make_backend()
    stopped = []
    monkeypatch.setattr(macro_recorder.threading, "Thread", FakeThread)
    monkeypatch.setattr(backend, "stop", lambda: stopped.append(True))

    with pytest.raises(RuntimeError, match="hooks could not be installed"):
        backend.start()

    assert stopped == [True]


def test_windows_hook_backend_start_succeeds(monkeypatch) -> None:
    backend = make_backend()
    backend.keyboard_hook = ctypes.c_void_p(1)
    backend.mouse_hook = ctypes.c_void_p(2)
    monkeypatch.setattr(macro_recorder.threading, "Thread", FakeThread)

    backend.start()

    assert backend.thread.started


def test_windows_hook_backend_stop_unhooks_posts_quit_and_joins() -> None:
    backend = make_backend()
    backend.keyboard_hook = ctypes.c_void_p(1)
    backend.mouse_hook = ctypes.c_void_p(2)
    backend.thread_id = 77
    backend.thread = FakeThread(lambda: None, "MacroRecorderHook", True)

    backend.stop()

    user32 = cast(FakeUser32, backend.user32)

    assert len(user32.unhooked) == 2
    assert user32.posted_messages == [(77, WM_QUIT, 0, 0)]
    assert backend.thread is None
    assert not backend.keyboard_hook
    assert not backend.mouse_hook


def test_windows_hook_backend_run_message_loop_installs_hooks(monkeypatch) -> None:
    backend = make_backend()
    user32 = cast(FakeUser32, backend.user32)
    user32.message_results = [1, 0]
    monkeypatch.setattr(macro_recorder.ctypes, "windll", FakeWindll())

    backend.run_message_loop()

    assert backend.thread_id == 77
    assert [hook[0] for hook in user32.installed_hooks] == [WH_KEYBOARD_LL, WH_MOUSE_LL]
    assert backend.ready.was_set
    assert user32.translated == 1
    assert user32.dispatched == 1


def test_windows_hook_backend_handles_keyboard_events() -> None:
    backend = make_backend()
    data = KBDLLHOOKSTRUCT(0x41, 0, 0, 0, 0)
    pointer = ctypes.cast(ctypes.pointer(data), ctypes.c_void_p).value
    assert pointer is not None

    assert backend.handle_keyboard(HC_ACTION, WM_KEYDOWN, pointer) == 321
    assert backend.handle_keyboard(HC_ACTION, WM_KEYUP, pointer) == 321
    assert backend.handle_keyboard(1, WM_KEYDOWN, pointer) == 321
    assert backend.recorder.keys == [(0x41, True, ""), (0x41, False, "")]


def test_windows_hook_backend_translates_keyboard_text_with_active_layout() -> None:
    backend = make_backend()
    user32 = cast(FakeUser32, backend.user32)
    user32.keyboard_text = "q"
    data = KBDLLHOOKSTRUCT(0x41, 30, 0, 0, 0)
    pointer = ctypes.cast(ctypes.pointer(data), ctypes.c_void_p).value
    assert pointer is not None

    backend.handle_keyboard(HC_ACTION, WM_KEYDOWN, pointer)

    assert backend.recorder.keys == [(0x41, True, "q")]


def test_windows_hook_backend_ignores_non_printable_translated_text() -> None:
    backend = make_backend()
    user32 = cast(FakeUser32, backend.user32)
    user32.keyboard_text = "\r"
    data = KBDLLHOOKSTRUCT(0x0D, 28, 0, 0, 0)
    pointer = ctypes.cast(ctypes.pointer(data), ctypes.c_void_p).value
    assert pointer is not None

    backend.handle_keyboard(HC_ACTION, WM_KEYDOWN, pointer)

    assert backend.recorder.keys == [(0x0D, True, "")]


def test_windows_hook_backend_returns_empty_text_when_keyboard_state_unavailable() -> None:
    backend = make_backend()
    user32 = cast(FakeUser32, backend.user32)
    user32.keyboard_state_available = False

    assert backend.text_for_keyboard_event(0x41, 30) == ""


def test_windows_hook_backend_returns_empty_text_when_translation_fails(monkeypatch) -> None:
    backend = make_backend()
    user32 = cast(FakeUser32, backend.user32)
    monkeypatch.setattr(
        user32,
        "ToUnicodeEx",
        lambda vk_code, scan_code, keyboard_state, buffer, buffer_size, flags, keyboard_layout: (
            failure for failure in ()
        ).throw(RuntimeError("translation failed")),
    )

    assert backend.text_for_keyboard_event(0x41, 30) == ""


def test_windows_hook_backend_handles_mouse_events() -> None:
    backend = make_backend()
    data = MSLLHOOKSTRUCT(POINT(10, 20), 0, 0, 0, 0)
    pointer = ctypes.cast(ctypes.pointer(data), ctypes.c_void_p).value
    assert pointer is not None

    backend.handle_mouse(HC_ACTION, WM_LBUTTONDOWN, pointer)
    backend.handle_mouse(HC_ACTION, WM_LBUTTONUP, pointer)
    backend.handle_mouse(HC_ACTION, WM_RBUTTONUP, pointer)
    backend.handle_mouse(HC_ACTION, WM_MBUTTONDOWN, pointer)

    data.mouseData = 0x00780000
    backend.handle_mouse(HC_ACTION, WM_MOUSEWHEEL, pointer)
    backend.handle_mouse(1, WM_MOUSEWHEEL, pointer)

    assert backend.recorder.buttons == [
        ("left", True, 10, 20),
        ("left", False, 10, 20),
        ("right", False, 10, 20),
        ("middle", True, 10, 20),
    ]
    assert backend.recorder.wheels == [(1, 10, 20)]


def test_recorded_step_builder_normalizes_shift_and_blocked_text() -> None:
    builder = RecordedStepBuilder()

    assert builder.normalize_input_text("a", "") == "a"

    builder.pressed_keys["shift"] = 1.0
    assert builder.normalize_input_text("a", "a") == "A"
    assert builder.normalize_input_text("1", "1") == "!"
    assert builder.normalize_input_text("q", "Q") == "Q"

    builder.pressed_keys["ctrl"] = 1.0
    assert builder.normalize_input_text("a", "a") == ""


def test_recorded_step_builder_resolve_time_uses_provider() -> None:
    builder = RecordedStepBuilder(time_provider=lambda: 12.5)

    assert builder.resolve_time(3.0) == 3.0
    assert builder.resolve_time(None) == 12.5
