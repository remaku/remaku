import json
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from remaku.models.macro_model import Macro, MacroModel
from remaku.models.step_tree import StepTree
from remaku.paths import macro_path, template_path, templates_dir


@dataclass(slots=True)
class ParsedMacroArchive:
    raw_macro: dict
    macro_id: str
    template_refs: set[str] = field(default_factory=set)
    archive_names: set[str] = field(default_factory=set)


@dataclass(slots=True)
class ImportMacroOptions:
    overwrite_template_conflicts: bool = False


@dataclass(slots=True)
class ImportMacroResult:
    macro_id: str
    label: str
    template_refs: set[str]
    generated_new_id: bool = False


class MacroImportError(ValueError):
    pass


def resolve_timestamp_macro_id() -> str:
    candidate = int(time.time())

    while macro_path(str(candidate)).exists():
        candidate += 1

    return str(candidate)


def normalize_duplicate_label(label: str) -> str:
    if label.endswith(")") and "(" in label:
        prefix, _, suffix = label.rpartition("(")
        if suffix[:-1].isdigit():
            return prefix.rstrip()

    return label


def existing_macro_labels(macro_model: MacroModel, exclude_macro_id: str = "") -> set[str]:
    labels: set[str] = set()

    for summary in macro_model.list_macros():
        if summary.id == exclude_macro_id:
            continue

        labels.add(summary.label or summary.id)

    return labels


def resolve_import_macro_label(label: str, macro_model: MacroModel, macro_id: str) -> str:
    base_label = normalize_duplicate_label(label or macro_id)
    labels = existing_macro_labels(macro_model, macro_id)

    if base_label not in labels:
        return base_label

    index = 1
    while f"{base_label} ({index})" in labels:
        index += 1

    return f"{base_label} ({index})"


def inspect_macro_archive(path: Path) -> ParsedMacroArchive:
    try:
        with zipfile.ZipFile(path, "r") as archive:
            archive_names = set(archive.namelist())
            if "macro.json" not in archive_names:
                raise MacroImportError("macro.json is missing from the archive")

            raw_macro = json.loads(archive.read("macro.json"))
            if not isinstance(raw_macro, dict):
                raise MacroImportError("Invalid macro data")

            meta_data = raw_macro.get("meta")
            if not isinstance(meta_data, dict):
                raise MacroImportError("Macro metadata is invalid")

            raw_macro_id = meta_data.get("id", meta_data.get("name"))
            if not raw_macro_id:
                raise MacroImportError("Macro metadata is invalid")

            if not isinstance(raw_macro.get("steps"), list):
                raise MacroImportError("Macro steps are invalid")

            refs = StepTree(raw_macro["steps"]).collect_template_refs()
            missing_templates = sorted(
                template_id for template_id in refs if f"templates/{template_id}.png" not in archive_names
            )

            if missing_templates:
                raise MacroImportError(f"Missing templates: {', '.join(missing_templates)}")

            return ParsedMacroArchive(
                raw_macro=raw_macro,
                macro_id=str(raw_macro_id),
                template_refs=refs,
                archive_names=archive_names,
            )
    except zipfile.BadZipFile as error:
        raise MacroImportError("Invalid zip file") from error
    except (OSError, json.JSONDecodeError, ValueError) as error:
        if isinstance(error, MacroImportError):
            raise

        raise MacroImportError("Failed to import macro") from error


def find_template_conflicts(macro_id: str, refs: set[str]) -> list[str]:
    return sorted(template_id for template_id in refs if template_path(macro_id, template_id).exists())


def resolve_import_macro_id() -> str:
    return resolve_timestamp_macro_id()


def ensure_template_metadata(raw_macro: dict) -> dict:
    raw_templates = raw_macro.setdefault("templates", {})
    if not isinstance(raw_templates, dict):
        raw_templates = {}
        raw_macro["templates"] = raw_templates

    return raw_templates


def merge_legacy_template_metadata(raw_macro: dict, template_id: str, legacy_meta: dict) -> None:
    raw_templates = ensure_template_metadata(raw_macro)

    entry = raw_templates.get(template_id, {"label": template_id})
    if not isinstance(entry, dict):
        entry = {"label": template_id}

    for key in ("capture_width", "capture_height"):
        if key in legacy_meta and key not in entry:
            entry[key] = legacy_meta[key]

    raw_templates[template_id] = entry


def write_archive_templates(
    archive: zipfile.ZipFile,
    parsed: ParsedMacroArchive,
    macro_id: str,
    overwrite_template_conflicts: bool,
) -> None:
    conflicts = set(find_template_conflicts(macro_id, parsed.template_refs))
    template_dir = templates_dir(macro_id)
    template_dir.mkdir(parents=True, exist_ok=True)

    for template_id in parsed.template_refs:
        png_destination = template_dir / f"{template_id}.png"
        if not png_destination.exists() or (overwrite_template_conflicts and template_id in conflicts):
            png_destination.write_bytes(archive.read(f"templates/{template_id}.png"))

        legacy_meta_path = f"templates/{template_id}.json"
        if legacy_meta_path not in parsed.archive_names:
            continue

        try:
            legacy_meta = json.loads(archive.read(legacy_meta_path))
        except (OSError, ValueError):
            continue

        if isinstance(legacy_meta, dict):
            merge_legacy_template_metadata(parsed.raw_macro, template_id, legacy_meta)


def install_macro_archive(path: Path, macro_model: MacroModel, options: ImportMacroOptions) -> ImportMacroResult:
    parsed = inspect_macro_archive(path)
    imported_macro_id = resolve_import_macro_id()
    generated_new_id = imported_macro_id != parsed.macro_id
    parsed.raw_macro["meta"]["name"] = imported_macro_id
    ensure_template_metadata(parsed.raw_macro)

    try:
        with zipfile.ZipFile(path, "r") as archive:
            write_archive_templates(
                archive,
                parsed,
                imported_macro_id,
                options.overwrite_template_conflicts,
            )
    except zipfile.BadZipFile as error:
        raise MacroImportError("Invalid zip file") from error
    except OSError as error:
        raise MacroImportError("Failed to import macro") from error

    imported_macro = Macro.from_dict(parsed.raw_macro)
    imported_macro.meta.id = imported_macro_id
    if not imported_macro.meta.label:
        imported_macro.meta.label = imported_macro_id
    imported_macro.meta.label = resolve_import_macro_label(
        imported_macro.meta.label,
        macro_model,
        imported_macro_id,
    )

    macro_model.save(imported_macro)

    return ImportMacroResult(
        macro_id=imported_macro_id,
        label=imported_macro.meta.label,
        template_refs=parsed.template_refs,
        generated_new_id=generated_new_id,
    )
