"""Step tree manager.

Builds and maintains a tree of ``StepNode`` objects from a macro's step list,
providing high-level operations that replace ad-hoc flat_steps manipulation.
"""

from __future__ import annotations

import copy

from step_node import StepNode


class StepTree:
    """Manages the step tree for a single macro."""

    def __init__(self, steps: list[dict]) -> None:
        self.steps = steps
        self.root_nodes: list[StepNode] = [StepNode(s) for s in steps]

    # ------------------------------------------------------------------
    # Building
    # ------------------------------------------------------------------

    @classmethod
    def from_macro(cls, macro: dict) -> StepTree:
        """Create a tree from a macro dict."""
        return cls(macro.get("steps", []))

    # ------------------------------------------------------------------
    # Flattening (display order)
    # ------------------------------------------------------------------

    def flatten(self) -> list[StepNode]:
        """Flatten the tree to display order (DFS, pre-order)."""
        result: list[StepNode] = []
        for node in self.root_nodes:
            result.append(node)
            result.extend(node.all_descendants())
        return result

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def find_node(self, step: dict) -> StepNode | None:
        """Find the node wrapping *step* by identity."""
        for node in self.flatten():
            if node.step is step:
                return node
        return None

    def node_at(self, flat_index: int) -> StepNode | None:
        """Return the node at *flat_index* in the flattened list."""
        flat = self.flatten()
        if 0 <= flat_index < len(flat):
            return flat[flat_index]
        return None

    # ------------------------------------------------------------------
    # Top-level filtering
    # ------------------------------------------------------------------

    def get_top_level(self, nodes: list[StepNode]) -> list[StepNode]:
        """Filter out nodes that are descendants of other nodes in the list."""
        return StepNode.filter_top_level(nodes)

    # ------------------------------------------------------------------
    # Tree operations
    # ------------------------------------------------------------------

    def wrap_in_repeat(self, nodes: list[StepNode]) -> StepNode:
        """Wrap *nodes* (already top-level filtered) in a new repeat block.

        The new repeat is inserted at the position of the first node
        in its parent list.  Returns the new repeat node.
        """
        if not nodes:
            raise ValueError("Cannot wrap an empty list of nodes")

        top_level = self.get_top_level(nodes)
        first = top_level[0]
        first_parent = first.parent

        # Collect the raw step dicts (deep copy to avoid shared refs).
        wrapped_steps = [copy.deepcopy(n.step) for n in top_level]

        # Remove original nodes from their parent lists (reverse order).
        for node in reversed(top_level):
            node.remove()

        # Create the repeat step and node.
        repeat_step: dict = {"type": "repeat", "count": 1, "steps": wrapped_steps}
        repeat_node = StepNode(repeat_step)

        # Insert the repeat at the first node's former position.
        if first_parent is not None:
            # Find the key the first node belonged to.
            for key, child_list in first_parent.child_lists():
                # We need the raw list index.
                raw_list = first_parent.step.get(key, [])
                # Find where first.step was in the raw list.
                try:
                    raw_idx = raw_list.index(first.step)
                except ValueError:
                    raw_idx = len(raw_list)
                repeat_node.parent = first_parent
                child_list.insert(raw_idx, repeat_node)
                raw_list.insert(raw_idx, repeat_step)
                break
        else:
            # First node was a root node.
            try:
                idx = self.steps.index(first.step)
            except ValueError:
                idx = len(self.steps)
            self.steps.insert(idx, repeat_step)
            self.root_nodes.insert(idx, repeat_node)

        return repeat_node

    def duplicate_nodes(self, nodes: list[StepNode]) -> list[StepNode]:
        """Deep-copy *nodes* and insert the copies after the originals.

        Returns the list of newly created nodes.
        """
        top_level = self.get_top_level(nodes)
        duplicates: list[StepNode] = []

        for node in top_level:
            dup_step = copy.deepcopy(node.step)
            dup_node = StepNode(dup_step)
            dup_node.insert_after(node)
            # Also insert into the raw step list.
            key = node.sibling_key()
            raw_list = node.parent.step.get(key, []) if node.parent else self.steps
            try:
                raw_idx = raw_list.index(node.step)
            except ValueError:
                raw_idx = len(raw_list)
            raw_list.insert(raw_idx + 1, dup_step)
            duplicates.append(dup_node)

        return duplicates

    # ------------------------------------------------------------------
    # Sync raw step lists from tree (write-back)
    # ------------------------------------------------------------------

    def sync_from_tree(self) -> None:
        """Synchronize the raw ``macro["steps"]`` list from the tree structure.

        This ensures the underlying step dicts match the tree after
        structural changes.
        """
        self.steps[:] = [n.step for n in self.root_nodes]
        for node in self.root_nodes:
            self.sync_node_children(node)

    def sync_node_children(self, node: StepNode) -> None:
        for key, child_list in node.child_lists():
            node.step[key] = [n.step for n in child_list]
            for child in child_list:
                self.sync_node_children(child)

    # ------------------------------------------------------------------
    # Collect template refs (replaces recursive collect_template_refs)
    # ------------------------------------------------------------------

    def collect_template_refs(self) -> set[str]:
        """Collect all template names referenced by any step in the tree."""
        refs: set[str] = set()
        for node in self.flatten():
            if name := node.step.get("template"):
                refs.add(name)
            for name in node.step.get("templates", []):
                refs.add(name)
        return refs
