import json

from loguru import logger

from remaku.models.macro_model import MacroModel, TemplateInfo
from remaku.paths import templates_dir


def migrate_legacy_templates(macro_model: MacroModel) -> tuple[int, int]:
    macros_updated = 0
    files_migrated = 0

    for summary in macro_model.list_macros():
        macro_dir = templates_dir(summary.name)

        if not macro_dir.exists():
            continue

        legacy_files = sorted(macro_dir.glob("*.json"))

        if not legacy_files:
            continue

        macro = macro_model.load(summary.name)

        if macro is None:
            continue

        modified = False

        for json_file in legacy_files:
            try:
                with json_file.open("r", encoding="utf-8") as f:
                    data = json.load(f)
            except (OSError, json.JSONDecodeError):
                continue

            if not isinstance(data, dict):
                continue

            capture_width = data.get("capture_width")
            capture_height = data.get("capture_height")

            if not (isinstance(capture_width, (int, float)) and isinstance(capture_height, (int, float))):
                continue

            capture_width = int(capture_width)
            capture_height = int(capture_height)

            if capture_width <= 0 or capture_height <= 0:
                continue

            template_id = json_file.stem
            entry = macro.templates.get(template_id)

            if entry is None:
                entry = TemplateInfo()
                macro.templates[template_id] = entry

            if entry.capture_width <= 0:
                entry.capture_width = capture_width

            if entry.capture_height <= 0:
                entry.capture_height = capture_height

            json_file.unlink(missing_ok=True)
            files_migrated += 1
            modified = True

        if modified:
            macro_model.save(macro)
            macros_updated += 1

    if files_migrated > 0:
        logger.info(
            "Migrated {} legacy template file(s) across {} macro(s)",
            files_migrated,
            macros_updated,
        )

    return macros_updated, files_migrated
