import copy
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from remaku.models.macro_model import Macro
from remaku.models.step_node import StepNode
from remaku.models.step_tree import StepTree
from remaku.paths import template_path, templates_dir


@dataclass(slots=True)
class PasteStepsResult:
    selected_step: dict | None = None
    changed: bool = False


class ClipboardService:
    def __init__(
        self,
        template_path_provider: Callable[[str, str], Path] | None = None,
        templates_dir_provider: Callable[[str], Path] | None = None,
    ) -> None:
        self.template_path_provider = template_path_provider or template_path
        self.templates_dir_provider = templates_dir_provider or templates_dir

    def collect_template_refs_from_steps(self, steps: list[dict]) -> set[str]:
        return StepTree(copy.deepcopy(steps)).collect_template_refs()

    def copy_selected_steps(
        self, current_macro: Macro, step_tree: StepTree, selected_nodes: list[StepNode]
    ) -> dict | None:
        top_level = step_tree.get_top_level(selected_nodes)
        steps = [copy.deepcopy(node.step) for node in top_level]
        if not steps:
            return None

        refs = self.collect_template_refs_from_steps(steps)
        macro_templates = current_macro.to_dict().get("templates", {})
        template_data = {
            template_id: self.template_path_provider(current_macro.meta.id, template_id).read_bytes()
            for template_id in refs
            if self.template_path_provider(current_macro.meta.id, template_id).exists()
        }
        template_meta = {
            template_id: copy.deepcopy(macro_templates.get(template_id, {}))
            for template_id in refs
            if template_id in macro_templates
        }

        return {
            "steps": steps,
            "templates": template_data,
            "template_meta": template_meta,
        }

    def paste_steps(
        self,
        current_macro: Macro,
        step_tree: StepTree,
        step_clipboard: dict,
        target_node: StepNode | None,
        selected_step: dict | None,
    ) -> PasteStepsResult:
        clipboard_steps = copy.deepcopy(step_clipboard.get("steps", []))
        if not clipboard_steps:
            return PasteStepsResult(selected_step=selected_step)

        inserted_nodes = step_tree.insert_steps_after(target_node, clipboard_steps)
        self.templates_dir_provider(current_macro.meta.id).mkdir(parents=True, exist_ok=True)

        for template_id, data in step_clipboard.get("templates", {}).items():
            destination = self.template_path_provider(current_macro.meta.id, template_id)
            if not destination.exists():
                destination.write_bytes(data)

        for template_id, meta in step_clipboard.get("template_meta", {}).items():
            if template_id not in current_macro.templates:
                current_macro.templates[template_id] = (
                    current_macro.templates.get(template_id)
                    or Macro.from_dict({"meta": {}, "templates": {template_id: meta}, "steps": []}).templates[
                        template_id
                    ]
                )
                continue

            current_meta = current_macro.templates[template_id]
            if not current_meta.label and "label" in meta:
                current_meta.label = str(meta["label"])
            if not current_meta.capture_width and "capture_width" in meta:
                current_meta.capture_width = int(meta["capture_width"])
            if not current_meta.capture_height and "capture_height" in meta:
                current_meta.capture_height = int(meta["capture_height"])

        selected_after_paste = inserted_nodes[0].step if inserted_nodes else selected_step

        return PasteStepsResult(selected_step=selected_after_paste, changed=True)
