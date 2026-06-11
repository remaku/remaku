from remaku.models.step_dict import StepDict, get_step_branches, get_step_list, get_step_type

CONTAINER_CHILD_KEYS: dict[str, list[str]] = {
    "repeat": ["steps"],
    "if_image": ["then", "else"],
    "if_any_image": [],
    "grid_nav": ["on_next_row", "on_next_col"],
}


class StepNode:
    def __init__(self, step: StepDict, parent: "StepNode | None" = None) -> None:
        self.step = step
        self.parent = parent
        self.children: list[StepNode] = []

    @property
    def step_type(self) -> str:
        return get_step_type(self.step, "?")

    @property
    def is_container(self) -> bool:
        return self.step_type in CONTAINER_CHILD_KEYS or self.step_type == "if_any_image"

    @property
    def is_leaf(self) -> bool:
        return not self.is_container

    def child_lists(self) -> list[tuple[str, list["StepNode"]]]:
        result: list[tuple[str, list[StepNode]]] = []
        for key in CONTAINER_CHILD_KEYS.get(self.step_type, []):
            result.append((key, self.child_list_for_key(key)))
        if self.step_type == "if_any_image":
            for branch_name, branch_nodes in self.branches_map().items():
                result.append((branch_name, branch_nodes))
        return result

    def get_child_list(self, key: str) -> list["StepNode"]:
        if key in CONTAINER_CHILD_KEYS.get(self.step_type, []):
            return self.child_list_for_key(key)
        if self.step_type == "if_any_image":
            return self.branches_map().get(key, [])
        return []

    def set_child_list(self, key: str, nodes: list["StepNode"]) -> None:
        if key in CONTAINER_CHILD_KEYS.get(self.step_type, []):
            self.set_child_list_for_key(key, nodes)
            return
        if self.step_type == "if_any_image":
            branches = get_step_branches(self.step)
            branches[key] = [node.step for node in nodes]
            for node in nodes:
                node.parent = self

    def all_child_lists(self) -> list[list["StepNode"]]:
        return [child_list for _, child_list in self.child_lists()]

    def all_descendants(self) -> list["StepNode"]:
        result: list[StepNode] = []
        for _, child_list in self.child_lists():
            for child in child_list:
                result.append(child)
                result.extend(child.all_descendants())
        return result

    def is_descendant_of(self, ancestor: "StepNode") -> bool:
        current = self.parent
        while current is not None:
            if current is ancestor:
                return True
            current = current.parent
        return False

    def next_sibling(self) -> "StepNode | None":
        if self.parent is None:
            return None
        siblings = self.parent.get_child_list(self.sibling_key())
        index = self.sibling_index(siblings)
        if index < 0 or index + 1 >= len(siblings):
            return None
        return siblings[index + 1]

    def prev_sibling(self) -> "StepNode | None":
        if self.parent is None:
            return None
        siblings = self.parent.get_child_list(self.sibling_key())
        index = self.sibling_index(siblings)
        if index <= 0:
            return None
        return siblings[index - 1]

    def index_in_parent(self) -> int:
        if self.parent is None:
            return -1
        siblings = self.parent.get_child_list(self.sibling_key())
        return self.sibling_index(siblings)

    def remove(self) -> None:
        if self.parent is None:
            return
        key = self.sibling_key()
        siblings = self.parent.get_child_list(key)
        index = self.sibling_index(siblings)
        if index >= 0:
            siblings.pop(index)
            if self.parent.step_type == "if_any_image":
                raw_list = get_step_branches(self.parent.step).get(key, [])
            else:
                raw_list = get_step_list(self.parent.step, key)
            if 0 <= index < len(raw_list):
                raw_list.pop(index)
        self.parent = None

    def insert_after(self, sibling: "StepNode") -> None:
        if sibling.parent is None:
            return
        key = sibling.sibling_key()
        siblings = sibling.parent.get_child_list(key)
        index = siblings.index(sibling) if sibling in siblings else len(siblings)
        siblings.insert(index + 1, self)
        if sibling.parent.step_type == "if_any_image":
            raw_list = get_step_branches(sibling.parent.step).setdefault(key, [])
        else:
            raw_list = get_step_list(sibling.parent.step, key)
        raw_list.insert(index + 1, self.step)
        self.parent = sibling.parent

    def append_to(self, target_list: list["StepNode"], parent: "StepNode | None" = None) -> None:
        if self.parent is not None:
            self.remove()
        target_list.append(self)
        if parent is not None:
            self.parent = parent

    def insert_in(self, target_list: list["StepNode"], index: int, parent: "StepNode | None" = None) -> None:
        if self.parent is not None:
            self.remove()
        target_list.insert(index, self)
        if parent is not None:
            self.parent = parent

    @staticmethod
    def filter_top_level(nodes: list["StepNode"]) -> list["StepNode"]:
        descendant_ids = set()
        for node in nodes:
            for desc in node.all_descendants():
                descendant_ids.add(id(desc))
        return [node for node in nodes if id(node) not in descendant_ids]

    def __repr__(self) -> str:
        return f"StepNode({self.step_type}, id={id(self)})"

    def child_list_for_key(self, key: str) -> list["StepNode"]:
        raw_list = get_step_list(self.step, key)
        cache_key = f"cached_children_{key}"
        cached = getattr(self, cache_key, None)
        if cached is not None and len(cached) == len(raw_list):
            return cached
        nodes = [StepNode(s, parent=self) for s in raw_list]
        setattr(self, cache_key, nodes)
        return nodes

    def set_child_list_for_key(self, key: str, nodes: list["StepNode"]) -> None:
        self.step[key] = [node.step for node in nodes]
        for node in nodes:
            node.parent = self
        setattr(self, f"cached_children_{key}", nodes)

    def branches_map(self) -> dict[str, list["StepNode"]]:
        branches = get_step_branches(self.step)
        template_ids = self.step.get("templates", [])
        for template_id in template_ids:
            branches.setdefault(template_id, [])
        all_names = list(dict.fromkeys([*template_ids, *branches.keys()]))
        cached = getattr(self, "cached_branches", None)
        if (
            cached is not None
            and set(cached.keys()) == set(all_names)
            and all(len(cached.get(key, [])) == len(branches.get(key, [])) for key in all_names)
        ):
            return cached
        result: dict[str, list[StepNode]] = {}
        for branch_name in all_names:
            raw_list = branches.get(branch_name, [])
            result[branch_name] = [StepNode(s, parent=self) for s in raw_list]
        self.cached_branches = result
        return result

    def sibling_key(self) -> str:
        if self.parent is None:
            return ""
        for key, child_list in self.parent.child_lists():
            if any(node is self for node in child_list):
                return key
        return ""

    def sibling_index(self, siblings: list["StepNode"]) -> int:
        for index, sibling in enumerate(siblings):
            if sibling is self:
                return index
        return -1

    def clear_caches(self) -> None:
        for key in CONTAINER_CHILD_KEYS.get(self.step_type, []):
            cache_key = f"cached_children_{key}"
            if hasattr(self, cache_key):
                delattr(self, cache_key)
        if self.step_type == "if_any_image" and hasattr(self, "cached_branches"):
            delattr(self, "cached_branches")
