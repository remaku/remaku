from remaku.models.step_dict import StepDict, get_step_branches, get_step_list, get_step_type

CONTAINER_CHILD_KEYS: dict[str, list[str]] = {
    "repeat": ["steps"],
    "if_image": ["then", "else"],
    "if_number": ["then", "else"],
    "if_any_image": [],
    "grid_nav": ["on_next_row", "on_next_col"],
    "repeat_until_number": ["steps"],
}


class StepNode:
    def __init__(self, step: StepDict, parent: "StepNode | None" = None) -> None:
        self.step = step
        self.parent = parent
        self.children_by_key: dict[str, list[StepNode]] = {}
        self.branches_by_key: dict[str, list[StepNode]] = {}

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
            return self.branch_list_for_key(key)

        return []

    def set_child_list(self, key: str, nodes: list["StepNode"]) -> None:
        if key in CONTAINER_CHILD_KEYS.get(self.step_type, []):
            self.children_by_key[key] = nodes
            self.assign_parent(nodes)
            return

        if self.step_type == "if_any_image":
            self.branches_by_key[key] = nodes
            self.assign_parent(nodes)

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

        siblings = self.parent.get_child_list(self.sibling_key())
        index = self.sibling_index(siblings)
        if index >= 0:
            siblings.pop(index)

        self.parent = None

    def insert_after(self, sibling: "StepNode") -> None:
        if sibling.parent is None:
            return

        key = sibling.sibling_key()
        siblings = sibling.parent.get_child_list(key)
        index = siblings.index(sibling) if sibling in siblings else len(siblings) - 1
        siblings.insert(index + 1, self)
        self.parent = sibling.parent

    def append_to(self, target_list: list["StepNode"], parent: "StepNode | None" = None) -> None:
        if self.parent is not None:
            self.remove()

        target_list.append(self)
        self.parent = parent

    def insert_in(self, target_list: list["StepNode"], index: int, parent: "StepNode | None" = None) -> None:
        if self.parent is not None:
            self.remove()

        target_list.insert(index, self)
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
        if key not in self.children_by_key:
            raw_list = get_step_list(self.step, key)
            self.children_by_key[key] = [StepNode(step, parent=self) for step in raw_list]

        return self.children_by_key[key]

    def set_child_list_for_key(self, key: str, nodes: list["StepNode"]) -> None:
        self.children_by_key[key] = nodes
        self.assign_parent(nodes)

    def branches_map(self) -> dict[str, list["StepNode"]]:
        branches = get_step_branches(self.step)
        template_ids = [str(template_id) for template_id in self.step.get("templates", [])]
        all_names = list(dict.fromkeys([*template_ids, *branches.keys(), *self.branches_by_key.keys()]))

        for branch_name in all_names:
            if branch_name not in self.branches_by_key:
                raw_list = branches.setdefault(branch_name, [])
                self.branches_by_key[branch_name] = [StepNode(step, parent=self) for step in raw_list]

        return {branch_name: self.branches_by_key[branch_name] for branch_name in all_names}

    def branch_list_for_key(self, key: str) -> list["StepNode"]:
        self.branches_map()
        if key not in self.branches_by_key:
            self.branches_by_key[key] = []

        return self.branches_by_key[key]

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
        self.children_by_key.clear()
        self.branches_by_key.clear()

    def serialize_children(self) -> None:
        if self.step_type == "if_any_image":
            branches = get_step_branches(self.step)
            template_ids = [str(t) for t in self.step.get("templates", [])]
            for key in list(branches.keys()):
                if key not in template_ids:
                    del branches[key]
            for key in list(self.branches_by_key.keys()):
                if key not in template_ids:
                    del self.branches_by_key[key]

        for key, child_list in self.child_lists():
            for child in child_list:
                child.serialize_children()

            if self.step_type == "if_any_image":
                get_step_branches(self.step)[key] = [child.step for child in child_list]
            else:
                self.step[key] = [child.step for child in child_list]

    def assign_parent(self, nodes: list["StepNode"]) -> None:
        for node in nodes:
            node.parent = self
