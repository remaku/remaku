import copy

from remaku.models.step_dict import (
    StepDict,
    get_step_branch_names,
    get_step_branches,
    get_step_list,
    get_step_str,
    get_step_str_list,
    get_step_type,
)
from remaku.models.step_node import CONTAINER_CHILD_KEYS, StepNode


class StepTree:
    def __init__(self, steps: list[StepDict]) -> None:
        self.root_nodes: list[StepNode] = [StepNode(step) for step in steps]

    @property
    def steps(self) -> list[StepDict]:
        for node in self.root_nodes:
            node.serialize_children()

        return [node.step for node in self.root_nodes]

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
        siblings = self.sibling_list(first)
        indexed_nodes = sorted(
            ((siblings.index(node), node) for node in top_level if node in siblings),
            key=lambda item: item[0],
        )

        if not indexed_nodes:
            raise ValueError("Cannot wrap nodes from different sibling lists")

        insert_index = indexed_nodes[0][0]
        wrapped_steps = [copy.deepcopy(node.step) for _, node in indexed_nodes]
        parent = first.parent

        for index, node in reversed(indexed_nodes):
            siblings.pop(index)
            node.parent = None

        repeat_step: StepDict = {"type": "repeat", "count": 1, "steps": wrapped_steps}
        repeat_node = StepNode(repeat_step, parent=parent)
        siblings.insert(insert_index, repeat_node)

        return repeat_node

    def duplicate_nodes(self, nodes: list[StepNode]) -> list[StepNode]:
        top_level = self.get_top_level(nodes)
        duplicates: list[StepNode] = []

        for node in top_level:
            dup_step = copy.deepcopy(node.step)
            dup_node = StepNode(dup_step, parent=node.parent)
            siblings = self.sibling_list(node)
            index = self.sibling_index(node)
            if index < 0:
                index = len(siblings) - 1

            siblings.insert(index + 1, dup_node)
            duplicates.append(dup_node)

        return duplicates

    def add_step(self, target_node: StepNode | None, step: StepDict) -> StepNode:
        node = StepNode(step)

        if target_node is None:
            self.root_nodes.append(node)
            return node

        default_key = self.default_child_key(target_node)
        if default_key:
            child_list = target_node.get_child_list(default_key)
            node.parent = target_node
            child_list.append(node)
            return node

        self.insert_node_after(target_node, node)
        return node

    def add_step_to_branch(self, parent_node: StepNode, branch_key: str, step: StepDict) -> StepNode:
        node = StepNode(step, parent=parent_node)
        parent_node.get_child_list(branch_key).append(node)
        return node

    def add_step_to_any_branch(self, parent_node: StepNode, template_id: str, step: StepDict) -> StepNode:
        return self.add_step_to_branch(parent_node, template_id, step)

    def insert_steps_after(self, target_node: StepNode | None, steps: list[StepDict]) -> list[StepNode]:
        nodes: list[StepNode] = []
        current_target = target_node
        for step in steps:
            node = self.add_step(current_target, step)
            nodes.append(node)
            current_target = node

        return nodes

    def sync_from_tree(self) -> None:
        for node in self.root_nodes:
            node.serialize_children()

    def sync_node_children(self, node: StepNode) -> None:
        node.serialize_children()

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
        self.remove_node(node)

    def move_step(self, node: StepNode, direction: int) -> bool:
        source_list = self.sibling_list(node)
        source_index = self.sibling_index(node)
        if source_index < 0:
            return False

        new_index = source_index + direction

        if 0 <= new_index < len(source_list):
            neighbor = source_list[new_index]
            if self.try_move_into_container(source_list, source_index, neighbor, direction):
                return True

            moved = source_list.pop(source_index)
            source_list.insert(new_index, moved)
            return True

        if node.parent is None:
            return False

        source_parent = node.parent
        sibling_key = node.sibling_key()
        target_sibling_key = self.find_sibling_key(source_parent, sibling_key, direction)
        if target_sibling_key is not None:
            dest_list = source_parent.get_child_list(target_sibling_key)
            self.move_between_lists(source_list, source_index, dest_list, source_parent, append=direction == -1)
            return True

        grandparent = source_parent.parent
        if grandparent is not None:
            parent_list = self.sibling_list(source_parent)
            parent_index = self.sibling_index(source_parent)
            if parent_index < 0:
                return False

            insert_at = parent_index if direction == -1 else parent_index + 1
            self.move_between_lists(source_list, source_index, parent_list, grandparent, insert_at=insert_at)
            return True

        parent_in_roots = self.sibling_index(source_parent)
        if parent_in_roots < 0:
            return False

        insert_at = parent_in_roots if direction == -1 else parent_in_roots + 1
        self.move_between_lists(source_list, source_index, self.root_nodes, None, insert_at=insert_at)
        return True

    def move_root(self, node: StepNode, direction: int) -> bool:
        if node.parent is not None:
            return False

        return self.move_step(node, direction)

    def can_move(self, node: StepNode, direction: int) -> bool:
        source_list = self.sibling_list(node)
        source_index = self.sibling_index(node)
        if source_index < 0:
            return False

        new_index = source_index + direction
        if 0 <= new_index < len(source_list):
            return True

        if node.parent is None:
            return False

        source_parent = node.parent
        sibling_key = node.sibling_key()
        if self.find_sibling_key(source_parent, sibling_key, direction) is not None:
            return True

        if source_parent.parent is not None:
            return self.sibling_index(source_parent) >= 0

        return source_parent in self.root_nodes

    def can_move_root(self, node: StepNode, direction: int) -> bool:
        if node.parent is not None:
            return False

        index = self.sibling_index(node)
        if index < 0:
            return False

        new_index = index + direction
        return 0 <= new_index < len(self.root_nodes)

    def sibling_list(self, node: StepNode) -> list[StepNode]:
        if node.parent is None:
            return self.root_nodes

        return node.parent.get_child_list(node.sibling_key())

    def sibling_index(self, node: StepNode) -> int:
        siblings = self.sibling_list(node)
        for index, sibling in enumerate(siblings):
            if sibling is node:
                return index

        return -1

    def next_sibling(self, node: StepNode) -> StepNode | None:
        siblings = self.sibling_list(node)
        index = self.sibling_index(node)
        if index < 0 or index + 1 >= len(siblings):
            return None

        return siblings[index + 1]

    def prev_sibling(self, node: StepNode) -> StepNode | None:
        siblings = self.sibling_list(node)
        index = self.sibling_index(node)
        if index <= 0:
            return None

        return siblings[index - 1]

    def insert_node_after(self, target_node: StepNode | None, node: StepNode) -> None:
        if target_node is None:
            node.parent = None
            self.root_nodes.append(node)
            return

        siblings = self.sibling_list(target_node)
        index = self.sibling_index(target_node)
        if index < 0:
            index = len(siblings) - 1

        node.parent = target_node.parent
        siblings.insert(index + 1, node)

    def remove_node(self, node: StepNode) -> None:
        siblings = self.sibling_list(node)
        index = self.sibling_index(node)
        if index >= 0:
            siblings.pop(index)

        node.parent = None

    @staticmethod
    def default_child_key(node: StepNode) -> str:
        if node.step_type == "if_any_image":
            branches = node.branches_map()
            return next(iter(branches), "")

        keys = CONTAINER_CHILD_KEYS.get(node.step_type, [])
        return keys[0] if keys else ""

    @staticmethod
    def try_move_into_container(
        source_list: list[StepNode], source_index: int, neighbor: StepNode, direction: int
    ) -> bool:
        if neighbor.is_leaf:
            return False

        moved = source_list[source_index]
        if neighbor.is_descendant_of(moved):
            return False

        if neighbor.step_type == "if_any_image":
            branch_names = list(neighbor.branches_map())
        else:
            branch_names = CONTAINER_CHILD_KEYS.get(neighbor.step_type, [])

        if not branch_names:
            return False

        child_key = branch_names[0] if direction == 1 else branch_names[-1]
        dest_list = neighbor.get_child_list(child_key)
        moved = source_list.pop(source_index)
        moved.parent = neighbor

        if direction == -1:
            dest_list.append(moved)
        else:
            dest_list.insert(0, moved)

        return True

    @staticmethod
    def move_between_lists(
        source_list: list[StepNode],
        source_index: int,
        dest_list: list[StepNode],
        parent: StepNode | None,
        *,
        append: bool = False,
        insert_at: int | None = None,
    ) -> None:
        node = source_list.pop(source_index)
        node.parent = parent

        if append:
            dest_list.append(node)
            return

        if insert_at is None:
            dest_list.insert(0, node)
            return

        dest_list.insert(insert_at, node)

    @staticmethod
    def find_sibling_key(parent: StepNode, current_key: str, direction: int) -> str | None:
        if parent.step_type == "if_any_image":
            keys = list(parent.branches_map())
        else:
            keys = CONTAINER_CHILD_KEYS.get(parent.step_type, [])

        try:
            index = keys.index(current_key)
        except ValueError:
            return None

        next_index = index + direction
        if 0 <= next_index < len(keys):
            return keys[next_index]

        return None

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
        if node.parent is not None:
            node.parent.serialize_children()

        for root_node in self.root_nodes:
            root_node.serialize_children()

    @staticmethod
    def step_type(step: StepDict) -> str:
        return get_step_type(step)
