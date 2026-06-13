import json
import zipfile
from pathlib import Path
from typing import Any, cast

import pytest

from remaku.models.macro_model import Macro, MacroModel, MacroSummary
from remaku.services import macro_import_service
from remaku.services.macro_import_service import (
    ImportMacroOptions,
    MacroImportError,
    ParsedMacroArchive,
    ensure_template_metadata,
    existing_macro_labels,
    inspect_macro_archive,
    install_macro_archive,
    normalize_duplicate_label,
)


class FakeMacroModel:
    def __init__(self) -> None:
        self.saved: list[Macro] = []

    def list_macros(self) -> list[MacroSummary]:
        return []

    def save(self, macro: Macro) -> None:
        self.saved.append(macro)


def write_macro_zip(path: Path, macro_data: Any, files: dict[str, bytes] | None = None) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("macro.json", json.dumps(macro_data))

        for name, content in (files or {}).items():
            archive.writestr(name, content)


def raise_os_error(path: Path, mode: str) -> None:
    raise OSError("denied")


def raise_bad_zip(path: Path, mode: str) -> None:
    raise zipfile.BadZipFile("bad")


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


def test_inspect_macro_archive_reports_invalid_shapes(tmp_path: Path) -> None:
    archive_path = tmp_path / "macro.zip"

    write_macro_zip(archive_path, [])

    with pytest.raises(MacroImportError, match="Invalid macro data"):
        inspect_macro_archive(archive_path)

    write_macro_zip(archive_path, {"meta": [], "steps": []})

    with pytest.raises(MacroImportError, match="Macro metadata is invalid"):
        inspect_macro_archive(archive_path)

    write_macro_zip(archive_path, {"meta": {}, "steps": []})

    with pytest.raises(MacroImportError, match="Macro metadata is invalid"):
        inspect_macro_archive(archive_path)

    write_macro_zip(archive_path, {"meta": {"name": "sample"}, "steps": {}})

    with pytest.raises(MacroImportError, match="Macro steps are invalid"):
        inspect_macro_archive(archive_path)


def test_inspect_macro_archive_reports_missing_macro_json_and_bad_zip(tmp_path: Path) -> None:
    missing_macro_path = tmp_path / "missing_macro.zip"

    with zipfile.ZipFile(missing_macro_path, "w") as archive:
        archive.writestr("notes.txt", "missing")

    with pytest.raises(MacroImportError, match=r"macro\.json is missing"):
        inspect_macro_archive(missing_macro_path)

    invalid_json_path = tmp_path / "invalid_json.zip"

    with zipfile.ZipFile(invalid_json_path, "w") as archive:
        archive.writestr("macro.json", "{")

    with pytest.raises(MacroImportError, match="Failed to import macro"):
        inspect_macro_archive(invalid_json_path)

    bad_zip_path = tmp_path / "bad.zip"
    bad_zip_path.write_text("not zip", encoding="utf-8")

    with pytest.raises(MacroImportError, match="Invalid zip file"):
        inspect_macro_archive(bad_zip_path)


def test_install_macro_archive_handles_template_metadata_edge_cases(tmp_path: Path, monkeypatch) -> None:
    archive_path = tmp_path / "macro.zip"
    write_macro_zip(
        archive_path,
        {
            "meta": {"name": "sample", "label": "Sample"},
            "templates": {"button": "legacy"},
            "steps": [
                {"type": "wait_image", "template": "button"},
                {"type": "wait_image", "template": "plain"},
                {"type": "wait_image", "template": "bad"},
            ],
        },
        {
            "templates/button.png": b"button-new",
            "templates/button.json": json.dumps({"capture_width": 320}).encode(),
            "templates/plain.png": b"plain",
            "templates/bad.png": b"bad",
            "templates/bad.json": b"not json",
        },
    )
    model = FakeMacroModel()
    template_root = tmp_path / "templates"
    existing_button = template_root / "100" / "button.png"
    existing_button.parent.mkdir(parents=True)
    existing_button.write_bytes(b"button-old")
    monkeypatch.setattr(macro_import_service, "macro_path", lambda macro_id: tmp_path / "macros" / f"{macro_id}.json")
    monkeypatch.setattr(macro_import_service, "templates_dir", lambda macro_id: template_root / macro_id)
    monkeypatch.setattr(
        macro_import_service,
        "template_path",
        lambda macro_id, template_id: template_root / macro_id / f"{template_id}.png",
    )
    monkeypatch.setattr(macro_import_service.time, "time", lambda: 100.1)

    result = install_macro_archive(
        archive_path,
        cast(MacroModel, model),
        ImportMacroOptions(overwrite_template_conflicts=True),
    )

    assert result.template_refs == {"button", "plain", "bad"}
    assert existing_button.read_bytes() == b"button-new"
    assert model.saved[0].templates["button"].capture_width == 320
    assert (template_root / "100" / "plain.png").read_bytes() == b"plain"


def test_install_macro_archive_reports_write_errors(tmp_path: Path, monkeypatch) -> None:
    archive_path = tmp_path / "macro.zip"
    model = FakeMacroModel()
    parsed = ParsedMacroArchive(
        raw_macro={"meta": {"name": "sample"}, "steps": [{"type": "wait_image", "template": "button"}]},
        macro_id="sample",
        template_refs={"button"},
        archive_names={"macro.json", "templates/button.png"},
    )
    monkeypatch.setattr(macro_import_service, "inspect_macro_archive", lambda path: parsed)
    monkeypatch.setattr(macro_import_service, "macro_path", lambda macro_id: tmp_path / "macros" / f"{macro_id}.json")
    monkeypatch.setattr(macro_import_service, "templates_dir", lambda macro_id: tmp_path / "templates" / macro_id)
    monkeypatch.setattr(macro_import_service.time, "time", lambda: 100.1)
    monkeypatch.setattr(macro_import_service.zipfile, "ZipFile", raise_os_error)

    with pytest.raises(MacroImportError, match="Failed to import macro"):
        install_macro_archive(archive_path, cast(MacroModel, model), ImportMacroOptions())


def test_install_macro_archive_reports_bad_zip_during_write(tmp_path: Path, monkeypatch) -> None:
    archive_path = tmp_path / "macro.zip"
    model = FakeMacroModel()
    parsed = ParsedMacroArchive(
        raw_macro={"meta": {"name": "sample"}, "steps": [{"type": "wait_image", "template": "button"}]},
        macro_id="sample",
        template_refs={"button"},
        archive_names={"macro.json", "templates/button.png"},
    )
    monkeypatch.setattr(macro_import_service, "inspect_macro_archive", lambda path: parsed)
    monkeypatch.setattr(macro_import_service, "macro_path", lambda macro_id: tmp_path / "macros" / f"{macro_id}.json")
    monkeypatch.setattr(macro_import_service.time, "time", lambda: 100.1)
    monkeypatch.setattr(macro_import_service.zipfile, "ZipFile", raise_bad_zip)

    with pytest.raises(MacroImportError, match="Invalid zip file"):
        install_macro_archive(archive_path, cast(MacroModel, model), ImportMacroOptions())


def test_normalize_duplicate_label_and_existing_labels(monkeypatch) -> None:
    model = FakeMacroModel()
    monkeypatch.setattr(
        model,
        "list_macros",
        lambda: [
            MacroSummary(id="1", label="Buy 22B", path="1.json"),
            MacroSummary(id="2", label="", path="2.json"),
        ],
    )

    assert normalize_duplicate_label("Buy 22B (2)") == "Buy 22B"
    assert normalize_duplicate_label("Plain") == "Plain"
    assert existing_macro_labels(cast(MacroModel, model)) == {"Buy 22B", "2"}
    assert existing_macro_labels(cast(MacroModel, model), exclude_macro_id="1") == {"2"}


def test_ensure_template_metadata_creates_dict() -> None:
    raw_macro = {"templates": "invalid"}

    templates = ensure_template_metadata(raw_macro)

    assert templates == {}
    assert raw_macro["templates"] == {}
