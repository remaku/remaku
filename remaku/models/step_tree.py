import copy

from remaku.models.step_dict import (
    StepDict,
    get_step_branch_names,
    get_step_branches,
    get_step_in_list_index,
    get_step_list,
    get_step_str,
    get_step_str_list,
    get_step_type,
    move_step_in_list,
)
from remaku.models.step_node import CONTAINER_CHILD_KEYS, StepNode


class StepTree:
    def __init__(self, steps: list[StepDict]) -> None:
        self.steps = steps
        self.root_nodes: list[StepNode] = [StepNode(s) for s in steps]

    @classmethod
    def from_macro(cls, macro: StepDict) -> "StepTree":
        return cls(get_step_list(macro, "steps"))

    def flatten(self) -> list[StepNode]:
        result: list[StepNode] = []
        for node in self.root_nodes:
            result.append(node)
            result.extend(node.all_descendants())
        return result

    def find_node(self, step: StepDict) -> StepNode | None:
        for node in self.flatten():
            if node.step is step:
                return node
        return None

    def find_node_by_path(self, path: tuple[tuple[str, int], ...]) -> StepNode | None:
        if not path:
            return None

        if path[0][0] != "steps":
            return None

        nodes = self.root_nodes
        node = None

        for depth, (_, index) in enumerate(path):
            if not 0 <= index < len(nodes):
                return None

            node = nodes[index]

            if depth + 1 < len(path):
                next_branch_key = path[depth + 1][0]
                nodes = node.get_child_list(next_branch_key)

        return node

    def node_at(self, flat_index: int) -> StepNode | None:
        flat = self.flatten()
        if 0 <= flat_index < len(flat):
            return flat[flat_index]
        return None

    def get_top_level(self, nodes: list[StepNode]) -> list[StepNode]:
        return StepNode.filter_top_level(nodes)

    def wrap_in_repeat(self, nodes: list[StepNode]) -> StepNode:
        if not nodes:
            raise ValueError("Cannot wrap an empty list of nodes")

        top_level = self.get_top_level(nodes)
        first = top_level[0]
        first_parent = first.parent

        insert_key = ""
        insert_index = 0
        if first_parent is not None:
            for key, child_list in first_parent.child_lists():
                if first in child_list:
                    insert_key = key
                    insert_index = child_list.index(first)
                    break

        wrapped_steps = [copy.deepcopy(node.step) for node in top_level]

        for node in reversed(top_level):
            node.remove()

        repeat_step: StepDict = {"type": "repeat", "count": 1, "steps": wrapped_steps}
        repeat_node = StepNode(repeat_step)

        if first_parent is not None:
            raw_list = get_step_list(first_parent.step, insert_key)
            repeat_node.parent = first_parent
            first_parent.get_child_list(insert_key).insert(insert_index, repeat_node)
            raw_list.insert(insert_index, repeat_step)
        else:
            positions = []
            for node in top_level:
                try:
                    positions.append(next(index for index, s in enumerate(self.steps) if s is node.step))
                except StopIteration:
                    positions.append(-1)

            for node in top_level:
                try:
                    index = next(i for i, n in enumerate(self.root_nodes) if n is node)
                    self.root_nodes.pop(index)
                    self.steps.pop(index)
                except StopIteration:
                    pass

            first_position = positions[0]
            removed_before = sum(1 for p in positions if 0 <= p < first_position)
            adjusted_index = first_position - removed_before

            self.steps.insert(adjusted_index, repeat_step)
            self.root_nodes.insert(adjusted_index, repeat_node)

        return repeat_node

    def duplicate_nodes(self, nodes: list[StepNode]) -> list[StepNode]:
        top_level = self.get_top_level(nodes)
        duplicates: list[StepNode] = []

        for node in top_level:
            dup_step = copy.deepcopy(node.step)
            dup_node = StepNode(dup_step)

            if node.parent is not None:
                dup_node.insert_after(node)
            else:
                try:
                    index = self.root_nodes.index(node)
                except ValueError:
                    index = len(self.root_nodes)
                self.root_nodes.insert(index + 1, dup_node)
                try:
                    raw_index = next(i for i, s in enumerate(self.steps) if s is node.step)
                except StopIteration:
                    raw_index = len(self.steps)
                self.steps.insert(raw_index + 1, dup_step)

            duplicates.append(dup_node)

        return duplicates

    def add_step(self, target_node: StepNode | None, step: StepDict) -> StepNode:
        if target_node is None:
            self.steps.append(step)
            node = StepNode(step)
            self.root_nodes.append(node)
            return node

        if target_node.step_type == "repeat":
            get_step_list(target_node.step, "steps").append(step)
            target_node.clear_caches()
            return StepNode(step, parent=target_node)

        if target_node.step_type in ("if_image", "if_any_image"):
            get_step_list(target_node.step, "then").append(step)
            target_node.clear_caches()
            return StepNode(step, parent=target_node)

        parent_key = target_node.sibling_key()
        if target_node.parent is not None and parent_key:
            raw_list = get_step_list(target_node.parent.step, parent_key)
            index = next((i for i, s in enumerate(raw_list) if s is target_node.step), len(raw_list))
            raw_list.insert(index + 1, step)
            target_node.parent.clear_caches()
            return StepNode(step, parent=target_node.parent)

        index = next((i for i, s in enumerate(self.steps) if s is target_node.step), len(self.steps))
        self.steps.insert(index + 1, step)
        node = StepNode(step)
        self.root_nodes.insert(index + 1, node)
        return node

    def add_step_to_branch(self, parent_node: StepNode, branch_key: str, step: StepDict) -> StepNode:
        if parent_node.step_type == "if_any_image":
            branches = get_step_branches(parent_node.step)
            branches.setdefault(branch_key, []).append(step)
        else:
            get_step_list(parent_node.step, branch_key).append(step)
        parent_node.clear_caches()
        return StepNode(step, parent=parent_node)

    def add_step_to_any_branch(self, parent_node: StepNode, template_id: str, step: StepDict) -> StepNode:
        branches = get_step_branches(parent_node.step)
        branches.setdefault(template_id, []).append(step)
        parent_node.clear_caches()
        return StepNode(step, parent=parent_node)

    def insert_steps_after(self, target_node: StepNode | None, steps: list[StepDict]) -> list[StepNode]:
        nodes: list[StepNode] = []
        current_target = target_node
        for step in steps:
            node = self.add_step(current_target, step)
            nodes.append(node)
            current_target = node
        return nodes

    def sync_from_tree(self) -> None:
        self.steps[:] = [node.step for node in self.root_nodes]
        for node in self.root_nodes:
            self.sync_node_children(node)

    def sync_node_children(self, node: StepNode) -> None:
        for key, child_list in node.child_lists():
            if node.step_type == "if_any_image":
                get_step_branches(node.step)[key] = [child.step for child in child_list]
            else:
                node.step[key] = [child.step for child in child_list]
            for child in child_list:
                self.sync_node_children(child)

    def collect_template_refs(self) -> set[str]:
        refs: set[str] = set()
        for node in self.flatten():
            if template_id := get_step_str(node.step, "template"):
                refs.add(template_id)
            for template_id in get_step_str_list(node.step, "templates"):
                refs.add(template_id)
        return refs

    def flatten_with_depth(self) -> list[tuple[StepNode, int]]:
        result: list[tuple[StepNode, int]] = []
        for node in self.root_nodes:
            result.append((node, 0))
            self.collect_descendants_with_depth(node, 1, result)
        return result

    def collect_descendants_with_depth(self, node: StepNode, depth: int, out: list[tuple[StepNode, int]]) -> None:
        for _, child_list in node.child_lists():
            for child in child_list:
                out.append((child, depth))
                self.collect_descendants_with_depth(child, depth + 1, out)

    def delete_node(self, node: StepNode) -> None:
        if node.parent is not None:
            node.remove()
        else:
            try:
                index = next(i for i, n in enumerate(self.root_nodes) if n is node)
                self.root_nodes.pop(index)
                self.steps.pop(index)
            except StopIteration:
                pass

    def move_step(self, node: StepNode, direction: int) -> bool:
        if node.parent is None:
            return self.move_root(node, direction)

        source_parent = node.parent
        sibling_key = node.sibling_key()
        source_list = self.get_parent_step_list(source_parent.step, source_parent.step_type, sibling_key)
        source_index = get_step_in_list_index(source_list, node.step)
        if source_index < 0:
            return False

        new_index = source_index + direction

        if 0 <= new_index < len(source_list):
            neighbor_step = source_list[new_index]
            if self.try_move_into_container(source_list, source_index, neighbor_step, direction):
                source_parent.clear_caches()
                return True

            move_step_in_list(source_list, source_index, new_index)
            source_parent.clear_caches()
            return True

        parent_step = source_parent.step
        parent_type = get_step_type(parent_step)
        target_sibling_key = self.find_sibling_key_raw(parent_type, sibling_key, direction, parent_step)
        if target_sibling_key is not None:
            dest_list = self.get_parent_step_list(parent_step, parent_type, target_sibling_key)
            self.move_between_lists(source_list, source_index, dest_list, append=direction == -1)
            source_parent.clear_caches()
            return True

        grandparent = source_parent.parent
        if grandparent is not None:
            parent_key = source_parent.sibling_key()
            parent_list = self.get_parent_step_list(grandparent.step, grandparent.step_type, parent_key)
            parent_index = get_step_in_list_index(parent_list, source_parent.step)
            if parent_index < 0:
                return False

            insert_at = parent_index if direction == -1 else parent_index + 1
            self.move_between_lists(source_list, source_index, parent_list, insert_at=insert_at)
            source_parent.clear_caches()
            grandparent.clear_caches()
            return True

        parent_in_roots = self.root_nodes.index(source_parent) if source_parent in self.root_nodes else -1
        if parent_in_roots < 0:
            return False

        source_list.pop(source_index)
        insert_at = parent_in_roots if direction == -1 else parent_in_roots + 1
        self.root_nodes.insert(insert_at, node)
        self.steps.insert(insert_at, node.step)
        source_parent.clear_caches()
        node.parent = None
        return True

    def move_root(self, node: StepNode, direction: int) -> bool:
        try:
            index = self.root_nodes.index(node)
        except ValueError:
            return False

        new_index = index + direction

        if 0 <= new_index < len(self.root_nodes):
            neighbor = self.root_nodes[new_index]
            if self.try_move_into_container(self.steps, index, neighbor.step, direction):
                self.root_nodes.pop(index)
                node.parent = neighbor
                neighbor.clear_caches()
                return True

            self.root_nodes[index], self.root_nodes[new_index] = self.root_nodes[new_index], self.root_nodes[index]
            move_step_in_list(self.steps, index, new_index)
            return True

        return False

    def can_move(self, node: StepNode, direction: int) -> bool:
        if node.parent is None:
            return self.can_move_root(node, direction)

        source_parent = node.parent
        sibling_key = node.sibling_key()
        source_list = self.get_parent_step_list(source_parent.step, source_parent.step_type, sibling_key)
        source_index = get_step_in_list_index(source_list, node.step)
        if source_index < 0:
            return False

        new_index = source_index + direction
        if 0 <= new_index < len(source_list):
            return True

        parent_type = get_step_type(source_parent.step)
        target_sibling_key = self.find_sibling_key_raw(parent_type, sibling_key, direction, source_parent.step)
        if target_sibling_key is not None:
            return True

        grandparent = source_parent.parent
        if grandparent is not None:
            parent_key = source_parent.sibling_key()
            parent_list = self.get_parent_step_list(grandparent.step, grandparent.step_type, parent_key)
            parent_index = get_step_in_list_index(parent_list, source_parent.step)
            if parent_index >= 0:
                return True

        return source_parent in self.root_nodes

    def can_move_root(self, node: StepNode, direction: int) -> bool:
        try:
            index = self.root_nodes.index(node)
        except ValueError:
            return False

        new_index = index + direction
        return 0 <= new_index < len(self.root_nodes)

    @staticmethod
    def try_move_into_container(
        source_list: list[StepDict], source_index: int, neighbor_step: StepDict, direction: int
    ) -> bool:
        neighbor_type = get_step_type(neighbor_step)
        keys = CONTAINER_CHILD_KEYS.get(neighbor_type, [])

        if neighbor_type == "if_any_image":
            branch_names = get_step_branch_names(neighbor_step)
            if not branch_names:
                return False
            child_key = branch_names[0] if direction == 1 else branch_names[-1]
            dest_list = get_step_branches(neighbor_step)[child_key]
        elif keys:
            child_key = keys[0] if direction == 1 else keys[-1]
            dest_list = get_step_list(neighbor_step, child_key)
        else:
            return False

        step = source_list.pop(source_index)
        if direction == -1:
            dest_list.append(step)
        else:
            dest_list.insert(0, step)

        return True

    @staticmethod
    def move_between_lists(
        source_list: list[StepDict],
        source_index: int,
        dest_list: list[StepDict],
        *,
        append: bool = False,
        insert_at: int | None = None,
    ) -> None:
        step = source_list.pop(source_index)
        if append:
            dest_list.append(step)
            return

        if insert_at is None:
            dest_list.insert(0, step)
            return

        dest_list.insert(insert_at, step)

    @staticmethod
    def find_sibling_key_raw(
        step_type: str, current_key: str, direction: int, step: StepDict | None = None
    ) -> str | None:
        if step_type == "if_any_image" and step is not None:
            keys = get_step_branch_names(step)
            try:
                index = keys.index(current_key)
            except ValueError:
                return None
            next_index = index + direction
            if 0 <= next_index < len(keys):
                return keys[next_index]
            return None

        keys = CONTAINER_CHILD_KEYS.get(step_type, [])
        try:
            index = keys.index(current_key)
        except ValueError:
            return None
        next_index = index + direction
        if 0 <= next_index < len(keys):
            return keys[next_index]
        return None

    @staticmethod
    def get_parent_step_list(parent_step: StepDict, parent_type: str, key: str) -> list[StepDict]:
        if parent_type == "if_any_image":
            return get_step_branches(parent_step).setdefault(key, [])
        return get_step_list(parent_step, key)

    def sync_parent_raw(self, node: StepNode) -> None:
        if node.parent is None:
            return
        parent = node.parent
        for key in CONTAINER_CHILD_KEYS.get(parent.step_type, []):
            cache_key = f"cached_children_{key}"
            cached = getattr(parent, cache_key, None)
            if cached is not None:
                parent.step[key] = [n.step for n in cached]
        if parent.step_type == "if_any_image":
            cached_branches = getattr(parent, "cached_branches", None)
            if cached_branches is not None:
                for branch_name, nodes in cached_branches.items():
                    get_step_branches(parent.step)[branch_name] = [n.step for n in nodes]
        parent.clear_caches()
