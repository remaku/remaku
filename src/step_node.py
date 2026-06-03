"""Step tree node model.

Provides a tree-structured representation of macro steps, replacing
the flat_steps / flat_parents pattern with proper parent-child references.
"""

from __future__ import annotations

# Child-list keys for each container step type.
CONTAINER_CHILD_KEYS: dict[str, list[str]] = {
    "repeat": ["steps"],
    "if_image": ["then", "else"],
    "if_any_image": [],  # branches are a dict, handled separately
    "grid_nav": ["on_next_row", "on_next_col"],
}


class StepNode:
    """A node in the step tree, wrapping a step dict with structural references."""

    def __init__(self, step: dict, parent: StepNode | None = None) -> None:
        self.step = step
        self.parent = parent
        self.children: list[StepNode] = []

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def step_type(self) -> str:
        return self.step.get("type", "?")

    @property
    def is_container(self) -> bool:
        return self.step_type in CONTAINER_CHILD_KEYS or self.step_type == "if_any_image"

    @property
    def is_leaf(self) -> bool:
        return not self.is_container

    # ------------------------------------------------------------------
    # Child list access (unified interface)
    # ------------------------------------------------------------------

    def child_lists(self) -> list[tuple[str, list[StepNode]]]:
        """Return all child branches as ``(branch_name, child_nodes)`` pairs.

        Examples::

            repeat      -> [("steps", [...])]
            if_image    -> [("then", [...]), ("else", [...])]
            grid_nav    -> [("on_next_row", [...]), ("on_next_col", [...])]
            if_any_image -> [("tpl_a", [...]), ("tpl_b", [...])]
        """
        result: list[tuple[str, list[StepNode]]] = []
        for key in CONTAINER_CHILD_KEYS.get(self.step_type, []):
            result.append((key, self.child_list_for_key(key)))
        if self.step_type == "if_any_image":
            for branch_name, branch_nodes in self.branches_map().items():
                result.append((branch_name, branch_nodes))
        return result

    def get_child_list(self, key: str) -> list[StepNode]:
        """Return the child node list for a given branch key."""
        if key in CONTAINER_CHILD_KEYS.get(self.step_type, []):
            return self.child_list_for_key(key)
        if self.step_type == "if_any_image":
            return self.branches_map().get(key, [])
        return []

    def set_child_list(self, key: str, nodes: list[StepNode]) -> None:
        """Replace the child node list for a given branch key."""
        if key in CONTAINER_CHILD_KEYS.get(self.step_type, []):
            self.set_child_list_for_key(key, nodes)
            return
        if self.step_type == "if_any_image":
            branches = self.step.setdefault("branches", {})
            branches[key] = [n.step for n in nodes]
            for n in nodes:
                n.parent = self

    def all_child_lists(self) -> list[list[StepNode]]:
        """Return all raw child list references (for iteration)."""
        return [child_list for _, child_list in self.child_lists()]

    # ------------------------------------------------------------------
    # Descendant traversal
    # ------------------------------------------------------------------

    def all_descendants(self) -> list[StepNode]:
        """Return all descendant nodes in DFS order (excluding self)."""
        result: list[StepNode] = []
        for _, child_list in self.child_lists():
            for child in child_list:
                result.append(child)
                result.extend(child.all_descendants())
        return result

    def is_descendant_of(self, ancestor: StepNode) -> bool:
        """Check if this node is a descendant of *ancestor*."""
        current = self.parent
        while current is not None:
            if current is ancestor:
                return True
            current = current.parent
        return False

    # ------------------------------------------------------------------
    # Sibling navigation
    # ------------------------------------------------------------------

    def next_sibling(self) -> StepNode | None:
        """Return the next sibling, or ``None``."""
        if self.parent is None:
            return None
        siblings = self.parent.get_child_list(self.sibling_key())
        idx = self.sibling_index(siblings)
        if idx < 0 or idx + 1 >= len(siblings):
            return None
        return siblings[idx + 1]

    def prev_sibling(self) -> StepNode | None:
        """Return the previous sibling, or ``None``."""
        if self.parent is None:
            return None
        siblings = self.parent.get_child_list(self.sibling_key())
        idx = self.sibling_index(siblings)
        if idx <= 0:
            return None
        return siblings[idx - 1]

    def index_in_parent(self) -> int:
        """Return the index of this node in its parent's child list, or -1."""
        if self.parent is None:
            return -1
        siblings = self.parent.get_child_list(self.sibling_key())
        return self.sibling_index(siblings)

    # ------------------------------------------------------------------
    # Tree mutation
    # ------------------------------------------------------------------

    def remove(self) -> None:
        """Remove this node from its parent's child list."""
        if self.parent is None:
            return
        key = self.sibling_key()
        siblings = self.parent.get_child_list(key)
        idx = self.sibling_index(siblings)
        if idx >= 0:
            siblings.pop(idx)
            raw_list = self.parent.step.get(key, [])
            if 0 <= idx < len(raw_list):
                raw_list.pop(idx)
        self.parent = None

    def insert_after(self, sibling: StepNode) -> None:
        """Insert this node after *sibling* in the sibling's parent list."""
        if sibling.parent is None:
            return
        key = sibling.sibling_key()
        siblings = sibling.parent.get_child_list(key)
        idx = siblings.index(sibling) if sibling in siblings else len(siblings)
        siblings.insert(idx + 1, self)
        raw_list = sibling.parent.step.get(key, [])
        raw_list.insert(idx + 1, self.step)
        self.parent = sibling.parent

    def append_to(self, target_list: list[StepNode], parent: StepNode | None = None) -> None:
        """Append this node to *target_list* and update parent reference."""
        if self.parent is not None:
            self.remove()
        target_list.append(self)
        if parent is not None:
            self.parent = parent

    def insert_in(self, target_list: list[StepNode], index: int, parent: StepNode | None = None) -> None:
        """Insert this node into *target_list* at *index*."""
        if self.parent is not None:
            self.remove()
        target_list.insert(index, self)
        if parent is not None:
            self.parent = parent

    # ------------------------------------------------------------------
    # Top-level filtering (replaces duplicate descendant filtering)
    # ------------------------------------------------------------------

    @staticmethod
    def filter_top_level(nodes: list[StepNode]) -> list[StepNode]:
        """Return only nodes that are not descendants of other nodes in the list."""
        descendant_ids = set()
        for node in nodes:
            for desc in node.all_descendants():
                descendant_ids.add(id(desc))
        return [n for n in nodes if id(n) not in descendant_ids]

    # ------------------------------------------------------------------
    # Repr
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return f"StepNode({self.step_type}, id={id(self)})"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def child_list_for_key(self, key: str) -> list[StepNode]:
        """Build and cache a child node list for a given key."""
        raw_list = self.step.setdefault(key, [])
        cache_key = f"cached_children_{key}"
        cached = getattr(self, cache_key, None)
        if cached is not None and len(cached) == len(raw_list):
            return cached
        nodes = [StepNode(s, parent=self) for s in raw_list]
        setattr(self, cache_key, nodes)
        return nodes

    def set_child_list_for_key(self, key: str, nodes: list[StepNode]) -> None:
        """Replace the raw step list and rebuild child nodes."""
        self.step[key] = [n.step for n in nodes]
        for n in nodes:
            n.parent = self
        setattr(self, f"cached_children_{key}", nodes)

    def branches_map(self) -> dict[str, list[StepNode]]:
        """Build and cache branch child lists for if_any_image."""
        branches = self.step.setdefault("branches", {})
        cached = getattr(self, "cached_branches", None)
        if (
            cached is not None
            and set(cached.keys()) == set(branches.keys())
            and all(len(cached[k]) == len(branches[k]) for k in cached)
        ):
            return cached
        result: dict[str, list[StepNode]] = {}
        for branch_name, raw_list in branches.items():
            result[branch_name] = [StepNode(s, parent=self) for s in raw_list]
        self.cached_branches = result
        return result

    def sibling_key(self) -> str:
        """Return the branch key this node belongs to in its parent."""
        if self.parent is None:
            return ""
        for key, child_list in self.parent.child_lists():
            if any(n is self for n in child_list):
                return key
        return ""

    def sibling_index(self, siblings: list[StepNode]) -> int:
        """Return the index of self in *siblings*, or -1."""
        for i, s in enumerate(siblings):
            if s is self:
                return i
        return -1

    def clear_caches(self) -> None:
        """Clear all cached child lists so they rebuild from raw on next access."""
        for key in CONTAINER_CHILD_KEYS.get(self.step_type, []):
            cache_key = f"cached_children_{key}"
            if hasattr(self, cache_key):
                delattr(self, cache_key)
        if self.step_type == "if_any_image" and hasattr(self, "cached_branches"):
            delattr(self, "cached_branches")
