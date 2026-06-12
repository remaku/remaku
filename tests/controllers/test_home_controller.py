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
from remaku.services.engine import Status


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

    def showNormal(self) -> None:
        self.show_normal_calls += 1

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

    def show_macro_properties(self, macro: Macro | None) -> None:
        self.macro_properties = macro

    def show_step_properties(self, *args) -> None:
        self.step_properties = args

    def show_branch_properties(self, *args) -> None:
        self.branch_properties = args


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
        self.add_button = FakeButton()
        self.delete_button = FakeButton()
        self.move_up_button = FakeButton()
        self.move_down_button = FakeButton()
        self.undo_button = FakeButton()
        self.redo_button = FakeButton()


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
        self.start_calls = 0
        self.stop_calls = 0

    def is_running(self) -> bool:
        return self.running

    def start(self) -> None:
        self.start_calls += 1
        self.running = True

    def stop(self) -> None:
        self.stop_calls += 1
        self.running = False

    def get_status(self) -> Status:
        return self.status


def make_controller() -> HomeController:
    controller = cast(Any, HomeController.__new__(HomeController))
    controller.current_macro = None
    controller.current_runner = None
    controller.selected_macro_id = ""
    controller.selected_step = None
    controller.selected_branch_parent = None
    controller.selected_branch_key = ""
    controller.step_tree = None
    controller.view = FakeView()
    controller.macro_model = cast(MacroModel, FakeMacroModel())
    controller.editing_locked = False
    controller.undo_stacks = {}
    controller.redo_stacks = {}
    controller.undo_selection_indexes = {}
    controller.redo_selection_indexes = {}
    controller.step_clipboard = None
    return cast(HomeController, controller)


class FakeUser32:
    def __init__(self, register_result: bool = True) -> None:
        self.register_result = register_result
        self.register_calls: list[tuple[int, int, int, int]] = []
        self.unregister_calls: list[tuple[int, int]] = []

    def RegisterHotKey(self, hwnd: int, hotkey_id: int, modifiers: int, vk: int) -> bool:
        self.register_calls.append((hwnd, hotkey_id, modifiers, vk))
        return self.register_result

    def UnregisterHotKey(self, hwnd: int, hotkey_id: int) -> None:
        self.unregister_calls.append((hwnd, hotkey_id))

    def VkKeyScanW(self, codepoint: int) -> int:
        return codepoint + 0x100


class FakeWindll:
    def __init__(self, user32: FakeUser32) -> None:
        self.user32 = user32


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
    user32 = FakeUser32()
    fake_config = FakeConfigModel()
    controller_view = FakeView()
    controller_view.center_panel.step_list.itemSelectionChanged = FakeSignal()
    model = FakeMacroModel()
    shortcuts = []

    def make_shortcut(key_sequence, parent) -> FakeShortcut:
        shortcut = FakeShortcut(key_sequence, parent)
        shortcuts.append(shortcut)
        return shortcut

    monkeypatch.setattr(home_controller.ctypes, "windll", FakeWindll(user32))
    monkeypatch.setattr(home_controller, "config_model", fake_config)
    monkeypatch.setattr(home_controller, "QShortcut", make_shortcut)

    controller = HomeController(cast(Any, controller_view), cast(MacroModel, model))

    assert controller.view is controller_view
    assert controller.macro_model is model
    assert controller.selected_macro_id == ""
    assert controller.actions["run"] == controller.run_current_macro
    assert controller.actions["settings"] == controller.open_settings
    assert len(shortcuts) == 12
    assert len(controller.editing_shortcuts) == 10
    assert controller_view.toolbar.undo_button.enabled is False
    assert controller_view.toolbar.redo_button.enabled is False
    assert controller_view.center_panel.step_tree_items == []
    assert user32.register_calls == []


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

    assert controller.parse_hotkey("CTRL+Alt+enter") == (0x0002 | 0x0001, 0x0D)
    assert controller.parse_hotkey("shift+f1") == (0x0004, 0x70)


def test_key_to_vk_uses_vk_key_scan_for_single_character(monkeypatch) -> None:
    user32 = FakeUser32()
    monkeypatch.setattr(home_controller.ctypes, "windll", FakeWindll(user32))
    controller = make_controller()

    assert controller.key_to_vk("a") == ord("a")


def test_register_hotkeys_unregisters_previous_and_skips_invalid(monkeypatch) -> None:
    user32 = FakeUser32(register_result=True)
    monkeypatch.setattr(home_controller.ctypes, "windll", FakeWindll(user32))
    macros = {
        "enabled": Macro(meta=MacroMeta(id="enabled", label="Enabled", hotkey="ctrl+f1", enabled=True)),
        "disabled": Macro(meta=MacroMeta(id="disabled", label="Disabled", hotkey="ctrl+f2", enabled=False)),
        "invalid": Macro(meta=MacroMeta(id="invalid", label="Invalid", hotkey="ctrl+unknown", enabled=True)),
        "empty": Macro(meta=MacroMeta(id="empty", label="Empty", hotkey="", enabled=True)),
    }
    model = FakeMacroModel(macros=macros)
    controller = make_controller()
    controller.macro_model = cast(MacroModel, model)
    controller.hotkey_ids = [0xBF99]
    controller.hotkey_map = {0xBF99: "old"}

    controller.register_hotkeys()

    assert user32.unregister_calls == [(99, 0xBF99)]
    assert user32.register_calls == [(99, 0xBF02, 0x0002, 0x70)]
    assert controller.hotkey_ids == [0xBF02]
    assert controller.hotkey_map == {0xBF02: "enabled"}


def test_register_hotkeys_does_not_store_failed_registration(monkeypatch) -> None:
    user32 = FakeUser32(register_result=False)
    monkeypatch.setattr(home_controller.ctypes, "windll", FakeWindll(user32))
    model = FakeMacroModel(macros={"macro": Macro(meta=MacroMeta(id="macro", label="Macro", hotkey="ctrl+f1"))})
    controller = make_controller()
    controller.macro_model = cast(MacroModel, model)
    controller.hotkey_ids = []
    controller.hotkey_map = {}

    controller.register_hotkeys()

    assert user32.register_calls == [(99, 0xBF00, 0x0002, 0x70)]
    assert controller.hotkey_ids == []
    assert controller.hotkey_map == {}


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
    controller.hotkey_map = {0xBF00: "target"}
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

    assert calls == ["settings"]


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
    controller.restore_macro_state = lambda macro_dict, selection_index=None: restored.append(
        (macro_dict, selection_index)
    )
    controller.selected_step_flat_index = lambda: 2

    controller.undo()
    controller.redo()

    assert restored == [
        ({"steps": [{"type": "key", "key": "undo"}]}, 0),
        ({"steps": [{"type": "key", "key": "current"}]}, 2),
    ]


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


def test_handle_macro_running_changed_reports_terminal_status() -> None:
    controller = make_controller()
    calls = []
    controller.set_editing_locked = lambda locked: calls.append(("locked", locked))
    controller.current_runner = cast(Any, FakeRunner(status=Status(last_reason="done")))

    controller.handle_macro_running_changed(False)

    assert calls == [("locked", False)]
    assert cast(Any, controller.view).statuses == ["Done: Runner"]


def test_parse_step_property_converts_known_types() -> None:
    controller = make_controller()

    assert controller.parse_step_property("skip", "true") is True
    assert controller.parse_step_property("ms", "150") == 150
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
    controller.handle_macro_meta_changed("label", "Renamed")

    assert macro.meta.enabled is True
    assert macro.meta.label == "Renamed"
    assert model.saved == [macro, macro]
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

    assert controller.step_tree.steps == [{"type": "delay", "ms": 0, "skip": False, "note": ""}]
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


def test_resolve_timestamp_macro_id_increments_until_unused(monkeypatch) -> None:
    controller = make_controller()
    controller.macro_model = cast(MacroModel, FakeMacroModel({"100", "101"}))
    monkeypatch.setattr(home_controller.time, "time", lambda: 100.1)

    assert controller.resolve_timestamp_macro_id() == "102"


def test_add_step_factory_returns_supported_steps() -> None:
    controller = make_controller()

    assert controller.add_step_factory("key") is not None
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
    monkeypatch.setattr(home_controller, "macro_path", lambda macro_id: tmp_path / "macros" / f"{macro_id}.json")
    monkeypatch.setattr(home_controller, "templates_dir", lambda macro_id: tmp_path / "templates" / macro_id)
    monkeypatch.setattr(
        home_controller,
        "template_path",
        lambda macro_id, template_id: tmp_path / "templates" / macro_id / f"{template_id}.png",
    )
    monkeypatch.setattr(home_controller, "config_model", fake_config)

    controller.import_macro()

    assert model.saved[0].meta.id == "imported"
    assert model.saved[0].templates["button"].capture_width == 320
    assert (tmp_path / "templates" / "imported" / "button.png").read_bytes() == b"png"
    assert fake_config.config.general.macro_order == ["imported"]
    assert fake_config.save_calls == 1
    assert controller.selected_macro_id == "imported"
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
