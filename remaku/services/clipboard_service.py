import copy
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from remaku.models.macro_model import Macro, TemplateInfo
from remaku.models.step_node import CONTAINER_CHILD_KEYS, StepNode
from remaku.models.step_tree import StepTree
from remaku.paths import template_path, templates_dir
from remaku.services.template_ids import generate_unique_template_id


@dataclass(slots=True)
class PasteStepsResult:
    selected_step: dict | None = None
    changed: bool = False


class ClipboardService:
    def __init__(
        self,
        template_path_provider: Callable[[str, str], Path] | None = None,
        templates_dir_provider: Callable[[str], Path] | None = None,
        template_id_provider: Callable[[], str] | None = None,
        label_provider: Callable[[str], str] | None = None,
    ) -> None:
        self.template_path_provider = template_path_provider or template_path
        self.templates_dir_provider = templates_dir_provider or templates_dir
        self.template_id_provider = template_id_provider or (lambda: str(int(time.time())))
        self.label_provider = label_provider or (lambda template_id: "")

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

        used_template_ids = set(current_macro.templates)
        for step in clipboard_steps:
            self.clone_template_refs_for_step(current_macro, step_clipboard, step, used_template_ids)

        inserted_nodes = step_tree.insert_steps_after(target_node, clipboard_steps)
        self.templates_dir_provider(current_macro.meta.id).mkdir(parents=True, exist_ok=True)

        selected_after_paste = inserted_nodes[0].step if inserted_nodes else selected_step

        return PasteStepsResult(selected_step=selected_after_paste, changed=True)

    def clone_template_refs_for_step(
        self,
        current_macro: Macro,
        step_clipboard: dict,
        step: dict,
        used_template_ids: set[str],
    ) -> None:
        if template_id := str(step.get("template") or ""):
            step["template"] = self.clone_template_ref(current_macro, step_clipboard, template_id, used_template_ids)

        if step.get("type") == "if_any_image":
            self.clone_if_any_image_refs(current_macro, step_clipboard, step, used_template_ids)

        for child_key in CONTAINER_CHILD_KEYS.get(str(step.get("type", "")), []):
            for child_step in step.get(child_key, []):
                self.clone_template_refs_for_step(current_macro, step_clipboard, child_step, used_template_ids)

    def clone_if_any_image_refs(
        self,
        current_macro: Macro,
        step_clipboard: dict,
        step: dict,
        used_template_ids: set[str],
    ) -> None:
        branches = step.get("branches", {})
        if not isinstance(branches, dict):
            branches = {}

        new_branches = {}
        new_templates = []

        for template_id in step.get("templates", []):
            old_template_id = str(template_id)
            new_template_id = self.clone_template_ref(current_macro, step_clipboard, old_template_id, used_template_ids)
            new_templates.append(new_template_id)
            branch_steps = branches.get(old_template_id, [])

            for child_step in branch_steps:
                self.clone_template_refs_for_step(current_macro, step_clipboard, child_step, used_template_ids)

            new_branches[new_template_id] = branch_steps

        step["templates"] = new_templates
        if new_branches:
            step["branches"] = new_branches
        elif "branches" in step:
            del step["branches"]

    def clone_template_ref(
        self,
        current_macro: Macro,
        step_clipboard: dict,
        old_template_id: str,
        used_template_ids: set[str],
    ) -> str:
        new_template_id = generate_unique_template_id(
            current_macro,
            self.template_id_provider,
            self.template_path_provider,
            used_template_ids=used_template_ids,
        )
        used_template_ids.add(new_template_id)

        data = step_clipboard.get("templates", {}).get(old_template_id)
        if data is not None:
            destination = self.template_path_provider(current_macro.meta.id, new_template_id)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)

        meta = step_clipboard.get("template_meta", {}).get(old_template_id)
        if meta is not None:
            current_macro.templates[new_template_id] = Macro.from_dict(
                {"meta": {}, "templates": {new_template_id: meta}, "steps": []}
            ).templates[new_template_id]
        else:
            current_macro.templates[new_template_id] = TemplateInfo(label=self.label_provider(new_template_id))

        return new_template_id
