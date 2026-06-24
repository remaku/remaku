import shutil
from collections.abc import Callable
from pathlib import Path

from remaku.models.macro_model import DEFAULT_TEMPLATE_MATCH_MODE, TEMPLATE_MATCH_MODES, Macro, TemplateInfo
from remaku.models.step_tree import StepTree
from remaku.paths import template_path
from remaku.services.template_ids import generate_unique_template_id


class TemplateService:
    def __init__(
        self,
        template_id_provider: Callable[[], str],
        label_provider: Callable[[str], str],
        template_path_provider: Callable[[str, str], Path] | None = None,
        screen_size_provider: Callable[[], tuple[int, int]] | None = None,
    ) -> None:
        self.template_id_provider = template_id_provider
        self.label_provider = label_provider
        self.template_path_provider = template_path_provider or template_path
        self.screen_size_provider = screen_size_provider or (lambda: (0, 0))

    def apply_captured_template(
        self,
        current_macro: Macro,
        selected_step: dict,
        old_template_id: str,
        new_template_id: str,
        width: int,
        height: int,
        step_tree: StepTree | None = None,
    ) -> None:
        self.replace_template(
            current_macro,
            selected_step,
            old_template_id,
            new_template_id,
            width,
            height,
            remove_old_file=True,
            step_tree=step_tree,
        )

    def pick_template(
        self,
        current_macro: Macro,
        selected_step: dict,
        old_template_id: str,
        source_path: str,
        capture_width: int | None = None,
        capture_height: int | None = None,
        step_tree: StepTree | None = None,
    ) -> str:
        if capture_width is None or capture_height is None:
            w, h = self.screen_size_provider()
            if capture_width is None:
                capture_width = w
            if capture_height is None:
                capture_height = h
        new_template_id = self.template_id_provider()
        destination = self.template_path_provider(current_macro.meta.id, new_template_id)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(source_path, destination)
        self.replace_template(
            current_macro,
            selected_step,
            old_template_id,
            new_template_id,
            capture_width,
            capture_height,
            remove_old_file=True,
            step_tree=step_tree,
        )

        return new_template_id

    def replace_template(
        self,
        current_macro: Macro,
        selected_step: dict,
        old_template_id: str,
        new_template_id: str,
        capture_width: int,
        capture_height: int,
        remove_old_file: bool = False,
        step_tree: StepTree | None = None,
    ) -> None:
        old_template_is_owned = self.is_template_owned_by_step(step_tree, selected_step, old_template_id)
        should_remove_old = remove_old_file and old_template_is_owned

        if should_remove_old:
            old_png = self.template_path_provider(current_macro.meta.id, old_template_id)
            if old_png.exists():
                old_png.unlink()

        if old_template_is_owned:
            old_meta = current_macro.templates.pop(old_template_id, None)
        else:
            old_meta = current_macro.templates.get(old_template_id)

        new_meta = current_macro.templates.get(new_template_id)
        if new_meta is None:
            new_meta = TemplateInfo()
            current_macro.templates[new_template_id] = new_meta

        new_meta.capture_width = capture_width
        new_meta.capture_height = capture_height

        if old_meta is not None and old_meta.label and not new_meta.label:
            new_meta.label = old_meta.label
        else:
            new_meta.label = self.label_provider(new_template_id)

        if old_meta is not None:
            new_meta.match_mode = old_meta.match_mode
        elif not new_meta.match_mode:
            new_meta.match_mode = DEFAULT_TEMPLATE_MATCH_MODE

        self.replace_step_template(selected_step, old_template_id, new_template_id)

    def replace_step_template(self, selected_step: dict, old_template_id: str, new_template_id: str) -> None:
        step_type = selected_step.get("type", "")

        if step_type == "if_any_image":
            branches = selected_step.setdefault("branches", {})
            if old_template_id in branches:
                branches[new_template_id] = branches.pop(old_template_id)
            selected_step["templates"] = [
                new_template_id if template_id == old_template_id else template_id
                for template_id in selected_step.get("templates", [])
            ]
            return

        if selected_step.get("template") == old_template_id:
            selected_step["template"] = new_template_id

    def is_template_owned_by_step(self, step_tree: StepTree | None, selected_step: dict, template_id: str) -> bool:
        if step_tree is None:
            return True

        selected_ref_count = self.count_direct_template_refs(selected_step, template_id)
        if selected_ref_count == 0:
            return False

        total_ref_count = 0
        for node in step_tree.flatten():
            total_ref_count += self.count_direct_template_refs(node.step, template_id)

        return total_ref_count <= selected_ref_count

    def count_direct_template_refs(self, step: dict, template_id: str) -> int:
        count = 0

        if step.get("template") == template_id:
            count += 1

        count += sum(1 for item in step.get("templates", []) if item == template_id)

        return count

    def delete_template(self, current_macro: Macro, step_tree: StepTree, template_id: str) -> None:
        png_path = self.template_path_provider(current_macro.meta.id, template_id)
        if png_path.exists():
            png_path.unlink()

        current_macro.templates.pop(template_id, None)

        for node in step_tree.flatten():
            step = node.step

            if step.get("template") == template_id:
                step["template"] = ""

            if "templates" in step:
                step["templates"] = [item for item in step["templates"] if item != template_id]
                if "branches" in step:
                    step["branches"].pop(template_id, None)
                    if not step["branches"]:
                        del step["branches"]

    def generate_unique_template_id(self, current_macro: Macro, selected_step: dict | None = None) -> str:
        return generate_unique_template_id(
            current_macro,
            self.template_id_provider,
            self.template_path_provider,
            selected_step=selected_step,
        )

    def add_template(self, current_macro: Macro, selected_step: dict) -> bool:
        if selected_step.get("type") != "if_any_image":
            return False

        new_template_id = self.generate_unique_template_id(current_macro, selected_step)
        current_macro.templates[new_template_id] = TemplateInfo()
        selected_step.setdefault("templates", []).append(new_template_id)

        return True

    def update_template_meta(self, current_macro: Macro, template_id: str, field: str, value: str) -> bool:
        template_info = current_macro.templates.get(template_id)
        if template_info is None:
            return False

        if field == "label":
            template_info.label = value
        elif field in ("capture_width", "capture_height"):
            try:
                setattr(template_info, field, int(value))
            except ValueError:
                return False
        elif field == "match_mode":
            if value not in TEMPLATE_MATCH_MODES:
                return False

            template_info.match_mode = value
        else:
            return False

        return True
