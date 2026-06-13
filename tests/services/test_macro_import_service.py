import json
import zipfile
from pathlib import Path
from typing import cast

import pytest

from remaku.models.macro_model import Macro, MacroModel, MacroSummary
from remaku.services import macro_import_service
from remaku.services.macro_import_service import (
    ImportMacroOptions,
    MacroImportError,
    inspect_macro_archive,
    install_macro_archive,
)


class FakeMacroModel:
    def __init__(self) -> None:
        self.saved: list[Macro] = []

    def list_macros(self) -> list[MacroSummary]:
        return []

    def save(self, macro: Macro) -> None:
        self.saved.append(macro)


def write_macro_zip(path: Path, macro_data: dict, files: dict[str, bytes] | None = None) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("macro.json", json.dumps(macro_data))

        for name, content in (files or {}).items():
            archive.writestr(name, content)


def test_inspect_macro_archive_collects_template_refs(tmp_path: Path) -> None:
    archive_path = tmp_path / "macro.zip"
    write_macro_zip(
        archive_path,
        {"meta": {"name": "sample"}, "steps": [{"type": "wait_image", "template": "button"}]},
        {"templates/button.png": b"png"},
    )

    parsed = inspect_macro_archive(archive_path)

    assert parsed.macro_id == "sample"
    assert parsed.template_refs == {"button"}


def test_inspect_macro_archive_reports_missing_template(tmp_path: Path) -> None:
    archive_path = tmp_path / "macro.zip"
    write_macro_zip(
        archive_path,
        {"meta": {"name": "sample"}, "steps": [{"type": "wait_image", "template": "missing"}]},
    )

    with pytest.raises(MacroImportError, match="Missing templates: missing"):
        inspect_macro_archive(archive_path)


def test_install_macro_archive_saves_macro_and_templates(tmp_path: Path, monkeypatch) -> None:
    archive_path = tmp_path / "macro.zip"
    write_macro_zip(
        archive_path,
        {
            "meta": {"name": "sample", "label": "Sample"},
            "templates": {},
            "steps": [{"type": "wait_image", "template": "button"}],
        },
        {
            "templates/button.png": b"png",
            "templates/button.json": json.dumps({"capture_width": 320, "capture_height": 180}).encode(),
        },
    )
    model = FakeMacroModel()
    monkeypatch.setattr(macro_import_service, "macro_path", lambda macro_id: tmp_path / "macros" / f"{macro_id}.json")
    monkeypatch.setattr(macro_import_service, "templates_dir", lambda macro_id: tmp_path / "templates" / macro_id)
    monkeypatch.setattr(
        macro_import_service,
        "template_path",
        lambda macro_id, template_id: tmp_path / "templates" / macro_id / f"{template_id}.png",
    )

    monkeypatch.setattr(macro_import_service.time, "time", lambda: 100.1)

    result = install_macro_archive(archive_path, cast(MacroModel, model), ImportMacroOptions())

    assert result.macro_id == "100"
    assert model.saved[0].meta.id == "100"
    assert model.saved[0].meta.label == "Sample"
    assert model.saved[0].templates["button"].capture_width == 320
    assert (tmp_path / "templates" / "100" / "button.png").read_bytes() == b"png"


def test_install_macro_archive_uses_timestamp_id_when_macro_exists(tmp_path: Path, monkeypatch) -> None:
    archive_path = tmp_path / "macro.zip"
    write_macro_zip(archive_path, {"meta": {"name": "sample"}, "steps": []})
    existing_path = tmp_path / "macros" / "sample.json"
    timestamp_path = tmp_path / "macros" / "100.json"
    next_timestamp_path = tmp_path / "macros" / "101.json"
    existing_path.parent.mkdir(parents=True)
    existing_path.write_text("{}", encoding="utf-8")
    timestamp_path.write_text("{}", encoding="utf-8")
    model = FakeMacroModel()
    monkeypatch.setattr(macro_import_service, "macro_path", lambda macro_id: tmp_path / "macros" / f"{macro_id}.json")
    monkeypatch.setattr(macro_import_service, "templates_dir", lambda macro_id: tmp_path / "templates" / macro_id)
    monkeypatch.setattr(macro_import_service.time, "time", lambda: 100.1)

    result = install_macro_archive(archive_path, cast(MacroModel, model), ImportMacroOptions())

    assert result.macro_id == "101"
    assert result.generated_new_id is True
    assert model.saved[0].meta.id == "101"
    assert not next_timestamp_path.exists()


def test_install_macro_archive_adds_suffix_when_label_exists(tmp_path: Path, monkeypatch) -> None:
    archive_path = tmp_path / "macro.zip"
    write_macro_zip(archive_path, {"meta": {"name": "100", "label": "Buy 22B"}, "steps": []})
    model = FakeMacroModel()
    monkeypatch.setattr(macro_import_service, "macro_path", lambda macro_id: tmp_path / "macros" / f"{macro_id}.json")
    monkeypatch.setattr(macro_import_service, "templates_dir", lambda macro_id: tmp_path / "templates" / macro_id)
    monkeypatch.setattr(
        model,
        "list_macros",
        lambda: [
            MacroSummary(id="200", label="Buy 22B", path="200.json"),
            MacroSummary(id="201", label="Buy 22B (1)", path="201.json"),
        ],
    )
    monkeypatch.setattr(macro_import_service.time, "time", lambda: 300.1)

    result = install_macro_archive(archive_path, cast(MacroModel, model), ImportMacroOptions())

    assert result.macro_id == "300"
    assert model.saved[0].meta.label == "Buy 22B (2)"
