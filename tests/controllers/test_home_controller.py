import json
import zipfile
from pathlib import Path
from typing import Any, cast

from PySide6.QtCore import Qt

from remaku.controllers import home_controller
from remaku.controllers.home_controller import HomeController
from remaku.models.config_model import AppConfig
from remaku.models.macro_model import Macro, MacroMeta, MacroModel, MacroSummary, TemplateInfo
from remaku.models.step_tree import StepTree
from remaku.services import hotkey_service, macro_import_service
from remaku.services.clipboard_service import ClipboardService
from remaku.services.engine import Status
from remaku.services.template_service import TemplateService
from remaku.views.components.hotkey_edit import HotkeyEdit


class FakeMacroModel:
    def __init__(self, existing_ids: set[str] | None = None, macros: dict[str, Macro] | None = None) -> None:
        self.existing_ids = existing_ids or set()
        self.macros = macros or {}
        self.saved: list[Macro] = []
        self.deleted: list[str] = []

    def list_macros(self) -> list[MacroSummary]:
        ids = sorted(self.existing_ids | set(self.macros))
        return [MacroSummary(id=macro_id, label=macro_id.upper(), path=f"{macro_id}.json") for macro_id in ids]

    def load(self, macro_id: str) -> Macro | None:
        return self.macros.get(macro_id)

    def save(self, macro: Macro) -> None:
        self.saved.append(macro)
        self.macros[macro.meta.id] = macro
        self.existing_ids.add(macro.meta.id)

    def delete(self, macro_id: str) -> bool:
        if macro_id not in self.macros and macro_id not in self.existing_ids:
            return False

        self.deleted.append(macro_id)
        self.macros.pop(macro_id, None)
        self.existing_ids.discard(macro_id)
        return True


class FakeWindow:
    def __init__(self) -> None:
        self.show_normal_calls = 0
        self.show_minimized_calls = 0

    def showNormal(self) -> None:
        self.show_normal_calls += 1

    def showMinimized(self) -> None:
        self.show_minimized_calls += 1

    def winId(self) -> int:
        return 99


class FakeMacroListItem:
    def __init__(self, macro_id: str) -> None:
        self.macro_id = macro_id

    def data(self, role) -> str:
        assert role == Qt.ItemDataRole.UserRole
        return self.macro_id


class FakeMacroList:
    def __init__(self, macro_ids: list[str]) -> None:
        self.items = [FakeMacroListItem(macro_id) for macro_id in macro_ids]
        self.current_item: FakeMacroListItem | None = None
        self.blocked_states: list[bool] = []
        self.disabled = False

    def blockSignals(self, blocked: bool) -> None:
        self.blocked_states.append(blocked)

    def count(self) -> int:
        return len(self.items)

    def item(self, index: int) -> FakeMacroListItem:
        return self.items[index]

    def setCurrentItem(self, item: FakeMacroListItem) -> None:
        self.current_item = item

    def setDisabled(self, disabled: bool) -> None:
        self.disabled = disabled


class FakeLeftPanel:
    def __init__(self, macro_ids: list[str]) -> None:
        self.macro_list = FakeMacroList(macro_ids)
        self.new_macro_button = FakeButton()
        self.list_items: list[tuple[str, str]] = []
        self.selected_macro_id = ""

    def set_macro_list(self, items: list[tuple[str, str]], selected_macro_id: str = "") -> None:
        self.list_items = items
        self.selected_macro_id = selected_macro_id


class FakeStepList:
    def __init__(self) -> None:
        self.disabled = False
        self.itemSelectionChanged = FakeSignal()

    def selectedItems(self) -> list:
        return []

    def setDisabled(self, disabled: bool) -> None:
        self.disabled = disabled


class FakeCenterPanel:
    def __init__(self) -> None:
        self.step_tree_items: list[dict] = []
        self.selected_step = None
        self.selected_branch = None
        self.item_to_step: dict[object, dict] = {}
        self.step_list = FakeStepList()

    def set_step_tree(self, items: list[dict], selected_step=None, selected_branch=None) -> None:
        self.step_tree_items = items
        self.selected_step = selected_step
        self.selected_branch = selected_branch


class FakeRightPanel:
    def __init__(self) -> None:
        self.macro_properties: Macro | None = None
        self.step_properties: tuple | None = None
        self.branch_properties: tuple | None = None
        self.disabled = False

    def show_macro_properties(self, macro: Macro | None) -> None:
        self.macro_properties = macro

    def show_step_properties(self, *args) -> None:
        self.step_properties = args

    def show_branch_properties(self, *args) -> None:
        self.branch_properties = args

    def setDisabled(self, disabled: bool) -> None:
        self.disabled = disabled


class FakeButton:
    def __init__(self) -> None:
        self.enabled = True
        self.disabled = False

    def setEnabled(self, enabled: bool) -> None:
        self.enabled = enabled

    def setDisabled(self, disabled: bool) -> None:
        self.disabled = disabled


class FakeToolbar:
    def __init__(self) -> None:
        self.run_button = FakeButton()
        self.record_button = FakeButton()
        self.add_button = FakeButton()
        self.delete_button = FakeButton()
        self.move_up_button = FakeButton()
        self.move_down_button = FakeButton()
        self.undo_button = FakeButton()
        self.redo_button = FakeButton()
        self.file_menu_button = FakeButton()
        self.edit_menu_button = FakeButton()


class FakeView:
    def __init__(self) -> None:
        self.statuses: list[str] = []
        self.fake_window = FakeWindow()
        self.left_panel = FakeLeftPanel([])
        self.center_panel = FakeCenterPanel()
        self.right_panel = FakeRightPanel()
        self.toolbar = FakeToolbar()

    def set_status_text(self, text: str) -> None:
        self.statuses.append(text)

    def window(self) -> FakeWindow:
        return self.fake_window


class FakeConfigModel:
    def __init__(self) -> None:
        self.config = AppConfig()
        self.save_calls = 0

    def save(self) -> None:
        self.save_calls += 1


class FakeDialog:
    def __init__(self, accepted: bool, value: str = "") -> None:
        self.accepted = accepted
        self.dialog_value = value

    def exec(self) -> bool:
        return self.accepted

    def value(self) -> str:
        return self.dialog_value


class FakeRunner:
    def __init__(self, *, running: bool = False, status: Status | None = None) -> None:
        self.label = "Runner"
        self.running = running
        self.status = status or Status()
        self.macro: dict[str, Any] = {"steps": []}
        self.macro_path = Path("macro.json")
        self.current_step_path: Any = None
        self.start_calls = 0
        self.stop_calls = 0
        self.pause_calls = 0
        self.resume_calls = 0
        self.paused = False

    def is_running(self) -> bool:
        return self.running

    def is_paused(self) -> bool:
        return self.paused

    def start(self) -> None:
        self.start_calls += 1
        self.running = True

    def stop(self) -> None:
        self.stop_calls += 1
        self.running = False

    def pause(self) -> None:
        self.pause_calls += 1
        self.paused = True

    def resume(self) -> None:
        self.resume_calls += 1
        self.paused = False

    def get_status(self) -> Status:
        return self.status


class FakeRecorder:
    def __init__(self, steps: list[dict] | None = None) -> None:
        self.steps = steps or []
        self.running = False
        self.paused = False
        self.start_calls = 0
        self.stop_calls = 0
        self.cancel_calls = 0
        self.pause_calls = 0
        self.resume_calls = 0

    def start(self) -> None:
        self.start_calls += 1
        self.running = True

    def stop(self) -> list[dict]:
        self.stop_calls += 1
        self.running = False
        return self.steps

    def cancel(self) -> None:
        self.cancel_calls += 1
        self.running = False

    def pause(self) -> None:
        self.pause_calls += 1
        self.paused = True

    def resume(self) -> None:
        self.resume_calls += 1
        self.paused = False

    def is_running(self) -> bool:
        return self.running

    def is_paused(self) -> bool:
        return self.paused

    def elapsed_s(self) -> float:
        return 12.0

    def event_count(self) -> int:
        return len(self.steps)


class FakeRecordingOverlay:
    def __init__(self, stats_provider, parent) -> None:
        self.stats_provider = stats_provider
        self.parent = parent
        self.started = False
        self.stopped = False
        self.paused_values: list[bool] = []
        self.positions = []

    def move(self, x: int, y: int) -> None:
        self.positions.append((x, y))

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True

    def set_paused(self, paused: bool) -> None:
        self.paused_values.append(paused)


def make_controller() -> HomeController:
    controller = cast(Any, HomeController.__new__(HomeController))
    controller.current_macro = None
    controller.current_runner = None
    controller.current_recorder = None
    controller.recording_overlay = None
    controller.selected_macro_id = ""
    controller.selected_step = None
    controller.selected_branch_parent = None
    controller.selected_branch_key = ""
    controller.step_tree = None
    controller.view = FakeView()
    controller.macro_model = cast(MacroModel, FakeMacroModel())
    controller.editing_locked = False
    controller.editing_shortcuts = []
    controller.undo_stacks = {}
    controller.redo_stacks = {}
    controller.undo_selection_indexes = {}
    controller.redo_selection_indexes = {}
    controller.step_clipboard = None
    controller.clipboard_service = ClipboardService(
        lambda macro_id, template_id: home_controller.template_path(macro_id, template_id),
        lambda macro_id: home_controller.templates_dir(macro_id),
        controller.generate_template_id,
        controller.default_template_label,
    )
    controller.template_service = TemplateService(
        controller.generate_template_id,
        controller.default_template_label,
        lambda macro_id, template_id: home_controller.template_path(macro_id, template_id),
    )
    controller.hotkey_service = hotkey_service.HotkeyService(
        controller.macro_model,
        lambda: int(controller.view.window().winId()),
    )
    return cast(HomeController, controller)


class FakeSignal:
    def __init__(self) -> None:
        self.connected = []

    def connect(self, callback) -> None:
        self.connected.append(callback)


class FakeShortcut:
    def __init__(self, key_sequence, parent) -> None:
        self.key_sequence = key_sequence
        self.parent = parent
        self.activated = FakeSignal()
        self.enabled_values: list[bool] = []

    def setEnabled(self, value: bool) -> None:
        self.enabled_values.append(value)


def test_init_wires_actions_shortcuts_and_initial_state(monkeypatch) -> None:
    fake_config = FakeConfigModel()
    controller_view = FakeView()
    controller_view.center_panel.step_list.itemSelectionChanged = FakeSignal()
    model = FakeMacroModel()
    shortcuts = []

    def make_shortcut(key_sequence, parent) -> FakeShortcut:
        shortcut = FakeShortcut(key_sequence, parent)
        shortcuts.append(shortcut)
        return shortcut

    register_calls: list[tuple] = []

    def fake_register_hotkey(hwnd: int, hid: int, mods: int, vk: int) -> None:
        register_calls.append((hwnd, hid, mods, vk))

    hotkey_config = AppConfig()
    hotkey_config.general.pause_hotkey = ""
    monkeypatch.setattr(home_controller, "config_model", fake_config)
    monkeypatch.setattr(hotkey_service.config_model, "config", hotkey_config)
    monkeypatch.setattr(home_controller, "QShortcut", make_shortcut)
    monkeypatch.setattr(hotkey_service.win32gui, "RegisterHotKey", fake_register_hotkey)
    monkeypatch.setattr(hotkey_service.win32gui, "UnregisterHotKey", lambda hwnd, hid: None)

    controller = HomeController(cast(Any, controller_view), cast(MacroModel, model))

    assert register_calls == []

    assert controller.view is controller_view
    assert controller.macro_model is model
    assert controller.selected_macro_id == ""
    assert controller.actions["run"] == controller.run_current_macro
    assert controller.actions["settings"] == controller.open_settings
    assert controller.actions["macro_explorer"] == controller.open_macro_explorer
    assert len(shortcuts) == 12
    assert len(controller.editing_shortcuts) == 12
    assert controller_view.toolbar.undo_button.enabled is False
    assert controller_view.toolbar.redo_button.enabled is False
    assert controller_view.center_panel.step_tree_items == []


def test_handle_number_area_selected_saves_client_relative_area(monkeypatch) -> None:
    controller = make_controller()
    step = {
        "type": "wait_number",
        "x": 0,
        "y": 0,
        "width": 1,
        "height": 1,
        "operator": "≥",
        "value": 999,
    }
    macro = Macro(meta=MacroMeta(id="macro", target_window="Game"))
    controller.current_macro = macro
    controller.current_runner = cast(Any, FakeRunner())
    controller.selected_macro_id = "macro"
    controller.selected_step = step
    controller.step_tree = StepTree([step])
    controller.sync_runner_macro_from_current = lambda: None
    target_display = home_controller.display.DisplayTarget(
        screen=cast(Any, object()),
        physical_rect=home_controller.window.Rect(1000, 500, 1920, 1080),
    )

    class TargetWindow:
        _hWnd = 123

    monkeypatch.setattr(home_controller.window, "find_target_window", lambda title="": TargetWindow())
    monkeypatch.setattr(
        home_controller.window,
        "client_rect",
        lambda found_window: home_controller.window.Rect(900, 450, 1280, 720),
    )

    controller.handle_number_area_selected(120, 80, 200, 40, 1920, 1080, target_display)

    assert step["x"] == 220
    assert step["y"] == 130
    assert step["width"] == 200
    assert step["height"] == 40
    assert step["relative"] is True
    assert step["capture_width"] == 1280
    assert step["capture_height"] == 720
    assert cast(Any, controller.macro_model).saved[-1].steps[0].width == 200


def test_handle_shortcut_ignores_action_while_hotkey_input_focused(monkeypatch, qtbot) -> None:
    controller = make_controller()
    edit = HotkeyEdit()
    qtbot.addWidget(edit)
    calls = []
    monkeypatch.setattr(home_controller.QApplication, "focusWidget", lambda: edit)

    controller.handle_shortcut(lambda: calls.append("paste"))

    assert calls == []


def test_handle_shortcut_runs_action_when_hotkey_input_not_focused(monkeypatch) -> None:
    controller = make_controller()
    calls = []
    monkeypatch.setattr(home_controller.QApplication, "focusWidget", lambda: None)

    controller.handle_shortcut(lambda: calls.append("paste"))

    assert calls == ["paste"]


def test_set_editing_locked_disables_editing_controls() -> None:
    controller = make_controller()
    shortcuts = [FakeShortcut("ctrl+z", controller.view), FakeShortcut("delete", controller.view)]
    cast(Any, controller).editing_shortcuts = shortcuts
    view = cast(Any, controller.view)

    controller.set_editing_locked(True)

    assert controller.editing_locked is True
    assert [shortcut.enabled_values for shortcut in shortcuts] == [[False], [False]]
    assert view.toolbar.add_button.disabled is True
    assert view.toolbar.delete_button.disabled is True
    assert view.toolbar.move_up_button.disabled is True
    assert view.toolbar.move_down_button.disabled is True
    assert view.toolbar.undo_button.disabled is True
    assert view.toolbar.redo_button.disabled is True
    assert view.left_panel.macro_list.disabled is True
    assert view.left_panel.new_macro_button.disabled is True
    assert view.center_panel.step_list.disabled is True
    assert view.right_panel.disabled is True
    assert view.toolbar.file_menu_button.disabled is True
    assert view.toolbar.edit_menu_button.disabled is True

    controller.set_editing_locked(False)

    assert controller.editing_locked is False
    assert [shortcut.enabled_values for shortcut in shortcuts] == [[False, True], [False, True]]
    assert view.toolbar.add_button.disabled is False
    assert view.toolbar.delete_button.disabled is False
    assert view.toolbar.move_up_button.disabled is False
    assert view.toolbar.move_down_button.disabled is False
    assert view.toolbar.undo_button.disabled is False
    assert view.toolbar.redo_button.disabled is False
    assert view.left_panel.macro_list.disabled is False
    assert view.left_panel.new_macro_button.disabled is False
    assert view.center_panel.step_list.disabled is False
    assert view.right_panel.disabled is False
    assert view.toolbar.file_menu_button.disabled is False
    assert view.toolbar.edit_menu_button.disabled is False


def test_start_macro_recording_requires_current_macro() -> None:
    controller = make_controller()

    controller.start_macro_recording()

    assert cast(Any, controller.view).statuses == ["Select a macro first"]


def test_start_macro_recording_starts_recorder_and_overlay(monkeypatch) -> None:
    fake_config = FakeConfigModel()
    fake_config.config.general.overlay_position = (77, 88)
    recorder = FakeRecorder()
    controller = make_controller()
    controller.current_macro = Macro(meta=MacroMeta(id="macro", label="Macro"))
    controller.current_runner = cast(Any, FakeRunner())
    controller.step_tree = StepTree([])
    monkeypatch.setattr(home_controller, "config_model", fake_config)
    monkeypatch.setattr(home_controller, "MacroRecorder", lambda target_rect: recorder)
    monkeypatch.setattr(home_controller, "RecordingOverlay", FakeRecordingOverlay)

    controller.start_macro_recording()

    assert recorder.start_calls == 1
    assert controller.current_recorder is recorder
    assert cast(Any, controller.recording_overlay).started is True
    assert cast(Any, controller.recording_overlay).positions == [(77, 88)]
    assert cast(Any, controller.view).toolbar.run_button.disabled is True
    assert cast(Any, controller.view).statuses[-1] == "Recording macro: Macro"


def test_stop_macro_recording_inserts_steps_after_selected_step() -> None:
    first_step = {"type": "key", "key": "a"}
    macro = Macro.from_dict({"meta": {"name": "macro"}, "steps": [first_step]})
    runner = FakeRunner()
    runner.macro = macro.to_dict()
    model = FakeMacroModel(macros={"macro": macro})
    controller = make_controller()
    controller.macro_model = cast(MacroModel, model)
    controller.current_macro = macro
    controller.current_runner = cast(Any, runner)
    controller.selected_macro_id = "macro"
    controller.step_tree = StepTree([{"type": "key", "key": "a"}])
    controller.selected_step = controller.step_tree.root_nodes[0].step
    recorder = FakeRecorder([{"type": "key", "key": "b", "hold_ms": 80}])
    recorder.start()
    controller.current_recorder = cast(Any, recorder)
    controller.recording_overlay = cast(Any, FakeRecordingOverlay(lambda: (0, 0), controller.view))

    controller.stop_macro_recording()

    assert [step.to_dict().get("key") for step in macro.steps] == ["a", "b"]
    assert model.saved[-1] is macro
    assert controller.selected_step == {"type": "key", "key": "b", "hold_ms": 80}
    assert cast(Any, controller.view).statuses[-1] == "Recorded 1 steps"


def test_stop_macro_recording_inserts_steps_into_selected_branch() -> None:
    macro = Macro.from_dict({"meta": {"name": "macro"}, "steps": [{"type": "if_image", "template": "one"}]})
    runner = FakeRunner()
    runner.macro = macro.to_dict()
    controller = make_controller()
    controller.current_macro = macro
    controller.current_runner = cast(Any, runner)
    controller.selected_macro_id = "macro"
    controller.step_tree = StepTree([{"type": "if_image", "template": "one", "then": [], "else": []}])
    controller.selected_branch_parent = controller.step_tree.root_nodes[0].step
    controller.selected_branch_key = "then"
    recorder = FakeRecorder([{"type": "delay", "ms": 100}])
    recorder.start()
    controller.current_recorder = cast(Any, recorder)

    controller.stop_macro_recording()

    assert macro.to_dict()["steps"][0]["then"][0]["ms"] == 100
    assert controller.selected_step == {"type": "delay", "ms": 100}


def test_cancel_macro_recording_does_not_save() -> None:
    recorder = FakeRecorder([{"type": "key", "key": "a"}])
    recorder.start()
    model = FakeMacroModel()
    controller = make_controller()
    controller.macro_model = cast(MacroModel, model)
    controller.current_recorder = cast(Any, recorder)
    controller.recording_overlay = cast(Any, FakeRecordingOverlay(lambda: (0, 0), controller.view))

    controller.cancel_macro_recording()

    assert recorder.cancel_calls == 1
    assert model.saved == []
    assert cast(Any, controller.view).statuses[-1] == "Recording cancelled"


def test_toggle_macro_recording_pause_toggles_recorder() -> None:
    recorder = FakeRecorder()
    recorder.start()
    controller = make_controller()
    controller.current_recorder = cast(Any, recorder)
    controller.recording_overlay = cast(Any, FakeRecordingOverlay(lambda: (0, 0), controller.view))

    controller.toggle_macro_recording_pause()
    controller.toggle_macro_recording_pause()

    assert recorder.pause_calls == 1
    assert recorder.resume_calls == 1
    assert cast(Any, controller.recording_overlay).paused_values == [True, False]


def test_sort_macro_items_uses_configured_order_then_label(monkeypatch) -> None:
    fake_config = FakeConfigModel()
    fake_config.config.general.macro_order = ["beta"]
    monkeypatch.setattr(home_controller, "config_model", fake_config)
    controller = make_controller()
    items = [
        MacroSummary(id="alpha", label="Zoo", path="alpha.json"),
        MacroSummary(id="beta", label="Beta", path="beta.json"),
        MacroSummary(id="gamma", label="apple", path="gamma.json"),
    ]

    sorted_items = controller.sort_macro_items(items)

    assert [item.id for item in sorted_items] == ["beta", "gamma", "alpha"]


def test_parse_hotkey_handles_modifiers_and_named_key() -> None:
    controller = make_controller()

    assert controller.hotkey_service.parse_hotkey("CTRL+Alt+enter") == (0x0002 | 0x0001, 0x0D)
    assert controller.hotkey_service.parse_hotkey("shift+f1") == (0x0004, 0x70)


def test_key_to_vk_uses_vk_key_scan_for_single_character(monkeypatch) -> None:
    monkeypatch.setattr(hotkey_service.win32api, "VkKeyScan", lambda key: ord(key) + 0x100)
    controller = make_controller()

    assert controller.hotkey_service.key_to_vk("a") == ord("a")


def test_register_hotkeys_unregisters_previous_and_skips_invalid(monkeypatch) -> None:
    register_calls: list[tuple[int, int, int, int]] = []
    unregister_calls: list[tuple[int, int]] = []

    def fake_register(hwnd: int, hid: int, mods: int, vk: int) -> None:
        register_calls.append((hwnd, hid, mods, vk))

    def fake_unregister(hwnd: int, hid: int) -> None:
        unregister_calls.append((hwnd, hid))

    hotkey_config = AppConfig()
    hotkey_config.general.pause_hotkey = ""
    monkeypatch.setattr(hotkey_service.win32gui, "RegisterHotKey", fake_register)
    monkeypatch.setattr(hotkey_service.win32gui, "UnregisterHotKey", fake_unregister)
    monkeypatch.setattr(hotkey_service.config_model, "config", hotkey_config)
    macros = {
        "enabled": Macro(meta=MacroMeta(id="enabled", label="Enabled", hotkey="ctrl+f1", enabled=True)),
        "disabled": Macro(meta=MacroMeta(id="disabled", label="Disabled", hotkey="ctrl+f2", enabled=False)),
        "invalid": Macro(meta=MacroMeta(id="invalid", label="Invalid", hotkey="ctrl+unknown", enabled=True)),
        "empty": Macro(meta=MacroMeta(id="empty", label="Empty", hotkey="", enabled=True)),
    }
    model = FakeMacroModel(macros=macros)
    controller = make_controller()
    controller.macro_model = cast(MacroModel, model)
    controller.hotkey_service.hotkey_ids = [0xBF99]
    controller.hotkey_service.hotkey_map = {0xBF99: "old"}

    controller.register_hotkeys()

    assert unregister_calls == [(99, 0xBF99)]
    assert register_calls == [(99, 0xBF02, 0x0002, 0x70)]
    assert controller.hotkey_service.hotkey_ids == [0xBF02]
    assert controller.hotkey_service.hotkey_map == {0xBF02: "enabled"}


def test_register_hotkeys_does_not_store_failed_registration(monkeypatch) -> None:
    register_calls: list[tuple[int, int, int, int]] = []

    def fake_register(hwnd: int, hid: int, mods: int, vk: int) -> None:
        register_calls.append((hwnd, hid, mods, vk))
        raise Exception("failed")

    hotkey_config = AppConfig()
    hotkey_config.general.pause_hotkey = ""
    monkeypatch.setattr(hotkey_service.win32gui, "RegisterHotKey", fake_register)
    monkeypatch.setattr(hotkey_service.win32gui, "UnregisterHotKey", lambda hwnd, hid: None)
    monkeypatch.setattr(hotkey_service.config_model, "config", hotkey_config)
    model = FakeMacroModel(macros={"macro": Macro(meta=MacroMeta(id="macro", label="Macro", hotkey="ctrl+f1"))})
    controller = make_controller()
    controller.macro_model = cast(MacroModel, model)
    controller.hotkey_service.hotkey_ids = []
    controller.hotkey_service.hotkey_map = {}

    controller.register_hotkeys()

    assert register_calls == [(99, 0xBF00, 0x0002, 0x70)]
    assert controller.hotkey_service.hotkey_ids == []
    assert controller.hotkey_service.hotkey_map == {}


def test_handle_hotkey_triggered_selects_macro_and_loads_steps(monkeypatch, tmp_path: Path) -> None:
    macro = Macro.from_dict(
        {
            "meta": {"name": "target", "label": "Target", "enabled": True},
            "steps": [{"type": "key", "key": "enter"}],
        }
    )
    model = FakeMacroModel(macros={"target": macro})
    controller = make_controller()
    controller.macro_model = cast(MacroModel, model)
    controller.hotkey_service.hotkey_map = {0xBF00: "target"}
    cast(Any, controller.view).left_panel = FakeLeftPanel(["other", "target"])
    show_loaded_calls = []
    monkeypatch.setattr(home_controller, "macro_path", lambda macro_id: tmp_path / f"{macro_id}.json")
    monkeypatch.setattr(home_controller.MacroRunner, "start", lambda self: show_loaded_calls.append("start"))

    controller.handle_hotkey_triggered(0xBF00)

    macro_list = cast(Any, controller.view).left_panel.macro_list
    assert controller.selected_macro_id == "target"
    assert controller.current_macro is macro
    assert controller.step_tree is not None
    assert controller.step_tree.steps[0]["type"] == "key"
    assert controller.step_tree.steps[0]["key"] == "enter"
    assert macro_list.current_item is macro_list.items[1]
    assert macro_list.blocked_states == [True, False]
    assert show_loaded_calls == ["start"]


def test_handle_macro_selected_reload_same_macro_refreshes_current_state() -> None:
    macro = Macro(meta=MacroMeta(id="alpha"))
    controller = make_controller()
    controller.selected_macro_id = "alpha"
    controller.current_macro = macro
    calls = []
    controller.refresh_step_tree = lambda: calls.append("refresh_step_tree")
    controller.show_macro_properties = lambda macro: calls.append(("show_macro_properties", macro))
    controller.update_step_action_state = lambda: calls.append("update_step_action_state")

    controller.handle_macro_selected("alpha")

    assert controller.selected_step is None
    assert controller.selected_branch_parent is None
    assert controller.selected_branch_key == ""
    assert calls == ["refresh_step_tree", ("show_macro_properties", macro), "update_step_action_state"]


def test_handle_macro_selected_loads_new_macro() -> None:
    controller = make_controller()
    calls = []
    controller.load_selected_macro = lambda macro_id: calls.append(macro_id)

    controller.handle_macro_selected("beta")

    assert controller.selected_macro_id == "beta"
    assert calls == ["beta"]


def test_refresh_macro_list_loads_first_macro_and_updates_left_panel(monkeypatch) -> None:
    macro = Macro(meta=MacroMeta(id="beta", label="Beta"))
    model = FakeMacroModel(macros={"beta": macro})
    controller = make_controller()
    controller.macro_model = cast(MacroModel, model)
    load_calls = []
    hotkey_calls = []
    controller.load_selected_macro = lambda macro_id: load_calls.append(macro_id)
    controller.register_hotkeys = lambda: hotkey_calls.append("register")

    controller.refresh_macro_list()

    left_panel = cast(Any, controller.view).left_panel
    assert controller.selected_macro_id == "beta"
    assert left_panel.list_items == [("beta", "BETA")]
    assert left_panel.selected_macro_id == "beta"
    assert load_calls == ["beta"]
    assert hotkey_calls == ["register"]


def test_refresh_macro_list_shows_empty_state_when_no_macros() -> None:
    controller = make_controller()
    calls = []
    controller.show_empty_macro_state = lambda: calls.append("empty")
    controller.register_hotkeys = lambda: calls.append("hotkeys")

    controller.refresh_macro_list()

    assert calls == ["empty", "hotkeys"]


def test_handle_step_and_branch_selection_route_to_view_state(monkeypatch) -> None:
    controller = make_controller()
    step = {"type": "key"}
    calls = []
    monkeypatch.setattr(home_controller.QTimer, "singleShot", lambda delay, callback: callback())
    controller.show_step_selection = lambda step: calls.append(("show", step))
    controller.update_step_action_state = lambda: calls.append("update")

    controller.handle_step_selected(step)
    controller.handle_branch_selected(step, "then")

    assert controller.selected_step is None
    assert controller.selected_branch_parent is step
    assert controller.selected_branch_key == "then"
    assert calls == [("show", step), "update", ("show", None), "update"]


def test_handle_action_ignores_locked_editing_action() -> None:
    controller = make_controller()
    calls = []
    controller.editing_locked = True
    controller.actions = {"delete_step": lambda: calls.append("delete"), "settings": lambda: calls.append("settings")}

    controller.handle_action("delete_step")
    controller.handle_action("settings")

    assert calls == []


def test_handle_action_runs_known_action_when_unlocked() -> None:
    controller = make_controller()
    calls = []
    controller.actions = {"delete_step": lambda: calls.append("delete")}

    controller.handle_action("delete_step")
    controller.handle_action("missing")

    assert calls == ["delete"]


def test_show_empty_and_load_error_clear_current_state() -> None:
    controller = make_controller()
    controller.current_macro = Macro(meta=MacroMeta(id="old"))
    controller.current_runner = cast(Any, FakeRunner())
    controller.step_tree = StepTree([{"type": "key"}])
    controller.selected_step = {"type": "key"}
    refresh_calls = []
    controller.refresh_step_tree = lambda: refresh_calls.append("refresh")

    controller.show_empty_macro_state()

    assert controller.current_macro is None
    assert controller.current_runner is None
    assert controller.step_tree is None
    assert cast(Any, controller.view).right_panel.macro_properties is None

    controller.current_macro = Macro(meta=MacroMeta(id="old"))
    controller.show_macro_load_error("missing")

    assert controller.current_macro is None
    assert cast(Any, controller.view).statuses == ["Failed to load macro: missing"]
    assert refresh_calls == ["refresh", "refresh"]


def test_show_loaded_macro_sets_view_state() -> None:
    macro = Macro(meta=MacroMeta(id="macro"))
    runner = FakeRunner()
    step_tree = StepTree([{"type": "delay", "ms": 100}])
    controller = make_controller()

    controller.show_loaded_macro(macro, cast(Any, runner), step_tree)

    assert controller.current_macro is macro
    assert controller.current_runner is runner
    assert controller.step_tree is step_tree
    assert cast(Any, controller.view).right_panel.macro_properties is macro
    assert cast(Any, controller.view).center_panel.step_tree_items[0]["label"] == "Wait 100 ms"


def test_push_undo_stores_snapshot_and_clears_redo() -> None:
    controller = make_controller()
    runner = FakeRunner()
    runner.macro = {"steps": [{"type": "key", "key": "a"}]}
    controller.current_runner = cast(Any, runner)
    controller.selected_macro_id = "macro"
    controller.redo_stack.append({"old": True})
    controller.redo_selection_index_stack.append(1)

    controller.push_undo(0)
    runner.macro["steps"][0]["key"] = "b"

    assert controller.undo_stack == [{"steps": [{"type": "key", "key": "a"}]}]
    assert controller.undo_selection_index_stack == [0]
    assert controller.redo_stack == []
    assert controller.redo_selection_index_stack == []


def test_push_undo_caps_history_at_fifty_entries() -> None:
    controller = make_controller()
    runner = FakeRunner()
    controller.current_runner = cast(Any, runner)
    controller.selected_macro_id = "macro"

    for index in range(51):
        runner.macro = {"index": index}
        controller.push_undo(index)

    assert len(controller.undo_stack) == 50
    assert controller.undo_stack[0] == {"index": 1}
    assert controller.undo_selection_index_stack[0] == 1


def test_undo_and_redo_restore_saved_state() -> None:
    controller = make_controller()
    runner = FakeRunner()
    runner.macro = {"steps": [{"type": "key", "key": "current"}]}
    controller.current_runner = cast(Any, runner)
    controller.selected_macro_id = "macro"
    controller.undo_stack.append({"steps": [{"type": "key", "key": "undo"}]})
    controller.undo_selection_index_stack.append(0)
    restored = []

    def restore_macro_state(macro_dict, selection_index=None) -> None:
        restored.append((macro_dict, selection_index))
        runner.macro = macro_dict

    controller.restore_macro_state = restore_macro_state
    controller.selected_step_flat_index = lambda: 2

    controller.undo()
    controller.redo()

    assert restored == [
        ({"steps": [{"type": "key", "key": "undo"}]}, 0),
        ({"steps": [{"type": "key", "key": "current"}]}, 2),
    ]
    assert cast(Any, controller.view).statuses == [
        "Undo: Changed Press undo to Press current",
        "Redo: Changed Press undo to Press current",
    ]


def test_undo_and_redo_report_added_step_in_status_bar() -> None:
    controller = make_controller()
    runner = FakeRunner()
    runner.macro = {"steps": [{"type": "delay", "ms": 100}]}
    controller.current_runner = cast(Any, runner)
    controller.selected_macro_id = "macro"
    controller.undo_stack.append({"steps": []})
    controller.undo_selection_index_stack.append(None)

    def restore_macro_state(macro_dict, selection_index=None) -> None:
        runner.macro = macro_dict

    controller.restore_macro_state = restore_macro_state
    controller.selected_step_flat_index = lambda: None

    controller.undo()
    controller.redo()

    assert cast(Any, controller.view).statuses == [
        "Undo: Added Wait 100 ms",
        "Redo: Added Wait 100 ms",
    ]


def test_undo_reports_deleted_step_in_status_bar() -> None:
    controller = make_controller()
    runner = FakeRunner()
    runner.macro = {"steps": []}
    controller.current_runner = cast(Any, runner)
    controller.selected_macro_id = "macro"
    controller.undo_stack.append({"steps": [{"type": "key", "key": "enter"}]})
    controller.undo_selection_index_stack.append(None)
    controller.restore_macro_state = lambda macro_dict, selection_index=None: None

    controller.undo()

    assert cast(Any, controller.view).statuses == ["Undo: Deleted Press enter"]


def test_restore_macro_state_deletes_templates_missing_from_snapshot(tmp_path: Path, monkeypatch) -> None:
    current_macro = Macro.from_dict(
        {
            "meta": {"id": "macro"},
            "templates": {"old": {"label": "Old"}, "new": {"label": "New"}},
            "steps": [{"type": "if_any_image", "templates": ["old", "new"], "branches": {}}],
        }
    )
    restored_state = {
        "meta": {"id": "macro"},
        "templates": {"old": {"label": "Old"}},
        "steps": [{"type": "if_any_image", "templates": ["old"], "branches": {}}],
    }
    old_file = tmp_path / "templates" / "macro" / "old.png"
    new_file = tmp_path / "templates" / "macro" / "new.png"
    old_file.parent.mkdir(parents=True)
    old_file.write_bytes(b"old")
    new_file.write_bytes(b"new")
    controller = make_controller()
    controller.current_macro = current_macro
    controller.current_runner = cast(Any, FakeRunner())
    controller.step_tree = StepTree(current_macro.to_dict()["steps"])

    monkeypatch.setattr(
        home_controller,
        "template_path",
        lambda macro_id, template_id: tmp_path / "templates" / macro_id / f"{template_id}.png",
    )

    controller.restore_macro_state(restored_state)

    assert old_file.exists()
    assert not new_file.exists()
    assert set(controller.current_macro.templates) == {"old"}


def test_undo_capture_keeps_other_captured_if_any_template(tmp_path: Path, monkeypatch) -> None:
    template_root = tmp_path / "templates" / "macro"
    first_file = template_root / "image1.png"
    second_file = template_root / "image2.png"
    template_root.mkdir(parents=True)
    macro = Macro.from_dict(
        {
            "meta": {"id": "macro"},
            "templates": {"slot1": {"label": "Slot 1"}, "slot2": {"label": "Slot 2"}},
            "steps": [{"type": "if_any_image", "templates": ["slot1", "slot2"], "branches": {}}],
        }
    )
    model = FakeMacroModel(macros={"macro": macro})
    runner = FakeRunner()
    runner.macro = macro.to_dict()
    controller = make_controller()
    controller.current_macro = macro
    controller.current_runner = cast(Any, runner)
    controller.macro_model = cast(MacroModel, model)
    controller.selected_macro_id = "macro"
    selected_step = cast(dict[str, Any], macro.to_dict()["steps"][0])
    controller.selected_step = selected_step
    controller.step_tree = StepTree([selected_step])

    monkeypatch.setattr(
        home_controller,
        "template_path",
        lambda macro_id, template_id: tmp_path / "templates" / macro_id / f"{template_id}.png",
    )

    first_file.write_bytes(b"first")
    controller.handle_region_captured("slot1", "image1", 320, 180)
    controller.selected_step = controller.step_tree.steps[0]

    second_file.write_bytes(b"second")
    controller.handle_region_captured("slot2", "image2", 320, 180)

    controller.undo()

    assert first_file.read_bytes() == b"first"
    assert not second_file.exists()
    assert set(controller.current_macro.templates) == {"image1", "slot2"}
    assert controller.step_tree.steps[0]["templates"] == ["image1", "slot2"]


def test_redo_capture_restores_template_file_from_snapshot(tmp_path: Path, monkeypatch) -> None:
    template_root = tmp_path / "templates" / "macro"
    template_file = template_root / "captured.png"
    template_root.mkdir(parents=True)
    macro = Macro.from_dict(
        {
            "meta": {"id": "macro"},
            "templates": {"slot": {"label": "Slot"}},
            "steps": [{"type": "if_any_image", "templates": ["slot"], "branches": {}}],
        }
    )
    model = FakeMacroModel(macros={"macro": macro})
    runner = FakeRunner()
    runner.macro = macro.to_dict()
    controller = make_controller()
    controller.current_macro = macro
    controller.current_runner = cast(Any, runner)
    controller.macro_model = cast(MacroModel, model)
    controller.selected_macro_id = "macro"
    selected_step = cast(dict[str, Any], macro.to_dict()["steps"][0])
    controller.selected_step = selected_step
    controller.step_tree = StepTree([selected_step])

    monkeypatch.setattr(
        home_controller,
        "template_path",
        lambda macro_id, template_id: tmp_path / "templates" / macro_id / f"{template_id}.png",
    )

    template_file.write_bytes(b"captured")
    controller.handle_region_captured("slot", "captured", 320, 180)

    controller.undo()
    assert not template_file.exists()

    controller.redo()

    assert template_file.read_bytes() == b"captured"
    assert set(controller.current_macro.templates) == {"captured"}


def test_select_after_undo_redo_handles_empty_and_selection_index() -> None:
    controller = make_controller()
    macro = Macro.from_dict({"meta": {"name": "macro"}, "steps": []})
    controller.current_macro = macro
    controller.step_tree = StepTree([])

    controller.select_after_undo_redo([], [])

    assert controller.selected_step is None
    assert cast(Any, controller.view).right_panel.macro_properties is macro

    controller.step_tree = StepTree([{"type": "key", "key": "a"}])
    calls = []
    controller.refresh_step_tree = lambda: calls.append("refresh")
    controller.show_step_selection = lambda step: calls.append(("show", step))

    controller.select_after_undo_redo([], [], selection_index=0)

    assert controller.selected_step == {"type": "key", "key": "a"}
    assert calls == ["refresh", ("show", controller.selected_step)]


def test_select_after_undo_redo_selects_changed_or_previous_step() -> None:
    controller = make_controller()
    controller.step_tree = StepTree([{"type": "key", "key": "a"}, {"type": "delay", "ms": 1}])
    calls = []
    controller.refresh_step_tree = lambda: calls.append("refresh")
    controller.show_step_selection = lambda step: calls.append(("show", step))

    controller.select_after_undo_redo(
        [Macro.from_dict({"meta": {}, "steps": [{"type": "key", "key": "z"}]}).steps[0]], []
    )

    assert controller.selected_step == {"type": "key", "key": "a"}
    assert calls[-1] == ("show", controller.selected_step)


def test_run_current_macro_starts_and_stops_runner(qtbot) -> None:
    controller = make_controller()
    runner = FakeRunner(running=False)
    controller.current_runner = cast(Any, runner)

    with qtbot.waitSignal(home_controller.event_bus.macro_running_changed, timeout=100) as started:
        controller.run_current_macro()

    runner.running = True
    with qtbot.waitSignal(home_controller.event_bus.macro_running_changed, timeout=100) as stopped:
        controller.run_current_macro()

    assert started.args == [True]
    assert stopped.args == [False]
    assert runner.start_calls == 1
    assert runner.stop_calls == 1
    assert cast(Any, controller.view).statuses == ["Running macro: Runner", "Stopping macro: Runner"]


def test_toggle_current_macro_pause_pauses_and_resumes_running_runner() -> None:
    controller = make_controller()
    runner = FakeRunner(running=True)
    controller.current_runner = cast(Any, runner)

    controller.toggle_current_macro_pause()
    controller.toggle_current_macro_pause()

    assert runner.pause_calls == 1
    assert runner.resume_calls == 1


def test_toggle_current_macro_pause_ignores_stopped_runner() -> None:
    controller = make_controller()
    runner = FakeRunner(running=False)
    controller.current_runner = cast(Any, runner)

    controller.toggle_current_macro_pause()

    assert runner.pause_calls == 0
    assert runner.resume_calls == 0


def test_handle_macro_running_changed_reports_terminal_status() -> None:
    controller = make_controller()
    calls = []
    controller.set_editing_locked = lambda locked: calls.append(("locked", locked))
    controller.current_runner = cast(Any, FakeRunner(status=Status(last_reason="done")))

    controller.handle_macro_running_changed(False)

    assert calls == [("locked", False)]
    assert cast(Any, controller.view).statuses == ["Done: Runner (00:00)"]


def test_handle_macro_paused_changed_updates_status_text() -> None:
    controller = make_controller()
    runner = FakeRunner(running=True)
    controller.current_runner = cast(Any, runner)

    controller.handle_macro_paused_changed(True)
    controller.handle_macro_paused_changed(False)

    assert cast(Any, controller.view).statuses == ["Paused", "Running macro: Runner"]


def test_translate_status_message_formats_known_failures() -> None:
    controller = make_controller()

    assert controller.translate_status_message("missing_templates: A, B") == "Missing templates: A, B"
    assert controller.translate_status_message("Error: boom") == "Error: boom"
    assert controller.translate_status_message("macro_format: bad step") == "Macro format error: bad step"
    assert controller.translate_status_message("wait_timeout: Button") == "Wait timeout: Button"
    assert controller.translate_status_message("wait_any_timeout: A, B") == "Wait any timeout: A, B"
    assert controller.translate_status_message("mouse_click: empty") == "Mouse click: empty template"
    assert controller.translate_status_message("mouse_click_timeout: Button") == "Mouse click timeout: Button"
    assert controller.translate_status_message("mouse_move: empty") == "Mouse move: empty template"
    assert controller.translate_status_message("mouse_move_timeout: Button") == "Mouse move timeout: Button"
    assert controller.translate_status_message("window_not_found") == "Window not found"
    assert (
        controller.translate_status_message("elevation_mismatch")
        == "Elevation mismatch, do not run target app as admin"
    )
    assert controller.translate_status_message("other: value") == "other: value"


def test_parse_step_property_converts_known_types() -> None:
    controller = make_controller()

    assert controller.parse_step_property("skip", "true") is True
    assert controller.parse_step_property("ms", "150") == 150
    assert controller.parse_step_property("interval_ms", "25") == 25
    assert controller.parse_step_property("relative", "false") is False
    assert controller.parse_step_property("clicks", "-3") == -3
    assert controller.parse_step_property("x", "10") == 10
    assert controller.parse_step_property("y", "20") == 20
    assert controller.parse_step_property("threshold", "87") == 0.87
    assert controller.parse_step_property("key", "enter") == "enter"


def test_handle_macro_meta_changed_saves_and_registers_hotkeys() -> None:
    macro = Macro(meta=MacroMeta(id="macro", enabled=False))
    model = FakeMacroModel(macros={"macro": macro})
    controller = make_controller()
    controller.current_macro = macro
    controller.macro_model = cast(MacroModel, model)
    calls = []
    controller.register_hotkeys = lambda: calls.append("register")

    controller.handle_macro_meta_changed("enabled", "True")
    controller.handle_macro_meta_changed("gaming_mode", "False")
    controller.handle_macro_meta_changed("background_input", "False")
    controller.handle_macro_meta_changed("keep_target_focused", "True")
    controller.handle_macro_meta_changed("label", "Renamed")

    assert macro.meta.enabled is True
    assert macro.gaming_mode is False
    assert macro.background_input is False
    assert macro.keep_target_focused is True
    assert macro.meta.label == "Renamed"
    assert model.saved == [macro, macro, macro, macro, macro]
    assert calls == ["register"]


def test_handle_step_property_changed_updates_repeat_children() -> None:
    repeat_step = {"type": "repeat", "skip": False, "steps": [{"type": "key", "skip": False}]}
    macro = Macro.from_dict({"meta": {"name": "macro"}, "steps": [repeat_step]})
    model = FakeMacroModel(macros={"macro": macro})
    controller = make_controller()
    controller.current_macro = macro
    controller.current_runner = cast(Any, FakeRunner())
    controller.macro_model = cast(MacroModel, model)
    controller.step_tree = StepTree([repeat_step])
    controller.selected_step = controller.step_tree.steps[0]
    controller.refresh_selected_step = lambda: None

    controller.handle_step_property_changed("skip", "true")

    assert controller.step_tree.steps[0]["skip"] is True
    assert controller.step_tree.steps[0]["steps"][0]["skip"] is True
    assert model.saved[-1].steps[0].skip is True


def test_add_step_reports_missing_macro_or_unknown_type() -> None:
    controller = make_controller()

    controller.add_step("key")
    controller.step_tree = StepTree([])
    controller.add_step("unknown")

    assert cast(Any, controller.view).statuses == ["Select a macro first", "Unknown step type"]


def test_add_step_appends_new_step_and_saves() -> None:
    macro = Macro(meta=MacroMeta(id="macro"))
    model = FakeMacroModel(macros={"macro": macro})
    controller = make_controller()
    controller.current_macro = macro
    controller.current_runner = cast(Any, FakeRunner())
    controller.macro_model = cast(MacroModel, model)
    controller.step_tree = StepTree([])

    controller.add_step("delay")

    assert controller.step_tree.steps == [{"type": "delay", "ms": 500, "skip": False, "note": ""}]
    assert controller.selected_step == controller.step_tree.steps[0]
    assert model.saved[-1].steps[0].type == "delay"


def test_load_selected_macro_shows_error_or_loaded_macro(tmp_path: Path, monkeypatch) -> None:
    macro = Macro.from_dict({"meta": {"name": "macro"}, "steps": [{"type": "key", "key": "enter"}]})
    model = FakeMacroModel(macros={"macro": macro})
    controller = make_controller()
    controller.macro_model = cast(MacroModel, model)
    monkeypatch.setattr(home_controller, "macro_path", lambda macro_id: tmp_path / f"{macro_id}.json")

    controller.load_selected_macro("missing")
    controller.load_selected_macro("macro")

    assert cast(Any, controller.view).statuses == ["Failed to load macro: missing"]
    assert controller.current_macro is macro
    assert controller.current_runner is not None
    assert controller.step_tree is not None


def test_branch_label_uses_template_label_for_if_any_image() -> None:
    controller = make_controller()
    controller.current_macro = Macro(
        meta=MacroMeta(id="macro"),
        templates={"start": TemplateInfo(label="Start Button")},
    )

    label = controller.branch_label("start", {"type": "if_any_image"})

    assert label == "Start Button"


def test_branch_label_falls_back_to_humanized_key() -> None:
    controller = make_controller()

    assert controller.branch_label("custom_branch") == "Custom Branch"


def test_get_template_label_uses_macro_template_metadata() -> None:
    controller = make_controller()
    controller.current_macro = Macro(
        meta=MacroMeta(id="macro"),
        templates={"start": TemplateInfo(label="Start Button")},
    )

    assert controller.get_template_label("start") == "Start Button"
    assert controller.get_template_label("missing") == "missing"


def test_describe_step_formats_core_step_types() -> None:
    controller = make_controller()
    controller.current_macro = Macro(
        meta=MacroMeta(id="macro"),
        templates={"start": TemplateInfo(label="Start Button")},
    )

    assert controller.describe_step({"type": "key", "key": "enter"}) == "Press enter"
    assert controller.describe_step({"type": "delay", "ms": 250}) == "Wait 250 ms"
    assert controller.describe_step({"type": "text_input", "text": "哈囉\nworld"}) == "Type text: 哈囉 world"
    assert controller.describe_step({"type": "text_input", "text": "123456789012345678901"}) == (
        "Type text: 12345678901234567890..."
    )
    assert (
        controller.describe_step({"type": "wait_image", "template": "start", "note": "ready"})
        == "Wait for Start Button (ready)"
    )
    assert controller.describe_step({"type": "repeat", "count": 3}) == "Repeat 3 times"
    assert controller.describe_step({"type": "grid_nav", "rows": 2}) == "Grid navigation (2 rows)"


def test_set_descendant_skip_updates_nested_steps() -> None:
    controller = make_controller()
    steps = [
        {
            "type": "repeat",
            "skip": False,
            "steps": [
                {"type": "key", "key": "enter", "skip": False},
                {"type": "delay", "ms": 100, "skip": False},
            ],
        }
    ]
    controller.step_tree = StepTree(steps)

    controller.set_descendant_skip(steps[0], True)

    assert steps[0]["steps"][0]["skip"] is True
    assert steps[0]["steps"][1]["skip"] is True


def test_is_child_of_skipped_repeat_detects_skipped_ancestor() -> None:
    controller = make_controller()
    child = {"type": "key", "key": "enter"}
    steps = [{"type": "repeat", "skip": True, "steps": [child]}]
    controller.step_tree = StepTree(steps)

    assert controller.is_child_of_skipped_repeat(child) is True
    assert controller.is_child_of_skipped_repeat(steps[0]) is False


def test_step_tree_refs_from_macro_collects_template_ids() -> None:
    controller = make_controller()
    macro = Macro.from_dict(
        {
            "meta": {"name": "macro"},
            "steps": [
                {"type": "wait_image", "template": "one"},
                {"type": "if_any_image", "templates": ["two", "three"], "branches": {}},
            ],
        }
    )

    assert controller.step_tree_refs_from_macro(macro) == {"one", "two", "three"}


def test_add_step_factory_returns_supported_steps() -> None:
    controller = make_controller()

    assert controller.add_step_factory("key") is not None
    assert controller.add_step_factory("text_input") is not None
    assert controller.add_step_factory("missing") is None


def test_handle_macro_rename_saves_new_label(monkeypatch) -> None:
    macro = Macro(meta=MacroMeta(id="alpha", label="Old"))
    model = FakeMacroModel(macros={"alpha": macro})
    controller = make_controller()
    controller.macro_model = cast(MacroModel, model)
    refresh_calls = []
    controller.refresh_macro_list = lambda: refresh_calls.append("refresh")
    monkeypatch.setattr(home_controller, "RenameMacroDialog", lambda parent, current_label: FakeDialog(True, "New"))

    controller.handle_macro_rename("alpha")

    assert macro.meta.label == "New"
    assert model.saved == [macro]
    assert refresh_calls == ["refresh"]
    assert cast(Any, controller.view).statuses == ["Renamed macro: New"]


def test_handle_macro_rename_reports_load_error() -> None:
    controller = make_controller()
    controller.macro_model = cast(MacroModel, FakeMacroModel())

    controller.handle_macro_rename("missing")

    assert cast(Any, controller.view).statuses == ["Failed to load macro: missing"]


def test_handle_macro_delete_removes_template_dir_and_order(tmp_path: Path, monkeypatch) -> None:
    macro = Macro(meta=MacroMeta(id="alpha", label="Alpha"))
    model = FakeMacroModel(macros={"alpha": macro})
    fake_config = FakeConfigModel()
    fake_config.config.general.macro_order = ["alpha", "beta"]
    template_dir = tmp_path / "templates" / "alpha"
    template_dir.mkdir(parents=True)
    controller = make_controller()
    controller.selected_macro_id = "alpha"
    controller.macro_model = cast(MacroModel, model)
    refresh_calls = []
    controller.refresh_macro_list = lambda: refresh_calls.append("refresh")
    monkeypatch.setattr(home_controller, "config_model", fake_config)
    monkeypatch.setattr(home_controller, "templates_dir", lambda macro_id: tmp_path / "templates" / macro_id)
    monkeypatch.setattr(home_controller, "show_confirm_dialog", lambda *args: True)

    controller.handle_macro_delete("alpha")

    assert model.deleted == ["alpha"]
    assert not template_dir.exists()
    assert fake_config.config.general.macro_order == ["beta"]
    assert fake_config.save_calls == 1
    assert controller.selected_macro_id == ""
    assert refresh_calls == ["refresh"]
    assert cast(Any, controller.view).statuses == ["Deleted macro: Alpha"]


def test_handle_macro_delete_stops_when_not_confirmed(monkeypatch) -> None:
    model = FakeMacroModel(macros={"alpha": Macro(meta=MacroMeta(id="alpha"))})
    controller = make_controller()
    controller.macro_model = cast(MacroModel, model)
    monkeypatch.setattr(home_controller, "show_confirm_dialog", lambda *args: False)

    controller.handle_macro_delete("alpha")

    assert model.deleted == []


def test_duplicate_current_macro_copies_templates(tmp_path: Path, monkeypatch) -> None:
    macro = Macro(meta=MacroMeta(id="alpha", label="Alpha"))
    model = FakeMacroModel(macros={"alpha": macro})
    source_dir = tmp_path / "templates" / "alpha"
    source_dir.mkdir(parents=True)
    (source_dir / "button.png").write_bytes(b"png")
    controller = make_controller()
    controller.current_macro = macro
    controller.macro_model = cast(MacroModel, model)
    refresh_calls = []
    controller.refresh_macro_list = lambda: refresh_calls.append("refresh")
    monkeypatch.setattr(home_controller.time, "time", lambda: 200.0)
    monkeypatch.setattr(home_controller, "macro_path", lambda macro_id: tmp_path / "macros" / f"{macro_id}.json")
    monkeypatch.setattr(home_controller, "templates_dir", lambda macro_id: tmp_path / "templates" / macro_id)

    controller.duplicate_current_macro()

    assert model.saved[0].meta.id == "200"
    assert model.saved[0].meta.label == "Alpha Copy"
    assert (tmp_path / "templates" / "200" / "button.png").read_bytes() == b"png"
    assert controller.selected_macro_id == "200"
    assert refresh_calls == ["refresh"]
    assert cast(Any, controller.view).statuses == ["Duplicated macro: Alpha Copy"]


def test_handle_macro_order_changed_saves_visible_order(monkeypatch) -> None:
    fake_config = FakeConfigModel()
    controller = make_controller()

    class FakeItem:
        def __init__(self, macro_id: str) -> None:
            self.macro_id = macro_id

        def data(self, role) -> str:
            assert role == Qt.ItemDataRole.UserRole
            return self.macro_id

    class FakeList:
        def __init__(self) -> None:
            self.items = [FakeItem("beta"), FakeItem("alpha")]

        def count(self) -> int:
            return len(self.items)

        def item(self, index: int):
            return self.items[index]

    class FakeLeftPanel:
        macro_list = FakeList()

    cast(Any, controller.view).left_panel = FakeLeftPanel()
    monkeypatch.setattr(home_controller, "config_model", fake_config)

    controller.handle_macro_order_changed()

    assert fake_config.config.general.macro_order == ["beta", "alpha"]
    assert fake_config.save_calls == 1


def write_macro_zip(path: Path, macro_data: dict, files: dict[str, bytes] | None = None) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("macro.json", json.dumps(macro_data))

        for name, content in (files or {}).items():
            archive.writestr(name, content)


def test_import_macro_saves_archive_and_templates(tmp_path: Path, monkeypatch) -> None:
    archive_path = tmp_path / "macro.zip"
    macro_data = {
        "meta": {"name": "imported", "label": "Imported"},
        "templates": {},
        "steps": [{"type": "wait_image", "template": "button"}],
    }
    write_macro_zip(
        archive_path,
        macro_data,
        {
            "templates/button.png": b"png",
            "templates/button.json": json.dumps({"capture_width": 320, "capture_height": 180}).encode(),
        },
    )
    model = FakeMacroModel()
    fake_config = FakeConfigModel()
    controller = make_controller()
    controller.macro_model = cast(MacroModel, model)
    refresh_calls = []
    controller.refresh_macro_list = lambda: refresh_calls.append("refresh")
    monkeypatch.setattr(home_controller.QFileDialog, "getOpenFileName", lambda *args: (str(archive_path), ""))
    monkeypatch.setattr(macro_import_service.time, "time", lambda: 400.0)
    monkeypatch.setattr(home_controller, "macro_path", lambda macro_id: tmp_path / "macros" / f"{macro_id}.json")
    monkeypatch.setattr(home_controller, "templates_dir", lambda macro_id: tmp_path / "templates" / macro_id)
    monkeypatch.setattr(
        home_controller,
        "template_path",
        lambda macro_id, template_id: tmp_path / "templates" / macro_id / f"{template_id}.png",
    )
    monkeypatch.setattr(macro_import_service, "macro_path", lambda macro_id: tmp_path / "macros" / f"{macro_id}.json")
    monkeypatch.setattr(macro_import_service, "templates_dir", lambda macro_id: tmp_path / "templates" / macro_id)
    monkeypatch.setattr(
        macro_import_service,
        "template_path",
        lambda macro_id, template_id: tmp_path / "templates" / macro_id / f"{template_id}.png",
    )
    monkeypatch.setattr(home_controller, "config_model", fake_config)

    controller.import_macro()

    assert model.saved[0].meta.id == "400"
    assert model.saved[0].templates["button"].capture_width == 320
    assert (tmp_path / "templates" / "400" / "button.png").read_bytes() == b"png"
    assert fake_config.config.general.macro_order == ["400"]
    assert fake_config.save_calls == 1
    assert controller.selected_macro_id == "400"
    assert refresh_calls == ["refresh"]
    assert cast(Any, controller.view).statuses == ["Imported macro: Imported"]


def test_import_macro_reports_missing_template(tmp_path: Path, monkeypatch) -> None:
    archive_path = tmp_path / "macro.zip"
    write_macro_zip(
        archive_path,
        {
            "meta": {"name": "imported"},
            "steps": [{"type": "wait_image", "template": "missing"}],
        },
    )
    messages = []
    controller = make_controller()
    monkeypatch.setattr(home_controller.QFileDialog, "getOpenFileName", lambda *args: (str(archive_path), ""))
    monkeypatch.setattr(
        home_controller, "show_message_dialog", lambda parent, title, content: messages.append((title, content))
    )

    controller.import_macro()

    assert messages == [("Import failed", "Missing templates: missing")]


def test_export_current_macro_writes_macro_and_template_zip(tmp_path: Path, monkeypatch) -> None:
    export_path = tmp_path / "export.zip"
    template_dir = tmp_path / "templates" / "macro"
    template_dir.mkdir(parents=True)
    (template_dir / "button.png").write_bytes(b"png")
    macro = Macro.from_dict(
        {
            "meta": {"name": "macro", "label": "Macro"},
            "templates": {"button": {"label": "Button"}},
            "steps": [{"type": "wait_image", "template": "button"}],
        }
    )
    controller = make_controller()
    controller.current_macro = macro
    sync_calls = []
    controller.sync_macro_steps_from_tree = lambda: sync_calls.append("sync")
    monkeypatch.setattr(home_controller.QFileDialog, "getSaveFileName", lambda *args: (str(export_path), ""))
    monkeypatch.setattr(home_controller, "macro_path", lambda macro_id: tmp_path / "macros" / f"{macro_id}.json")
    monkeypatch.setattr(home_controller, "templates_dir", lambda macro_id: tmp_path / "templates" / macro_id)

    controller.export_current_macro()

    with zipfile.ZipFile(export_path, "r") as archive:
        assert set(archive.namelist()) == {"macro.json", "templates/button.png"}
        exported_macro = json.loads(archive.read("macro.json"))

    assert exported_macro["meta"]["name"] == "macro"
    assert sync_calls == ["sync"]
    assert cast(Any, controller.view).statuses == ["Exported macro: Macro"]


def archive_path_names(path: Path) -> set[str]:
    with zipfile.ZipFile(path, "r") as archive:
        return set(archive.namelist())


def test_handle_region_captured_updates_template_refs(tmp_path: Path, monkeypatch) -> None:
    old_file = tmp_path / "templates" / "macro" / "old.png"
    old_file.parent.mkdir(parents=True)
    old_file.write_bytes(b"old")
    macro = Macro(meta=MacroMeta(id="macro"), templates={"old": TemplateInfo(label="Old Label")})
    selected_step = {"type": "if_any_image", "templates": ["old"], "branches": {"old": [{"type": "key"}]}}
    controller = make_controller()
    controller.current_macro = macro
    controller.selected_step = selected_step
    mutate_calls = []
    controller.mutate_current_macro = lambda: mutate_calls.append("mutate")
    monkeypatch.setattr(
        home_controller,
        "template_path",
        lambda macro_id, template_id: tmp_path / "templates" / macro_id / f"{template_id}.png",
    )

    controller.handle_region_captured("old", "new", 320, 180)

    assert not old_file.exists()
    assert "old" not in macro.templates
    assert macro.templates["new"].label == "Old Label"
    assert macro.templates["new"].capture_width == 320
    assert selected_step["templates"] == ["new"]
    assert selected_step["branches"] == {"new": [{"type": "key"}]}
    assert mutate_calls == ["mutate"]
    assert cast(Any, controller.view).fake_window.show_normal_calls == 1


def test_handle_new_macro_retries_empty_name_then_creates(monkeypatch) -> None:
    model = FakeMacroModel()
    controller = make_controller()
    controller.macro_model = cast(MacroModel, model)
    dialogs = [FakeDialog(True, ""), FakeDialog(True, "Created")]
    messages = []
    refresh_calls = []
    controller.refresh_macro_list = lambda: refresh_calls.append("refresh")
    monkeypatch.setattr(home_controller, "NewMacroDialog", lambda parent: dialogs.pop(0))
    monkeypatch.setattr(
        home_controller, "show_message_dialog", lambda parent, title, content: messages.append((title, content))
    )
    monkeypatch.setattr(home_controller.time, "time", lambda: 300.0)

    controller.handle_new_macro()

    assert messages == [("New Macro", "Macro name cannot be empty.")]
    assert model.saved[0].meta.id == "300"
    assert model.saved[0].meta.label == "Created"
    assert controller.selected_macro_id == "300"
    assert refresh_calls == ["refresh"]
    assert cast(Any, controller.view).statuses == ["Created macro: Created"]


def test_handle_new_macro_cancel_does_not_save(monkeypatch) -> None:
    model = FakeMacroModel()
    controller = make_controller()
    controller.macro_model = cast(MacroModel, model)
    monkeypatch.setattr(home_controller, "NewMacroDialog", lambda parent: FakeDialog(False, "Ignored"))

    controller.handle_new_macro()

    assert model.saved == []
    assert cast(Any, controller.view).statuses == []


def test_handle_macro_rename_retries_empty_and_ignores_unchanged(monkeypatch) -> None:
    macro = Macro(meta=MacroMeta(id="alpha", label="Old"))
    model = FakeMacroModel(macros={"alpha": macro})
    controller = make_controller()
    controller.macro_model = cast(MacroModel, model)
    dialogs = [FakeDialog(True, ""), FakeDialog(True, "Old")]
    messages = []
    refresh_calls = []
    controller.refresh_macro_list = lambda: refresh_calls.append("refresh")
    monkeypatch.setattr(home_controller, "RenameMacroDialog", lambda parent, current_label: dialogs.pop(0))
    monkeypatch.setattr(
        home_controller, "show_message_dialog", lambda parent, title, content: messages.append((title, content))
    )

    controller.handle_macro_rename("alpha")

    assert messages == [("Rename Macro", "Macro name cannot be empty.")]
    assert macro.meta.label == "Old"
    assert model.saved == []
    assert refresh_calls == []
    assert cast(Any, controller.view).statuses == []


def test_describe_step_formats_template_branch_and_unknown_types() -> None:
    controller = make_controller()
    controller.current_macro = Macro(
        meta=MacroMeta(id="macro"),
        templates={"start": TemplateInfo(label="Start Button"), "empty": TemplateInfo(label="")},
    )

    assert controller.describe_step({"type": "hold_key_until_gone", "key": "a", "template": "start"}) == (
        "Hold a until Start Button gone"
    )
    assert controller.describe_step({"type": "if_image", "template": "start"}) == "If image Start Button"
    assert controller.describe_step({"type": "if_any_image", "templates": ["start", "missing"]}) == (
        "If any image Start Button, missing"
    )
    assert controller.describe_step({"type": "mouse_click", "button": "right", "x": 10, "y": 20}) == (
        "Right click at (10, 20)"
    )
    assert controller.describe_step({"type": "mouse_click", "target": "template", "template": "start"}) == (
        "Left click at Start Button"
    )
    assert controller.describe_step({"type": "mouse_move", "x": 30, "y": 40}) == "Move to (30, 40)"
    assert controller.describe_step({"type": "mouse_move", "target": "template", "template": "start"}) == (
        "Move to Start Button"
    )
    assert controller.describe_step({"type": "mouse_scroll", "clicks": -3}) == "Scroll -3"
    assert controller.describe_step({"type": "custom", "note": "later"}) == "custom (later)"
    assert controller.get_template_label("empty") == "empty"
    controller.current_macro = None
    assert controller.get_template_label("start") == "start"


def test_show_step_selection_handles_empty_macro_branch_and_skipped_child() -> None:
    controller = make_controller()

    controller.show_step_selection({"type": "key"})

    assert cast(Any, controller.view).right_panel.step_properties is None

    parent_step = {"type": "if_image", "template": "start", "then": [{"type": "key", "key": "enter"}]}
    macro = Macro(meta=MacroMeta(id="macro"), templates={"start": TemplateInfo(label="Start Button")})
    controller.current_macro = macro
    controller.step_tree = StepTree([parent_step])
    controller.selected_branch_parent = parent_step
    controller.selected_branch_key = "then"

    controller.show_step_selection(None)

    branch_properties = cast(Any, controller.view).right_panel.branch_properties
    assert branch_properties[0] is macro
    assert branch_properties[1] == "If image Start Button"
    assert branch_properties[2] == "Then"
    assert [step.type for step in branch_properties[3]] == ["key"]

    child_step = {"type": "key", "key": "a"}
    controller.selected_branch_parent = None
    controller.selected_branch_key = ""
    controller.step_tree = StepTree([{"type": "repeat", "skip": True, "steps": [child_step]}])

    controller.show_step_selection(child_step)

    step_properties = cast(Any, controller.view).right_panel.step_properties
    assert step_properties[1] == "Press a"
    assert step_properties[3] is False


def test_handle_macro_running_changed_reports_running_stopped_and_message() -> None:
    controller = make_controller()
    calls = []
    controller.set_editing_locked = lambda locked: calls.append(locked)
    controller.current_runner = cast(Any, FakeRunner(status=Status(last_reason="user_stopped")))

    controller.handle_macro_running_changed(True)
    controller.handle_macro_running_changed(False)
    controller.current_runner = cast(Any, FakeRunner(status=Status(message="failed")))
    controller.handle_macro_running_changed(False)
    controller.current_runner = None
    controller.handle_macro_running_changed(False)

    assert calls == [True, False, False, False]
    assert cast(Any, controller.view).statuses == [
        "Running macro: Runner",
        "Stopped macro: Runner (00:00)",
        "Runner: failed (00:00)",
    ]


def test_handle_hotkey_triggered_ignores_missing_disabled_and_stops_running(qtbot) -> None:
    macro = Macro(meta=MacroMeta(id="macro", enabled=False))
    model = FakeMacroModel(macros={"macro": macro})
    controller = make_controller()
    controller.macro_model = cast(MacroModel, model)
    controller.hotkey_service.hotkey_map = {1: "missing", 2: "macro", 3: "running"}

    controller.handle_hotkey_triggered(99)
    controller.handle_hotkey_triggered(1)
    controller.handle_hotkey_triggered(2)

    running_runner = FakeRunner(running=True)
    controller.selected_macro_id = "running"
    controller.current_runner = cast(Any, running_runner)
    model.macros["running"] = Macro(meta=MacroMeta(id="running", enabled=True))

    with qtbot.waitSignal(home_controller.event_bus.macro_running_changed, timeout=100) as stopped:
        controller.handle_hotkey_triggered(3)

    assert stopped.args == [False]
    assert running_runner.stop_calls == 1
    assert cast(Any, controller.view).statuses == []


def test_handle_hotkey_triggered_toggles_pause_hotkey() -> None:
    controller = make_controller()
    runner = FakeRunner(running=True)
    controller.current_runner = cast(Any, runner)

    controller.handle_hotkey_triggered(hotkey_service.PAUSE_HOTKEY_ID)

    assert runner.pause_calls == 1


def test_import_macro_returns_when_no_file_selected(monkeypatch) -> None:
    controller = make_controller()
    monkeypatch.setattr(home_controller.QFileDialog, "getOpenFileName", lambda *args: ("", ""))

    controller.import_macro()

    assert cast(Any, controller.view).statuses == []


def test_import_macro_reports_bad_zip_and_missing_macro_json(tmp_path: Path, monkeypatch) -> None:
    archive_path = tmp_path / "macro.zip"
    messages = []
    controller = make_controller()
    monkeypatch.setattr(home_controller.QFileDialog, "getOpenFileName", lambda *args: (str(archive_path), ""))
    monkeypatch.setattr(
        home_controller, "show_message_dialog", lambda parent, title, content: messages.append((title, content))
    )

    archive_path.write_bytes(b"not a zip")
    controller.import_macro()

    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("other.json", "{}")
    controller.import_macro()

    assert messages == [
        ("Import failed", "Invalid zip file"),
        ("Import failed", "macro.json is missing from the archive"),
    ]


def test_duplicate_current_macro_reports_missing_macro_and_existing_destination(tmp_path: Path, monkeypatch) -> None:
    controller = make_controller()

    controller.duplicate_current_macro()

    controller.current_macro = Macro(meta=MacroMeta(id="alpha", label="Alpha"))
    existing_path = tmp_path / "300.json"
    existing_path.write_text("{}")
    monkeypatch.setattr(home_controller.time, "time", lambda: 300.0)
    monkeypatch.setattr(home_controller, "macro_path", lambda macro_id: existing_path)

    controller.duplicate_current_macro()

    assert cast(Any, controller.view).statuses == [
        "Select a macro first",
        "Unable to duplicate macro. Please try again.",
    ]


def test_update_undo_redo_and_current_macro_helpers() -> None:
    controller = make_controller()
    controller.editing_locked = True

    controller.set_current_macro(Macro(meta=MacroMeta(id="macro")))

    toolbar = cast(Any, controller.view).toolbar
    assert toolbar.undo_button.enabled is False
    assert toolbar.redo_button.enabled is False

    controller.editing_locked = False
    controller.current_runner = cast(Any, FakeRunner())
    controller.selected_macro_id = "macro"
    controller.undo_stack.append({"undo": True})
    controller.redo_stack.append({"redo": True})

    controller.update_undo_redo_state()

    assert toolbar.undo_button.enabled is True
    assert toolbar.redo_button.enabled is True
    assert controller.current_macro_dict() == {"steps": []}

    controller.current_runner = None
    assert controller.current_macro_dict() is None


def test_sync_runner_macro_from_current_replaces_runner() -> None:
    macro = Macro(meta=MacroMeta(id="macro"))
    controller = make_controller()
    controller.current_macro = macro
    controller.current_runner = cast(Any, FakeRunner())

    controller.sync_runner_macro_from_current()

    assert controller.current_runner is not None
    assert controller.current_runner.macro_path == Path("macro.json")
    assert controller.current_runner.macro["meta"]["name"] == "macro"


def test_restore_macro_state_rebuilds_runner_and_saves(tmp_path: Path, monkeypatch) -> None:
    old_macro = Macro.from_dict({"meta": {"name": "macro"}, "steps": [{"type": "key", "key": "old"}]})
    model = FakeMacroModel(macros={"macro": old_macro})
    controller = make_controller()
    controller.current_macro = old_macro
    controller.current_runner = cast(Any, FakeRunner())
    controller.macro_model = cast(MacroModel, model)
    selected = []
    controller.select_after_undo_redo = lambda old_steps, new_steps, selection_index=None: selected.append(
        (old_steps, new_steps, selection_index)
    )
    monkeypatch.setattr(home_controller, "macro_path", lambda macro_id: tmp_path / f"{macro_id}.json")

    controller.restore_macro_state({"meta": {"name": "macro"}, "steps": [{"type": "delay", "ms": 5}]}, 0)

    assert controller.current_macro is not None
    assert controller.current_macro.steps[0].type == "delay"
    assert selected[0][2] == 0
    assert model.saved[-1].steps[0].type == "delay"


def test_restore_macro_state_returns_without_runner() -> None:
    controller = make_controller()

    controller.restore_macro_state({"meta": {}, "steps": []})

    assert controller.current_macro is None


def test_update_step_action_state_handles_locked_multi_and_single_selection() -> None:
    step = {"type": "key", "key": "a"}
    controller = make_controller()
    controller.step_tree = StepTree([step, {"type": "delay", "ms": 1}])
    selected_items = [object()]
    center = cast(Any, controller.view).center_panel
    center.step_list.selectedItems = lambda: selected_items
    center.item_to_step = {selected_items[0]: step}

    controller.update_step_action_state()

    toolbar = cast(Any, controller.view).toolbar
    assert toolbar.delete_button.enabled is True
    assert toolbar.move_up_button.enabled is False
    assert toolbar.move_down_button.enabled is True

    controller.editing_locked = True
    toolbar.delete_button.enabled = False
    controller.update_step_action_state()

    assert toolbar.delete_button.enabled is False


def test_selected_step_nodes_ignores_missing_or_non_dict_items() -> None:
    controller = make_controller()
    controller.step_tree = StepTree([{"type": "key", "key": "a"}])
    items = [object(), object()]
    center = cast(Any, controller.view).center_panel
    center.step_list.selectedItems = lambda: items
    center.item_to_step = {items[0]: "not-step", items[1]: {"type": "missing"}}

    assert controller.selected_step_nodes() == []


def test_clipboard_copy_cut_and_paste_steps(tmp_path: Path, monkeypatch, qtbot) -> None:
    step = {"type": "wait_image", "template": "button"}
    macro = Macro.from_dict(
        {
            "meta": {"name": "macro"},
            "templates": {"button": {"label": "Button", "capture_width": 320}},
            "steps": [step],
        }
    )
    controller = make_controller()
    controller.current_macro = macro
    controller.current_runner = cast(Any, FakeRunner())
    controller.step_tree = StepTree([step])
    controller.selected_macro_id = "macro"
    item = object()
    center = cast(Any, controller.view).center_panel
    center.step_list.selectedItems = lambda: [item]
    center.item_to_step = {item: step}
    template_file = tmp_path / "templates" / "macro" / "button.png"
    template_file.parent.mkdir(parents=True)
    template_file.write_bytes(b"png")
    monkeypatch.setattr(
        home_controller,
        "template_path",
        lambda macro_id, template_id: tmp_path / "templates" / macro_id / f"{template_id}.png",
    )
    monkeypatch.setattr(home_controller, "templates_dir", lambda macro_id: tmp_path / "templates" / macro_id)
    monkeypatch.setattr(home_controller.time, "time", lambda: 900.0)

    with qtbot.waitSignal(home_controller.event_bus.clipboard_changed, timeout=100) as clipboard_changed:
        controller.copy_selected_steps()

    assert clipboard_changed.args == [True]
    assert controller.step_clipboard is not None
    assert controller.step_clipboard["templates"] == {"button": b"png"}

    controller.cut_selected_steps()

    assert controller.step_tree.steps == []
    assert cast(Any, controller.view).statuses[-1] == "Deleted step"

    controller.paste_steps()

    assert controller.step_tree.steps[0]["template"] == "900"
    assert (tmp_path / "templates" / "macro" / "900.png").read_bytes() == b"png"
    assert controller.current_macro.templates["900"].label == "Button"
    assert controller.selected_step == controller.step_tree.steps[0]


def test_copy_cut_and_paste_return_without_required_state() -> None:
    controller = make_controller()

    controller.copy_selected_steps()
    controller.cut_selected_steps()
    controller.paste_steps()

    assert controller.step_clipboard is None
    assert cast(Any, controller.view).statuses == []


def test_paste_steps_returns_for_empty_clipboard_steps() -> None:
    controller = make_controller()
    controller.current_macro = Macro(meta=MacroMeta(id="macro"))
    controller.current_runner = cast(Any, FakeRunner())
    controller.step_tree = StepTree([])
    controller.step_clipboard = {"steps": [], "templates": {}, "template_meta": {}}

    controller.paste_steps()

    assert controller.step_tree.steps == []


def test_add_step_to_branch_repeat_and_invalid_branch() -> None:
    parent = {"type": "if_image", "then": []}
    repeat = {"type": "repeat", "steps": []}
    macro = Macro.from_dict({"meta": {"name": "macro"}, "steps": [parent, repeat]})
    controller = make_controller()
    controller.current_macro = macro
    controller.current_runner = cast(Any, FakeRunner())
    controller.step_tree = StepTree([parent, repeat])
    controller.selected_branch_parent = {"type": "missing"}
    controller.selected_branch_key = "then"

    controller.add_step("key")

    assert cast(Any, controller.view).statuses == ["Select a valid branch first"]

    controller.selected_branch_parent = parent
    controller.selected_branch_key = "then"
    controller.add_step("delay")

    assert parent["then"][0]["type"] == "delay"

    controller.selected_branch_parent = None
    controller.selected_branch_key = ""
    controller.selected_step = repeat
    controller.add_step("key")

    assert repeat["steps"][0]["type"] == "key"


def test_duplicate_delete_wrap_and_move_selected_step_paths() -> None:
    first = {"type": "key", "key": "a"}
    second = {"type": "delay", "ms": 1}
    macro = Macro.from_dict({"meta": {"name": "macro"}, "steps": [first, second]})
    controller = make_controller()
    controller.current_macro = macro
    controller.current_runner = cast(Any, FakeRunner())
    controller.step_tree = StepTree([first, second])
    controller.selected_macro_id = "macro"
    item = object()
    center = cast(Any, controller.view).center_panel
    center.step_list.selectedItems = lambda: [item]
    center.item_to_step = {item: first}

    controller.duplicate_selected_step()

    assert controller.step_tree.steps[1]["type"] == "key"
    assert cast(Any, controller.view).statuses[-1] == "Duplicated step"

    center.item_to_step = {item: controller.step_tree.steps[1]}
    controller.wrap_selected_step_in_repeat()

    assert controller.step_tree.steps[1]["type"] == "repeat"
    assert cast(Any, controller.view).statuses[-1] == "Wrapped step in repeat"

    controller.move_selected_step(1)

    assert cast(Any, controller.view).statuses[-1] == "Moved step"

    moved_step = controller.selected_step
    center.item_to_step = {item: moved_step}
    controller.delete_selected_step()

    assert cast(Any, controller.view).statuses[-1] == "Deleted step"


def test_duplicate_selected_step_clones_template(tmp_path: Path, monkeypatch) -> None:
    step = {"type": "wait_image", "template": "button"}
    macro = Macro.from_dict(
        {
            "meta": {"name": "macro"},
            "templates": {"button": {"label": "Button", "capture_width": 320}},
            "steps": [step],
        }
    )
    controller = make_controller()
    controller.current_macro = macro
    controller.current_runner = cast(Any, FakeRunner())
    controller.step_tree = StepTree([step])
    controller.selected_macro_id = "macro"
    item = object()
    center = cast(Any, controller.view).center_panel
    center.step_list.selectedItems = lambda: [item]
    center.item_to_step = {item: step}
    template_file = tmp_path / "templates" / "macro" / "button.png"
    template_file.parent.mkdir(parents=True)
    template_file.write_bytes(b"png")
    monkeypatch.setattr(
        home_controller,
        "template_path",
        lambda macro_id, template_id: tmp_path / "templates" / macro_id / f"{template_id}.png",
    )
    monkeypatch.setattr(home_controller, "templates_dir", lambda macro_id: tmp_path / "templates" / macro_id)
    monkeypatch.setattr(home_controller.time, "time", lambda: 904.0)

    controller.duplicate_selected_step()

    assert controller.step_tree.steps[0]["template"] == "button"
    assert controller.step_tree.steps[1]["template"] == "904"
    assert (tmp_path / "templates" / "macro" / "904.png").read_bytes() == b"png"
    assert macro.templates["button"].label == "Button"
    assert macro.templates["904"].label == "Button"
    assert macro.templates["904"].capture_width == 320


def test_delete_selected_step_removes_unused_template(tmp_path: Path) -> None:
    step = {"type": "wait_image", "template": "button"}
    macro = Macro.from_dict(
        {
            "meta": {"id": "macro"},
            "templates": {"button": {"label": "Button"}},
            "steps": [step],
        }
    )
    controller = make_controller()
    controller.current_macro = macro
    controller.current_runner = cast(Any, FakeRunner())
    controller.selected_macro_id = "macro"
    controller.step_tree = StepTree([step])
    controller.selected_step = step
    controller.template_service = TemplateService(
        controller.generate_template_id,
        controller.default_template_label,
        lambda macro_id, template_id: tmp_path / "templates" / macro_id / f"{template_id}.png",
    )
    template_file = tmp_path / "templates" / "macro" / "button.png"
    template_file.parent.mkdir(parents=True)
    template_file.write_bytes(b"png")

    item = object()
    center = cast(Any, controller.view).center_panel
    center.step_list.selectedItems = lambda: [item]
    center.item_to_step = {item: step}

    controller.delete_selected_step()

    assert "button" not in macro.templates
    assert not template_file.exists()
    assert macro.steps == []
    assert cast(FakeMacroModel, controller.macro_model).saved[-1].templates == {}


def test_delete_selected_step_keeps_template_used_by_another_step(tmp_path: Path) -> None:
    deleted_step = {"type": "wait_image", "template": "shared"}
    remaining_step = {"type": "mouse_click", "template": "shared"}
    macro = Macro.from_dict(
        {
            "meta": {"id": "macro"},
            "templates": {"shared": {"label": "Shared"}},
            "steps": [deleted_step, remaining_step],
        }
    )
    controller = make_controller()
    controller.current_macro = macro
    controller.current_runner = cast(Any, FakeRunner())
    controller.selected_macro_id = "macro"
    controller.step_tree = StepTree([deleted_step, remaining_step])
    controller.selected_step = deleted_step
    controller.template_service = TemplateService(
        controller.generate_template_id,
        controller.default_template_label,
        lambda macro_id, template_id: tmp_path / "templates" / macro_id / f"{template_id}.png",
    )
    template_file = tmp_path / "templates" / "macro" / "shared.png"
    template_file.parent.mkdir(parents=True)
    template_file.write_bytes(b"png")

    item = object()
    center = cast(Any, controller.view).center_panel
    center.step_list.selectedItems = lambda: [item]
    center.item_to_step = {item: deleted_step}

    controller.delete_selected_step()

    assert "shared" in macro.templates
    assert template_file.exists()
    assert controller.step_tree.collect_template_refs() == {"shared"}
    assert cast(FakeMacroModel, controller.macro_model).saved[-1].templates == macro.templates


def test_step_actions_report_missing_macro_or_step() -> None:
    controller = make_controller()

    controller.duplicate_selected_step()
    controller.delete_selected_step()
    controller.wrap_selected_step_in_repeat()
    controller.move_selected_step(1)

    controller.step_tree = StepTree([])
    controller.duplicate_selected_step()
    controller.delete_selected_step()
    controller.wrap_selected_step_in_repeat()
    controller.move_selected_step(1)

    assert cast(Any, controller.view).statuses == [
        "Select a macro first",
        "Select a macro first",
        "Select a macro first",
        "Select a macro first",
        "Select a macro first",
        "Select a step first",
        "Select a step first",
        "Select a step first",
    ]


def test_move_selected_step_reports_failed_move() -> None:
    step = {"type": "key", "key": "a"}
    controller = make_controller()
    controller.current_runner = cast(Any, FakeRunner())
    controller.selected_macro_id = "macro"
    controller.step_tree = StepTree([step])
    controller.selected_step = step

    controller.move_selected_step(-1)

    assert controller.undo_stack == []
    assert cast(Any, controller.view).statuses == ["Cannot move selected step"]


def test_run_current_macro_reports_missing_runner() -> None:
    controller = make_controller()

    controller.run_current_macro()

    assert cast(Any, controller.view).statuses == ["Select a macro first"]


def test_open_folders_settings_and_quit_emit_or_call(tmp_path: Path, monkeypatch, qtbot) -> None:
    controller = make_controller()
    opened = []
    closed = []
    cast(Any, controller.view).fake_window.close = lambda: closed.append("close")
    monkeypatch.setattr(home_controller, "log_dir", lambda: tmp_path / "logs")
    monkeypatch.setattr(home_controller, "macros_dir", lambda: tmp_path / "macros")
    monkeypatch.setattr(home_controller.os, "startfile", lambda path: opened.append(path), raising=False)

    controller.open_logs_folder()
    controller.open_macro_folder()

    with qtbot.waitSignal(home_controller.event_bus.switch_page_requested, timeout=100) as settings_page:
        controller.open_settings()

    with qtbot.waitSignal(home_controller.event_bus.switch_page_requested, timeout=100) as packs_page:
        controller.open_macro_explorer()

    controller.quit_application()

    assert opened == [tmp_path / "logs", tmp_path / "macros"]
    assert settings_page.args == ["settings"]
    assert packs_page.args == ["packs"]
    assert closed == ["close"]


def test_template_capture_add_delete_and_meta_changes(tmp_path: Path, monkeypatch) -> None:
    wait_step = {"type": "wait_image", "template": "old"}
    any_step = {"type": "if_any_image", "templates": ["old", "keep"], "branches": {"old": [{"type": "key"}]}}
    macro = Macro(
        meta=MacroMeta(id="macro"),
        templates={"old": TemplateInfo(label="Old"), "keep": TemplateInfo(label="Keep")},
    )
    controller = make_controller()
    controller.current_macro = macro
    controller.current_runner = cast(Any, FakeRunner())
    controller.selected_step = wait_step
    controller.step_tree = StepTree([wait_step, any_step])
    calls = []
    controller.mutate_current_macro = lambda: calls.append("mutate")
    controller.save_current_macro = lambda: calls.append("save")
    controller.sync_macro_steps_from_tree = lambda: calls.append("sync")
    controller.refresh_step_tree = lambda: calls.append("refresh")
    old_file = tmp_path / "templates" / "macro" / "old.png"
    old_file.parent.mkdir(parents=True)
    old_file.write_bytes(b"png")
    monkeypatch.setattr(
        home_controller,
        "template_path",
        lambda macro_id, template_id: tmp_path / "templates" / macro_id / f"{template_id}.png",
    )
    monkeypatch.setattr(home_controller.time, "time", lambda: 400.0)
    monkeypatch.setattr(home_controller.QTimer, "singleShot", lambda delay, callback: callback())
    launches = []
    controller.launch_region_selector = lambda template_id, target_display=None: launches.append(
        (template_id, target_display)
    )
    monkeypatch.setattr(home_controller.display, "target_display_for_macro", lambda target_window: "captured-display")

    controller.handle_template_capture("old")
    controller.selected_step = any_step
    controller.handle_template_add()
    controller.handle_template_delete("old")
    controller.handle_template_meta_changed("keep", "label", "Kept")
    controller.handle_template_meta_changed("keep", "capture_width", "bad")
    controller.handle_template_meta_changed("missing", "label", "Nope")

    assert cast(Any, controller.view).fake_window.show_minimized_calls == 1
    assert launches == [("old", "captured-display")]
    assert "400" in any_step["templates"]
    assert not old_file.exists()
    assert wait_step["template"] == ""
    assert any_step["templates"] == ["keep", "400"]
    assert "old" not in any_step["branches"]
    assert macro.templates["keep"].label == "Kept"
    assert calls == ["mutate", "mutate", "sync", "save", "refresh"]


def test_template_add_and_capture_return_without_required_state() -> None:
    controller = make_controller()

    controller.handle_template_capture("old")
    controller.handle_template_add()
    controller.handle_template_delete("old")
    controller.handle_template_meta_changed("old", "label", "Old")

    assert cast(Any, controller.view).statuses == []


def test_handle_region_captured_falls_back_to_generated_label(tmp_path: Path, monkeypatch) -> None:
    selected_step = {"type": "wait_image", "template": "old"}
    macro = Macro(meta=MacroMeta(id="macro"), templates={"old": TemplateInfo(label="")})
    controller = make_controller()
    controller.current_macro = macro
    controller.selected_step = selected_step
    calls = []
    controller.mutate_current_macro = lambda: calls.append("mutate")
    monkeypatch.setattr(
        home_controller,
        "template_path",
        lambda macro_id, template_id: tmp_path / "templates" / macro_id / f"{template_id}.png",
    )

    controller.handle_region_captured("old", "new", 1, 2)

    assert selected_step["template"] == "new"
    assert macro.templates["new"].label == "Template new"
    assert calls == ["mutate"]


def test_handle_region_captured_returns_without_selection_or_macro() -> None:
    controller = make_controller()

    controller.handle_region_captured("old", "new", 1, 2)

    assert cast(Any, controller.view).fake_window.show_normal_calls == 1


def test_state_helpers_return_when_runner_or_selection_missing() -> None:
    controller = make_controller()

    controller.sync_runner_macro_from_current()
    controller.push_undo()
    controller.save_current_macro()
    controller.undo()
    controller.redo()

    assert controller.current_runner is None
    assert controller.undo_stack == []
    assert controller.redo_stack == []

    controller.current_runner = cast(Any, FakeRunner())
    controller.step_tree = StepTree([{"type": "key", "key": "a"}])
    controller.selected_step = {"type": "missing"}

    assert controller.selected_step_flat_index() is None


def test_update_step_action_state_disables_move_buttons_for_multi_selection() -> None:
    steps = [{"type": "key", "key": "a"}, {"type": "delay", "ms": 1}]
    controller = make_controller()
    controller.step_tree = StepTree(steps)
    items = [object(), object()]
    center = cast(Any, controller.view).center_panel
    center.step_list.selectedItems = lambda: items
    center.item_to_step = {items[0]: steps[0], items[1]: steps[1]}

    controller.update_step_action_state()

    toolbar = cast(Any, controller.view).toolbar
    assert toolbar.delete_button.enabled is True
    assert toolbar.move_up_button.enabled is False
    assert toolbar.move_down_button.enabled is False


def test_select_after_undo_redo_selects_previous_when_new_steps_shorter() -> None:
    controller = make_controller()
    controller.step_tree = StepTree([{"type": "key", "key": "a"}])
    calls = []
    old_steps = Macro.from_dict({"meta": {}, "steps": [{"type": "key", "key": "a"}, {"type": "delay", "ms": 1}]}).steps
    controller.refresh_step_tree = lambda: calls.append("refresh")
    controller.show_step_selection = lambda step: calls.append(("show", step))

    controller.select_after_undo_redo(old_steps, [])

    assert controller.selected_step == {"type": "key", "key": "a"}
    assert calls == ["refresh", ("show", controller.selected_step)]


def test_step_selection_helpers_return_for_missing_nodes() -> None:
    controller = make_controller()
    controller.step_tree = StepTree([{"type": "key", "key": "a"}])

    assert controller.branch_steps({"type": "missing"}, "then") == []
    assert controller.is_child_of_skipped_repeat({"type": "missing"}) is False
    controller.set_descendant_skip({"type": "missing"}, True)

    assert controller.step_tree.steps == [{"type": "key", "key": "a"}]


def test_handle_macro_duplicate_loads_requested_macro_before_copy() -> None:
    controller = make_controller()
    calls = []
    controller.selected_macro_id = "old"
    controller.load_selected_macro = lambda macro_id: calls.append(("load", macro_id))
    controller.duplicate_current_macro = lambda: calls.append(("duplicate", controller.selected_macro_id))

    controller.handle_macro_duplicate("new")

    assert calls == [("load", "new"), ("duplicate", "new")]


def test_handle_macro_delete_reports_failed_delete(monkeypatch) -> None:
    controller = make_controller()
    controller.macro_model = cast(MacroModel, FakeMacroModel())
    messages = []
    monkeypatch.setattr(home_controller, "show_confirm_dialog", lambda *args: True)
    monkeypatch.setattr(
        home_controller, "show_message_dialog", lambda parent, title, content: messages.append((title, content))
    )

    controller.handle_macro_delete("missing")

    assert messages == [("Delete Macro", "Unable to delete the macro.")]


def test_copy_selected_steps_returns_when_top_level_empty(monkeypatch) -> None:
    step = {"type": "key", "key": "a"}
    controller = make_controller()
    controller.current_macro = Macro(meta=MacroMeta(id="macro"))
    controller.step_tree = StepTree([step])
    step_tree = cast(Any, controller.step_tree)
    controller.selected_step_nodes = lambda: [step_tree.root_nodes[0]]
    monkeypatch.setattr(step_tree, "get_top_level", lambda selected: [])

    controller.copy_selected_steps()

    assert controller.step_clipboard is None


def test_paste_steps_merges_existing_template_metadata(tmp_path: Path, monkeypatch) -> None:
    macro = Macro(meta=MacroMeta(id="macro"), templates={"button": TemplateInfo()})
    controller = make_controller()
    controller.current_macro = macro
    controller.current_runner = cast(Any, FakeRunner())
    controller.step_tree = StepTree([])
    controller.step_clipboard = {
        "steps": [{"type": "wait_image", "template": "button"}],
        "templates": {"button": b"png"},
        "template_meta": {"button": {"label": "Button", "capture_width": 320, "capture_height": 180}},
    }
    calls = []
    controller.mutate_current_macro = lambda: calls.append("mutate")
    monkeypatch.setattr(home_controller, "templates_dir", lambda macro_id: tmp_path / "templates" / macro_id)
    monkeypatch.setattr(
        home_controller,
        "template_path",
        lambda macro_id, template_id: tmp_path / "templates" / macro_id / f"{template_id}.png",
    )
    monkeypatch.setattr(home_controller.time, "time", lambda: 901.0)

    controller.paste_steps()

    assert controller.step_tree.steps[0]["template"] == "901"
    assert (tmp_path / "templates" / "macro" / "901.png").read_bytes() == b"png"
    assert macro.templates["button"].label == ""
    assert macro.templates["901"].label == "Button"
    assert macro.templates["901"].capture_width == 320
    assert macro.templates["901"].capture_height == 180
    assert calls == ["mutate"]


def test_import_macro_validation_errors(tmp_path: Path, monkeypatch) -> None:
    archive_path = tmp_path / "macro.zip"
    messages = []
    controller = make_controller()
    monkeypatch.setattr(home_controller.QFileDialog, "getOpenFileName", lambda *args: (str(archive_path), ""))
    monkeypatch.setattr(
        home_controller, "show_message_dialog", lambda parent, title, content: messages.append((title, content))
    )

    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("macro.json", json.dumps([]))
    controller.import_macro()

    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("macro.json", json.dumps({"steps": []}))
    controller.import_macro()

    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("macro.json", json.dumps({"meta": {}, "steps": []}))
    controller.import_macro()

    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("macro.json", json.dumps({"meta": {"name": "macro"}, "steps": {}}))
    controller.import_macro()

    assert messages == [
        ("Import failed", "Invalid macro data"),
        ("Import failed", "Macro metadata is invalid"),
        ("Import failed", "Macro metadata is invalid"),
        ("Import failed", "Macro steps are invalid"),
    ]


def test_import_macro_handles_duplicate_id_legacy_meta_and_existing_order(tmp_path: Path, monkeypatch) -> None:
    archive_path = tmp_path / "macro.zip"
    write_macro_zip(
        archive_path,
        {
            "meta": {"name": "imported", "label": ""},
            "templates": {"button": "legacy"},
            "steps": [{"type": "wait_image", "template": "button"}],
        },
        {
            "templates/button.png": b"new",
            "templates/button.json": json.dumps({"capture_width": 640, "capture_height": 360}).encode(),
        },
    )
    existing_file = tmp_path / "macros" / "500.json"
    existing_file.parent.mkdir(parents=True)
    existing_file.write_text("{}")
    fake_config = FakeConfigModel()
    fake_config.config.general.macro_order = ["501"]
    model = FakeMacroModel(existing_ids={"500"})
    controller = make_controller()
    controller.macro_model = cast(MacroModel, model)
    refresh_calls = []
    controller.refresh_macro_list = lambda: refresh_calls.append("refresh")
    monkeypatch.setattr(home_controller.QFileDialog, "getOpenFileName", lambda *args: (str(archive_path), ""))
    monkeypatch.setattr(macro_import_service.time, "time", lambda: 500.0)
    monkeypatch.setattr(home_controller, "macro_path", lambda macro_id: tmp_path / "macros" / f"{macro_id}.json")
    monkeypatch.setattr(home_controller, "templates_dir", lambda macro_id: tmp_path / "templates" / macro_id)
    monkeypatch.setattr(
        home_controller,
        "template_path",
        lambda macro_id, template_id: tmp_path / "templates" / macro_id / f"{template_id}.png",
    )
    monkeypatch.setattr(macro_import_service, "macro_path", lambda macro_id: tmp_path / "macros" / f"{macro_id}.json")
    monkeypatch.setattr(macro_import_service, "templates_dir", lambda macro_id: tmp_path / "templates" / macro_id)
    monkeypatch.setattr(
        macro_import_service,
        "template_path",
        lambda macro_id, template_id: tmp_path / "templates" / macro_id / f"{template_id}.png",
    )
    monkeypatch.setattr(home_controller, "config_model", fake_config)

    controller.import_macro()

    assert model.saved[0].meta.id == "501"
    assert model.saved[0].meta.label == "501"
    assert model.saved[0].templates["button"].label == "button"
    assert model.saved[0].templates["button"].capture_width == 640
    assert (tmp_path / "templates" / "501" / "button.png").read_bytes() == b"new"
    assert fake_config.config.general.macro_order == ["501"]
    assert fake_config.save_calls == 0
    assert refresh_calls == ["refresh"]


def test_import_macro_skips_invalid_legacy_metadata(tmp_path: Path, monkeypatch) -> None:
    archive_path = tmp_path / "macro.zip"
    write_macro_zip(
        archive_path,
        {
            "meta": {"name": "macro"},
            "templates": [],
            "steps": [
                {"type": "wait_image", "template": "bad_json"},
                {"type": "wait_image", "template": "bad_type"},
            ],
        },
        {
            "templates/bad_json.png": b"png",
            "templates/bad_json.json": b"{bad",
            "templates/bad_type.png": b"png",
            "templates/bad_type.json": json.dumps([]).encode(),
        },
    )
    model = FakeMacroModel()
    controller = make_controller()
    controller.macro_model = cast(MacroModel, model)
    controller.refresh_macro_list = lambda: None
    monkeypatch.setattr(home_controller.QFileDialog, "getOpenFileName", lambda *args: (str(archive_path), ""))
    monkeypatch.setattr(home_controller, "macro_path", lambda macro_id: tmp_path / "macros" / f"{macro_id}.json")
    monkeypatch.setattr(home_controller, "templates_dir", lambda macro_id: tmp_path / "templates" / macro_id)
    monkeypatch.setattr(
        home_controller,
        "template_path",
        lambda macro_id, template_id: tmp_path / "templates" / macro_id / f"{template_id}.png",
    )
    monkeypatch.setattr(macro_import_service, "macro_path", lambda macro_id: tmp_path / "macros" / f"{macro_id}.json")
    monkeypatch.setattr(macro_import_service, "templates_dir", lambda macro_id: tmp_path / "templates" / macro_id)
    monkeypatch.setattr(
        macro_import_service,
        "template_path",
        lambda macro_id, template_id: tmp_path / "templates" / macro_id / f"{template_id}.png",
    )

    controller.import_macro()

    assert model.saved[0].templates == {}


def test_export_current_macro_returns_or_reports_errors(tmp_path: Path, monkeypatch) -> None:
    controller = make_controller()

    controller.export_current_macro()

    macro = Macro(meta=MacroMeta(id="macro", label="Macro"))
    controller.current_macro = macro
    monkeypatch.setattr(home_controller, "macro_path", lambda macro_id: tmp_path / f"{macro_id}.json")
    monkeypatch.setattr(home_controller.QFileDialog, "getSaveFileName", lambda *args: ("", ""))
    controller.export_current_macro()

    monkeypatch.setattr(
        home_controller.QFileDialog, "getSaveFileName", lambda *args: (str(tmp_path / "missing" / "out.zip"), "")
    )
    controller.export_current_macro()

    assert cast(Any, controller.view).statuses == ["Select a macro first", "Failed to export macro"]


def test_launch_region_selector_returns_without_macro_and_starts_with_macro(monkeypatch) -> None:
    controller = make_controller()
    starts = []

    class FakeRegionSelector:
        def __init__(self, macro_id: str, parent, target_display=None) -> None:
            self.macro_id = macro_id
            self.parent = parent
            self.target_display = target_display
            self.region_selected = FakeSignal()
            self.cancelled = FakeSignal()

        def start(self) -> None:
            starts.append(
                (
                    self.macro_id,
                    self.parent,
                    self.target_display,
                    len(self.region_selected.connected),
                    len(self.cancelled.connected),
                )
            )

    monkeypatch.setattr(home_controller, "RegionSelector", FakeRegionSelector)
    monkeypatch.setattr(home_controller.display, "target_display_for_macro", lambda title: None)

    controller.launch_region_selector("old")

    controller.current_macro = Macro(meta=MacroMeta(id="macro"))
    controller.launch_region_selector("old")

    assert starts == [("macro", controller.view, None, 1, 1)]


def test_launch_region_selector_prefers_macro_target_window_screen(monkeypatch) -> None:
    controller = make_controller()
    target_display = object()
    targets = []

    class FakeRegionSelector:
        def __init__(self, macro_id: str, parent, target_display=None) -> None:
            self.region_selected = FakeSignal()
            self.cancelled = FakeSignal()
            targets.append((macro_id, parent, target_display))

        def start(self) -> None:
            pass

    controller.current_macro = Macro(meta=MacroMeta(id="macro", target_window="Game"))
    monkeypatch.setattr(home_controller, "RegionSelector", FakeRegionSelector)
    monkeypatch.setattr(
        home_controller.display,
        "target_display_for_macro",
        lambda title: target_display if title == "Game" else None,
    )

    controller.launch_region_selector("old")

    assert targets == [("macro", controller.view, target_display)]


def test_handle_template_capture_resolves_display_before_minimizing(monkeypatch) -> None:
    controller = make_controller()
    controller.current_macro = Macro(meta=MacroMeta(id="macro"))
    calls = []

    def fake_target_display(target_window: str):
        calls.append(("target", target_window, cast(Any, controller.view).fake_window.show_minimized_calls))
        return "cursor-display"

    def fake_single_shot(delay: int, callback) -> None:
        calls.append(("timer", delay, cast(Any, controller.view).fake_window.show_minimized_calls))
        callback()

    def fake_launch(template_id: str, target_display=None) -> None:
        calls.append(
            ("launch", template_id, target_display, cast(Any, controller.view).fake_window.show_minimized_calls)
        )

    monkeypatch.setattr(home_controller.display, "target_display_for_macro", fake_target_display)
    monkeypatch.setattr(home_controller.QTimer, "singleShot", fake_single_shot)
    controller.launch_region_selector = fake_launch

    controller.handle_template_capture("old")

    assert calls == [
        ("target", "", 0),
        ("timer", 200, 1),
        ("launch", "old", "cursor-display", 1),
    ]


def test_handle_template_pick_updates_if_any_image_refs(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "source.png"
    source.write_bytes(b"png")
    old_file = tmp_path / "templates" / "macro" / "old.png"
    old_file.parent.mkdir(parents=True)
    old_file.write_bytes(b"old")
    selected_step = {"type": "if_any_image", "templates": ["old"], "branches": {"old": [{"type": "key"}]}}
    macro = Macro(meta=MacroMeta(id="macro"), templates={"old": TemplateInfo(label="Old")})
    controller = make_controller()
    controller.current_macro = macro
    controller.selected_step = selected_step
    calls = []
    controller.mutate_current_macro = lambda: calls.append("mutate")
    controller.template_service.screen_size_provider = lambda: (800, 600)

    monkeypatch.setattr(home_controller.QFileDialog, "getOpenFileName", lambda *args: (str(source), ""))
    monkeypatch.setattr(home_controller.time, "time", lambda: 700.0)
    monkeypatch.setattr(
        home_controller,
        "template_path",
        lambda macro_id, template_id: tmp_path / "templates" / macro_id / f"{template_id}.png",
    )

    controller.handle_template_pick("old")

    assert not old_file.exists()
    assert (tmp_path / "templates" / "macro" / "700.png").read_bytes() == b"png"
    assert selected_step["templates"] == ["700"]
    assert selected_step["branches"] == {"700": [{"type": "key"}]}
    assert macro.templates["700"].label == "Old"
    assert macro.templates["700"].capture_width == 800
    assert macro.templates["700"].capture_height == 600
    assert calls == ["mutate"]


def test_handle_template_pick_returns_for_missing_state_and_cancel(tmp_path: Path, monkeypatch) -> None:
    controller = make_controller()

    controller.handle_template_pick("old")

    controller.current_macro = Macro(meta=MacroMeta(id="macro"))
    controller.selected_step = {"type": "wait_image", "template": "old"}
    monkeypatch.setattr(home_controller.QFileDialog, "getOpenFileName", lambda *args: ("", ""))
    controller.handle_template_pick("old")


def test_handle_template_pick_updates_single_template_with_generated_label(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "source.png"
    source.write_bytes(b"png")
    selected_step = {"type": "wait_image", "template": "old"}
    macro = Macro(meta=MacroMeta(id="macro"), templates={"old": TemplateInfo(label="")})
    controller = make_controller()
    controller.current_macro = macro
    controller.selected_step = selected_step
    controller.mutate_current_macro = lambda: None
    controller.template_service.screen_size_provider = lambda: (1, 2)

    monkeypatch.setattr(home_controller.QFileDialog, "getOpenFileName", lambda *args: (str(source), ""))
    monkeypatch.setattr(home_controller.time, "time", lambda: 800.0)
    monkeypatch.setattr(
        home_controller,
        "template_path",
        lambda macro_id, template_id: tmp_path / "templates" / macro_id / f"{template_id}.png",
    )

    controller.handle_template_pick("old")

    assert selected_step["template"] == "800"
    assert macro.templates["800"].label == "Template 800"


def test_handle_template_add_ignores_non_if_any_image() -> None:
    controller = make_controller()
    controller.current_macro = Macro(meta=MacroMeta(id="macro"))
    controller.selected_step = {"type": "wait_image", "template": "old"}

    controller.handle_template_add()

    assert controller.current_macro.templates == {}


def test_handle_template_add_pushes_undo_snapshot() -> None:
    selected_step = {"type": "if_any_image", "templates": ["old"], "branches": {}}
    macro = Macro.from_dict(
        {
            "meta": {"id": "macro"},
            "templates": {"old": {"label": "Old"}},
            "steps": [selected_step],
        }
    )
    runner = FakeRunner()
    runner.macro = macro.to_dict()
    controller = make_controller()
    controller.current_macro = macro
    controller.current_runner = cast(Any, runner)
    controller.selected_macro_id = "macro"
    controller.selected_step = selected_step
    controller.mutate_current_macro = lambda: None
    controller.template_service = TemplateService(
        lambda: "new",
        controller.default_template_label,
    )

    controller.handle_template_add()

    assert list(controller.undo_stack[0]["templates"]) == ["old"]
    assert controller.undo_stack[0]["steps"][0]["templates"] == ["old"]
    assert selected_step["templates"] == ["old", "new"]
    assert set(macro.templates) == {"old", "new"}


def test_handle_template_add_keeps_metadata_in_sync_when_ids_collide() -> None:
    selected_step = {"type": "if_any_image", "templates": [], "branches": {}}
    macro = Macro.from_dict(
        {
            "meta": {"id": "macro"},
            "steps": [selected_step],
        }
    )
    runner = FakeRunner()
    runner.macro = macro.to_dict()
    controller = make_controller()
    controller.current_macro = macro
    controller.current_runner = cast(Any, runner)
    controller.selected_macro_id = "macro"
    controller.selected_step = selected_step
    controller.mutate_current_macro = lambda: controller.sync_runner_macro_from_current()
    controller.template_service = TemplateService(
        lambda: "123",
        controller.default_template_label,
    )

    controller.handle_template_add()
    controller.handle_template_add()

    assert selected_step["templates"] == ["123", "124"]
    assert set(macro.templates) == {"123", "124"}


def test_highlight_current_step_selects_visible_item() -> None:
    step = {"type": "key", "key": "a"}
    runner = FakeRunner(running=True)
    runner.current_step_path = (("steps", 0),)
    controller = make_controller()
    controller.current_runner = cast(Any, runner)
    controller.step_tree = StepTree([step])
    tree_item = object()
    calls = []
    center = cast(Any, controller.view).center_panel
    center.item_to_step = {object(): {"type": "other"}, tree_item: step}
    center.step_list.blockSignals = lambda blocked: calls.append(("block", blocked))
    center.step_list.setCurrentItem = lambda item: calls.append(("current", item))
    center.step_list.expandItem = lambda item: calls.append(("expand", item))
    center.step_list.scrollToItem = lambda item: calls.append(("scroll", item))

    controller.highlight_current_step()

    assert calls == [
        ("block", True),
        ("current", tree_item),
        ("expand", tree_item),
        ("scroll", tree_item),
        ("block", False),
    ]


def test_highlight_current_step_returns_for_missing_state() -> None:
    controller = make_controller()
    controller.highlight_current_step()

    controller.current_runner = cast(Any, FakeRunner(running=False))
    controller.highlight_current_step()

    running_runner = FakeRunner(running=True)
    controller.current_runner = cast(Any, running_runner)
    controller.highlight_current_step()

    running_runner.current_step_path = (("steps", 99),)
    controller.step_tree = StepTree([{"type": "key", "key": "a"}])
    controller.highlight_current_step()

    running_runner.current_step_path = (("steps", 0),)
    controller.highlight_current_step()

    assert cast(Any, controller.view).center_panel.step_list.disabled is False


def test_show_about_dialog_executes(monkeypatch) -> None:
    controller = make_controller()
    calls = []

    class FakeAboutDialog:
        def __init__(self, parent, version: str) -> None:
            calls.append(("init", parent, version))

        def exec(self) -> None:
            calls.append(("exec",))

    monkeypatch.setattr(home_controller, "AboutDialog", FakeAboutDialog)

    controller.show_about_dialog()

    assert calls == [("init", cast(Any, controller.view).fake_window, home_controller.__version__), ("exec",)]


def test_select_after_undo_redo_handles_equal_empty_flat_lists() -> None:
    controller = make_controller()
    controller.current_macro = Macro(meta=MacroMeta(id="macro"))
    controller.step_tree = StepTree([])
    calls = []
    controller.show_macro_properties = lambda macro: calls.append(macro)

    controller.select_after_undo_redo([], [])

    assert controller.selected_step is None
    assert calls == [controller.current_macro]


def test_copy_selected_steps_returns_when_no_selected_nodes() -> None:
    controller = make_controller()
    controller.current_macro = Macro(meta=MacroMeta(id="macro"))
    controller.step_tree = StepTree([])

    controller.copy_selected_steps()

    assert controller.step_clipboard is None


def test_paste_steps_adds_missing_template_metadata(tmp_path: Path, monkeypatch) -> None:
    macro = Macro(meta=MacroMeta(id="macro"))
    controller = make_controller()
    controller.current_macro = macro
    controller.current_runner = cast(Any, FakeRunner())
    controller.step_tree = StepTree([])
    controller.step_clipboard = {
        "steps": [{"type": "wait_image", "template": "button"}],
        "templates": {},
        "template_meta": {"button": {"label": "Button", "capture_width": 320}},
    }
    controller.mutate_current_macro = lambda: None
    monkeypatch.setattr(home_controller, "templates_dir", lambda macro_id: tmp_path / "templates" / macro_id)
    monkeypatch.setattr(
        home_controller,
        "template_path",
        lambda macro_id, template_id: tmp_path / "templates" / macro_id / f"{template_id}.png",
    )
    monkeypatch.setattr(home_controller.time, "time", lambda: 902.0)

    controller.paste_steps()

    assert controller.step_tree.steps[0]["template"] == "902"
    assert macro.templates["902"].label == "Button"
    assert macro.templates["902"].capture_width == 320


def test_paste_steps_creates_template_from_clipboard_meta_when_not_in_macro(tmp_path: Path, monkeypatch) -> None:
    macro = Macro(meta=MacroMeta(id="macro"), templates={"existing": TemplateInfo(label="Existing")})
    controller = make_controller()
    controller.current_macro = macro
    controller.current_runner = cast(Any, FakeRunner())
    controller.step_tree = StepTree([])
    controller.step_clipboard = {
        "steps": [{"type": "wait_image", "template": "new_one"}],
        "templates": {},
        "template_meta": {"new_one": {"label": "New", "capture_width": 640, "capture_height": 360}},
    }
    controller.mutate_current_macro = lambda: None
    monkeypatch.setattr(home_controller, "templates_dir", lambda macro_id: tmp_path / "templates" / macro_id)
    monkeypatch.setattr(
        home_controller,
        "template_path",
        lambda macro_id, template_id: tmp_path / "templates" / macro_id / f"{template_id}.png",
    )
    monkeypatch.setattr(home_controller.time, "time", lambda: 903.0)

    controller.paste_steps()

    assert "existing" in macro.templates
    assert macro.templates["existing"].label == "Existing"
    assert controller.step_tree.steps[0]["template"] == "903"
    assert "new_one" not in macro.templates
    assert macro.templates["903"].label == "New"
    assert macro.templates["903"].capture_width == 640
    assert macro.templates["903"].capture_height == 360


def test_handle_macro_rename_cancel_does_not_save(monkeypatch) -> None:
    macro = Macro(meta=MacroMeta(id="alpha", label="Alpha"))
    model = FakeMacroModel(macros={"alpha": macro})
    controller = make_controller()
    controller.macro_model = cast(MacroModel, model)
    monkeypatch.setattr(
        home_controller, "RenameMacroDialog", lambda parent, current_label: FakeDialog(False, "Ignored")
    )

    controller.handle_macro_rename("alpha")

    assert model.saved == []


def test_handle_step_property_changed_returns_without_selected_step() -> None:
    controller = make_controller()

    controller.handle_step_property_changed("skip", "true")

    assert cast(Any, controller.view).statuses == []


def test_handle_step_property_changed_pushes_undo_before_note_change() -> None:
    step = {"type": "key", "key": "a", "note": "old"}
    macro = Macro(meta=MacroMeta(id="macro"))
    runner = FakeRunner()
    runner.macro = {"steps": [{"type": "key", "key": "a", "note": "old"}]}
    controller = make_controller()
    controller.current_macro = macro
    controller.current_runner = cast(Any, runner)
    controller.step_tree = StepTree([step])
    controller.selected_step = step

    controller.handle_step_property_changed("note", "new")

    assert step["note"] == "new"
    assert controller.undo_stack[0]["steps"][0]["note"] == "old"
    assert controller.undo_selection_index_stack == [0]


def test_handle_step_property_changed_skips_undo_when_value_unchanged() -> None:
    step = {"type": "key", "key": "a", "note": "same"}
    macro = Macro(meta=MacroMeta(id="macro"))
    runner = FakeRunner()
    runner.macro = {"steps": [{"type": "key", "key": "a", "note": "same"}]}
    controller = make_controller()
    controller.current_macro = macro
    controller.current_runner = cast(Any, runner)
    controller.step_tree = StepTree([step])
    controller.selected_step = step

    controller.handle_step_property_changed("note", "same")

    assert controller.undo_stack == []
    assert cast(Any, controller.macro_model).saved == []


def test_handle_template_meta_changed_pushes_undo_before_label_change() -> None:
    macro = Macro(meta=MacroMeta(id="macro"), templates={"button": TemplateInfo(label="Old")})
    runner = FakeRunner()
    runner.macro = macro.to_dict()
    controller = make_controller()
    controller.current_macro = macro
    controller.current_runner = cast(Any, runner)
    controller.step_tree = StepTree([])

    controller.handle_template_meta_changed("button", "label", "New")

    assert macro.templates["button"].label == "New"
    assert controller.undo_stack[0]["templates"]["button"]["label"] == "Old"


def test_handle_template_meta_changed_skips_undo_when_label_unchanged() -> None:
    macro = Macro(meta=MacroMeta(id="macro"), templates={"button": TemplateInfo(label="Same")})
    runner = FakeRunner()
    runner.macro = macro.to_dict()
    controller = make_controller()
    controller.current_macro = macro
    controller.current_runner = cast(Any, runner)

    controller.handle_template_meta_changed("button", "label", "Same")

    assert controller.undo_stack == []
    assert cast(Any, controller.macro_model).saved == []


def test_selected_step_flat_index_returns_none_for_missing_step_tree() -> None:
    controller = make_controller()
    controller.selected_step = {"type": "key"}

    assert controller.selected_step_flat_index() is None


def test_sync_macro_steps_from_tree_returns_without_required_state() -> None:
    controller = make_controller()
    controller.sync_macro_steps_from_tree()

    controller.step_tree = StepTree([])
    controller.sync_macro_steps_from_tree()

    assert controller.current_macro is None


def test_refresh_step_tree_marks_selected_branch() -> None:
    parent = {"type": "if_image", "then": []}
    controller = make_controller()
    controller.step_tree = StepTree([parent])
    controller.selected_branch_parent = parent
    controller.selected_branch_key = "then"

    controller.refresh_step_tree()

    assert cast(Any, controller.view).center_panel.selected_branch == (parent, "then")


def test_import_macro_reports_json_decode_error(tmp_path: Path, monkeypatch) -> None:
    archive_path = tmp_path / "macro.zip"
    messages = []
    controller = make_controller()
    monkeypatch.setattr(home_controller.QFileDialog, "getOpenFileName", lambda *args: (str(archive_path), ""))
    monkeypatch.setattr(
        home_controller, "show_message_dialog", lambda parent, title, content: messages.append((title, content))
    )

    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("macro.json", "{bad")

    controller.import_macro()

    assert messages == [("Import failed", "Failed to import macro")]


def test_import_macro_confirms_and_overwrites_existing_template(tmp_path: Path, monkeypatch) -> None:
    archive_path = tmp_path / "macro.zip"
    write_macro_zip(
        archive_path,
        {
            "meta": {"name": "macro"},
            "templates": {},
            "steps": [{"type": "wait_image", "template": "button"}],
        },
        {"templates/button.png": b"new"},
    )
    existing_template = tmp_path / "templates" / "500" / "button.png"
    existing_template.parent.mkdir(parents=True)
    existing_template.write_bytes(b"old")
    model = FakeMacroModel()
    controller = make_controller()
    controller.macro_model = cast(MacroModel, model)
    controller.refresh_macro_list = lambda: None
    monkeypatch.setattr(home_controller.QFileDialog, "getOpenFileName", lambda *args: (str(archive_path), ""))
    monkeypatch.setattr(macro_import_service.time, "time", lambda: 500.0)
    monkeypatch.setattr(home_controller, "macro_path", lambda macro_id: tmp_path / "macros" / f"{macro_id}.json")
    monkeypatch.setattr(home_controller, "templates_dir", lambda macro_id: tmp_path / "templates" / macro_id)
    monkeypatch.setattr(
        home_controller,
        "template_path",
        lambda macro_id, template_id: tmp_path / "templates" / macro_id / f"{template_id}.png",
    )
    monkeypatch.setattr(macro_import_service, "macro_path", lambda macro_id: tmp_path / "macros" / f"{macro_id}.json")
    monkeypatch.setattr(macro_import_service, "templates_dir", lambda macro_id: tmp_path / "templates" / macro_id)
    monkeypatch.setattr(
        macro_import_service,
        "template_path",
        lambda macro_id, template_id: tmp_path / "templates" / macro_id / f"{template_id}.png",
    )
    monkeypatch.setattr(home_controller, "show_confirm_dialog", lambda *args: True)

    controller.import_macro()

    assert existing_template.read_bytes() == b"new"
    assert model.saved[0].meta.id == "500"


def test_duplicate_selected_step_returns_when_duplicate_fails(monkeypatch) -> None:
    step = {"type": "key", "key": "a"}
    controller = make_controller()
    controller.current_macro = Macro(meta=MacroMeta(id="macro"))
    controller.current_runner = cast(Any, FakeRunner())
    controller.step_tree = StepTree([step])
    step_tree = cast(Any, controller.step_tree)
    controller.selected_step_nodes = lambda: [step_tree.root_nodes[0]]
    monkeypatch.setattr(step_tree, "duplicate_nodes", lambda selected: [])

    controller.duplicate_selected_step()

    assert cast(Any, controller.view).statuses == []


def test_duplicate_selected_step_reports_when_clipboard_payload_is_empty(monkeypatch) -> None:
    step = {"type": "key", "key": "a"}
    controller = make_controller()
    controller.current_macro = Macro(meta=MacroMeta(id="macro"))
    controller.current_runner = cast(Any, FakeRunner())
    controller.step_tree = StepTree([step])
    step_tree = cast(Any, controller.step_tree)
    controller.selected_step_nodes = lambda: [step_tree.root_nodes[0]]
    monkeypatch.setattr(step_tree, "get_top_level", lambda selected: [])

    controller.duplicate_selected_step()

    assert cast(Any, controller.view).statuses == ["Select a step first"]


def test_wrap_selected_step_returns_when_top_level_empty(monkeypatch) -> None:
    step = {"type": "key", "key": "a"}
    controller = make_controller()
    controller.current_runner = cast(Any, FakeRunner())
    controller.step_tree = StepTree([step])
    step_tree = cast(Any, controller.step_tree)
    controller.selected_step_nodes = lambda: [step_tree.root_nodes[0]]
    monkeypatch.setattr(step_tree, "get_top_level", lambda selected: [])

    controller.wrap_selected_step_in_repeat()

    assert cast(Any, controller.view).statuses == []


def test_select_macro_list_item_skips_none_items() -> None:
    controller = make_controller()
    macro_list = cast(Any, controller.view).left_panel.macro_list
    macro_list.items = [None, FakeMacroListItem("target")]

    controller.select_macro_list_item("target")

    assert macro_list.current_item is macro_list.items[1]


def test_select_after_undo_redo_uses_previous_fake_flat_node(monkeypatch) -> None:
    controller = make_controller()
    target_node = cast(Any, type("FakeNode", (), {"step": {"type": "key", "key": "a"}})())

    class FakeCurrentTree:
        def __init__(self) -> None:
            self.steps = [{"type": "placeholder"}]

        def flatten(self):
            return [target_node]

    class FakeOldTree:
        def flatten(self):
            return [target_node]

    monkeypatch.setattr(home_controller, "StepTree", lambda steps: FakeOldTree())
    controller.step_tree = cast(Any, FakeCurrentTree())
    calls = []
    controller.refresh_step_tree = lambda: calls.append("refresh")
    controller.show_step_selection = lambda step: calls.append(("show", step))

    controller.select_after_undo_redo([], [])

    assert controller.selected_step == target_node.step
    assert calls == ["refresh", ("show", target_node.step)]


def test_select_after_undo_redo_handles_fake_empty_flatten(monkeypatch) -> None:
    controller = make_controller()
    controller.current_macro = Macro(meta=MacroMeta(id="macro"))

    class FakeCurrentTree:
        def __init__(self) -> None:
            self.steps = [{"type": "placeholder"}]

        def flatten(self):
            return []

    class FakeOldTree:
        def flatten(self):
            return []

    monkeypatch.setattr(home_controller, "StepTree", lambda steps: FakeOldTree())
    controller.step_tree = cast(Any, FakeCurrentTree())
    calls = []
    controller.show_macro_properties = lambda macro: calls.append(macro)

    controller.select_after_undo_redo([], [])

    assert controller.selected_step is None
    assert calls == [controller.current_macro]


def test_handle_macro_meta_changed_returns_without_current_macro() -> None:
    controller = make_controller()

    controller.handle_macro_meta_changed("label", "Name")

    assert cast(Any, controller.macro_model).saved == []


def test_selected_step_flat_index_handles_value_error() -> None:
    controller = make_controller()
    selected_node = object()

    class FakeTree:
        def find_node(self, step):
            return selected_node

        def flatten(self):
            return []

    controller.step_tree = cast(Any, FakeTree())
    controller.selected_step = {"type": "key"}

    assert controller.selected_step_flat_index() is None


def test_selected_step_nodes_returns_empty_without_step_tree() -> None:
    controller = make_controller()

    assert controller.selected_step_nodes() == []
