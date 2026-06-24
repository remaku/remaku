from collections.abc import Callable
from pathlib import Path

from remaku.models.macro_model import Macro


def generate_unique_template_id(
    current_macro: Macro,
    template_id_provider: Callable[[], str],
    template_path_provider: Callable[[str, str], Path],
    *,
    used_template_ids: set[str] | None = None,
    selected_step: dict | None = None,
) -> str:
    used_ids = set(current_macro.templates)
    if used_template_ids is not None:
        used_ids.update(used_template_ids)

    if selected_step is not None:
        if template_id := selected_step.get("template"):
            used_ids.add(str(template_id))

        used_ids.update(str(template_id) for template_id in selected_step.get("templates", []))

        branches = selected_step.get("branches", {})
        if isinstance(branches, dict):
            used_ids.update(str(template_id) for template_id in branches)

    base_template_id = str(template_id_provider() or "template")
    template_id = base_template_id
    next_timestamp = int(base_template_id) + 1 if base_template_id.isdecimal() else None
    suffix = 1

    while template_id in used_ids or template_path_provider(current_macro.meta.id, template_id).exists():
        if next_timestamp is not None:
            template_id = str(next_timestamp)
            next_timestamp += 1
        else:
            template_id = f"{base_template_id}{suffix}"
            suffix += 1

    return template_id
