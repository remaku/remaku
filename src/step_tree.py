"""Step tree manager.

Builds and maintains a tree of ``StepNode`` objects from a macro's step list,
providing high-level operations that replace ad-hoc flat_steps manipulation.
"""

from __future__ import annotations

import contextlib
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

        # Save insertion position before removing (remove updates raw dicts).
        insert_key = ""
        insert_idx = 0
        if first_parent is not None:
            for key, child_list in first_parent.child_lists():
                if first in child_list:
                    insert_key = key
                    insert_idx = child_list.index(first)
                    break

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
            raw_list = first_parent.step.get(insert_key, [])
            repeat_node.parent = first_parent
            first_parent.get_child_list(insert_key).insert(insert_idx, repeat_node)
            raw_list.insert(insert_idx, repeat_step)
        else:
            # Root node case: save positions, remove originals, insert repeat.
            positions = []
            for node in top_level:
                try:
                    positions.append(self.steps.index(node.step))
                except ValueError:
                    positions.append(-1)

            for node in top_level:
                if node in self.root_nodes:
                    self.root_nodes.remove(node)
                with contextlib.suppress(ValueError):
                    self.steps.remove(node.step)

            first_pos = positions[0]
            removed_before = sum(1 for p in positions if 0 <= p < first_pos)
            adjusted_idx = first_pos - removed_before

            self.steps.insert(adjusted_idx, repeat_step)
            self.root_nodes.insert(adjusted_idx, repeat_node)

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

            if node.parent is not None:
                dup_node.insert_after(node)
            else:
                # Root node: insert into root_nodes and steps.
                try:
                    idx = self.root_nodes.index(node)
                except ValueError:
                    idx = len(self.root_nodes)
                self.root_nodes.insert(idx + 1, dup_node)
                try:
                    raw_idx = self.steps.index(node.step)
                except ValueError:
                    raw_idx = len(self.steps)
                self.steps.insert(raw_idx + 1, dup_step)

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
