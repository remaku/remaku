import json
from dataclasses import dataclass
from typing import cast

from remaku.models.macro_model import Macro, MacroMeta, MacroModel, MacroSummary, TemplateInfo
from remaku.services import migration


@dataclass
class FakeMacroModel:
    macros: dict[str, Macro]
    save_calls: int = 0

    def list_macros(self) -> list[MacroSummary]:
        return [
            MacroSummary(id=macro_id, label=macro.meta.label, path=f"{macro_id}.json")
            for macro_id, macro in self.macros.items()
        ]

    def load(self, macro_id: str) -> Macro | None:
        return self.macros.get(macro_id)

    def save(self, macro: Macro) -> None:
        self.save_calls += 1
        self.macros[macro.meta.id] = macro


@dataclass
class MissingLoadMacroModel(FakeMacroModel):
    def list_macros(self) -> list[MacroSummary]:
        return [MacroSummary(id="missing", label="missing", path="missing.json")]


def make_macro(macro_id: str) -> Macro:
    return Macro(meta=MacroMeta(id=macro_id, label=macro_id))


def as_macro_model(model: FakeMacroModel) -> MacroModel:
    return cast(MacroModel, model)


def test_migrate_legacy_templates_updates_macro_and_removes_json(tmp_path, monkeypatch) -> None:
    macro = make_macro("alpha")
    model = FakeMacroModel({"alpha": macro})
    template_dir = tmp_path / "templates" / "alpha"
    template_dir.mkdir(parents=True)
    legacy_file = template_dir / "button.json"
    legacy_file.write_text(json.dumps({"capture_width": 320, "capture_height": 180}), encoding="utf-8")
    monkeypatch.setattr(migration, "templates_dir", lambda macro_id: tmp_path / "templates" / macro_id)

    result = migration.migrate_legacy_templates(as_macro_model(model))

    assert result == (1, 1)
    assert model.save_calls == 1
    assert macro.templates["button"] == TemplateInfo(capture_width=320, capture_height=180)
    assert not legacy_file.exists()


def test_migrate_legacy_templates_preserves_existing_capture_values(tmp_path, monkeypatch) -> None:
    macro = make_macro("alpha")
    macro.templates["button"] = TemplateInfo(label="Button", capture_width=111, capture_height=0)
    model = FakeMacroModel({"alpha": macro})
    template_dir = tmp_path / "templates" / "alpha"
    template_dir.mkdir(parents=True)
    (template_dir / "button.json").write_text(
        json.dumps({"capture_width": 320, "capture_height": 180}), encoding="utf-8"
    )
    monkeypatch.setattr(migration, "templates_dir", lambda macro_id: tmp_path / "templates" / macro_id)

    result = migration.migrate_legacy_templates(as_macro_model(model))

    assert result == (1, 1)
    assert macro.templates["button"].label == "Button"
    assert macro.templates["button"].capture_width == 111
    assert macro.templates["button"].capture_height == 180


def test_migrate_legacy_templates_skips_invalid_files(tmp_path, monkeypatch) -> None:
    macro = make_macro("alpha")
    model = FakeMacroModel({"alpha": macro})
    template_dir = tmp_path / "templates" / "alpha"
    template_dir.mkdir(parents=True)
    (template_dir / "bad-json.json").write_text("not json", encoding="utf-8")
    (template_dir / "bad-list.json").write_text(json.dumps([]), encoding="utf-8")
    (template_dir / "bad-type.json").write_text(
        json.dumps({"capture_width": "320", "capture_height": 180}), encoding="utf-8"
    )
    (template_dir / "bad-size.json").write_text(
        json.dumps({"capture_width": 0, "capture_height": 180}), encoding="utf-8"
    )
    monkeypatch.setattr(migration, "templates_dir", lambda macro_id: tmp_path / "templates" / macro_id)

    result = migration.migrate_legacy_templates(as_macro_model(model))

    assert result == (0, 0)
    assert model.save_calls == 0
    assert macro.templates == {}


def test_migrate_legacy_templates_is_idempotent(tmp_path, monkeypatch) -> None:
    macro = make_macro("alpha")
    model = FakeMacroModel({"alpha": macro})
    template_dir = tmp_path / "templates" / "alpha"
    template_dir.mkdir(parents=True)
    (template_dir / "button.json").write_text(
        json.dumps({"capture_width": 320, "capture_height": 180}), encoding="utf-8"
    )
    monkeypatch.setattr(migration, "templates_dir", lambda macro_id: tmp_path / "templates" / macro_id)

    first = migration.migrate_legacy_templates(as_macro_model(model))
    second = migration.migrate_legacy_templates(as_macro_model(model))

    assert first == (1, 1)
    assert second == (0, 0)
    assert model.save_calls == 1


def test_migrate_legacy_templates_skips_missing_macro_or_template_dir(tmp_path, monkeypatch) -> None:
    model = FakeMacroModel({"alpha": make_macro("alpha")})
    monkeypatch.setattr(migration, "templates_dir", lambda macro_id: tmp_path / "templates" / macro_id)

    assert migration.migrate_legacy_templates(as_macro_model(model)) == (0, 0)


def test_migrate_legacy_templates_skips_when_macro_load_fails(tmp_path, monkeypatch) -> None:
    model = MissingLoadMacroModel({})
    template_dir = tmp_path / "templates" / "missing"
    template_dir.mkdir(parents=True)
    legacy_file = template_dir / "button.json"
    legacy_file.write_text(json.dumps({"capture_width": 320, "capture_height": 180}), encoding="utf-8")
    monkeypatch.setattr(migration, "templates_dir", lambda macro_id: tmp_path / "templates" / macro_id)

    assert migration.migrate_legacy_templates(as_macro_model(model)) == (0, 0)
    assert legacy_file.exists()
