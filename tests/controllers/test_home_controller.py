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

    def blockSignals(self, blocked: bool) -> None:
        self.blocked_states.append(blocked)

    def count(self) -> int:
        return len(self.items)

    def item(self, index: int) -> FakeMacroListItem:
        return self.items[index]

    def setCurrentItem(self, item: FakeMacroListItem) -> None:
        self.current_item = item


class FakeLeftPanel:
    def __init__(self, macro_ids: list[str]) -> None:
        self.macro_list = FakeMacroList(macro_ids)


class FakeCenterPanel:
    def __init__(self) -> None:
        self.step_tree_items: list[dict] = []
        self.selected_step = None
        self.selected_branch = None

    def set_step_tree(self, items: list[dict], selected_step=None, selected_branch=None) -> None:
        self.step_tree_items = items
        self.selected_step = selected_step
        self.selected_branch = selected_branch


class FakeRightPanel:
    def __init__(self) -> None:
        self.macro_properties: Macro | None = None

    def show_macro_properties(self, macro: Macro | None) -> None:
        self.macro_properties = macro


class FakeButton:
    def __init__(self) -> None:
        self.enabled = True

    def setEnabled(self, enabled: bool) -> None:
        self.enabled = enabled


class FakeToolbar:
    def __init__(self) -> None:
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


def test_parse_step_property_converts_known_types() -> None:
    controller = make_controller()

    assert controller.parse_step_property("skip", "true") is True
    assert controller.parse_step_property("ms", "150") == 150
    assert controller.parse_step_property("threshold", "87") == 0.87
    assert controller.parse_step_property("key", "enter") == "enter"


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
    assert archive_path_names(export_path) == {"macro.json", "templates/button.png"}
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
