"""Step tree manager.

Builds and maintains a tree of ``StepNode`` objects from a macro's step list,
providing high-level operations that replace ad-hoc flat_steps manipulation.
"""

from __future__ import annotations

import copy

from step_node import CONTAINER_CHILD_KEYS, StepNode


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
                    positions.append(next(i for i, s in enumerate(self.steps) if s is node.step))
                except StopIteration:
                    positions.append(-1)

            for node in top_level:
                try:
                    idx = next(i for i, n in enumerate(self.root_nodes) if n is node)
                    self.root_nodes.pop(idx)
                    self.steps.pop(idx)
                except StopIteration:
                    pass

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
                    raw_idx = next(i for i, s in enumerate(self.steps) if s is node.step)
                except StopIteration:
                    raw_idx = len(self.steps)
                self.steps.insert(raw_idx + 1, dup_step)

            duplicates.append(dup_node)

        return duplicates

    # ------------------------------------------------------------------
    # Add step
    # ------------------------------------------------------------------

    def add_step(self, target_node: StepNode | None, step: dict) -> StepNode:
        """Insert *step* after *target_node*, or append if *target_node* is None.

        If *target_node* is a container (repeat, if_image, if_any_image),
        append to its default child list instead of inserting after it.
        """
        if target_node is None:
            self.steps.append(step)
            return StepNode(step)

        if target_node.step_type == "repeat":
            target_node.step.setdefault("steps", []).append(step)
            return StepNode(step, parent=target_node)

        if target_node.step_type in ("if_image", "if_any_image"):
            target_node.step.setdefault("then", []).append(step)
            return StepNode(step, parent=target_node)

        parent_key = target_node.sibling_key()
        if target_node.parent is not None and parent_key:
            raw_list = target_node.parent.step.get(parent_key, [])
            idx = next((i for i, s in enumerate(raw_list) if s is target_node.step), len(raw_list))
            raw_list.insert(idx + 1, step)
            return StepNode(step, parent=target_node.parent)

        idx = next((i for i, s in enumerate(self.steps) if s is target_node.step), len(self.steps))
        self.steps.insert(idx + 1, step)
        return StepNode(step)

    def add_step_to_branch(self, parent_node: StepNode, branch_key: str, step: dict) -> StepNode:
        """Add a step to a specific branch of a container node."""
        parent_node.step.setdefault(branch_key, []).append(step)
        return StepNode(step, parent=parent_node)

    def add_step_to_any_branch(self, parent_node: StepNode, template_name: str, step: dict) -> StepNode:
        """Add a step to a template branch in if_any_image."""
        branches = parent_node.step.setdefault("branches", {})
        branches.setdefault(template_name, []).append(step)
        return StepNode(step, parent=parent_node)

    def insert_steps_after(self, target_node: StepNode | None, steps: list[dict]) -> list[StepNode]:
        """Insert multiple steps consecutively after *target_node*."""
        nodes: list[StepNode] = []
        current_target = target_node
        for step in steps:
            node = self.add_step(current_target, step)
            nodes.append(node)
            current_target = node
        return nodes

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

    # ------------------------------------------------------------------
    # Flatten with depth (for display)
    # ------------------------------------------------------------------

    def flatten_with_depth(self) -> list[tuple[StepNode, int]]:
        """Flatten the tree to ``(node, depth)`` pairs in display order."""
        result: list[tuple[StepNode, int]] = []
        for node in self.root_nodes:
            result.append((node, 0))
            self._collect_descendants_with_depth(node, 1, result)
        return result

    def _collect_descendants_with_depth(self, node: StepNode, depth: int, out: list[tuple[StepNode, int]]) -> None:
        for _, child_list in node.child_lists():
            for child in child_list:
                out.append((child, depth))
                self._collect_descendants_with_depth(child, depth + 1, out)

    # ------------------------------------------------------------------
    # Delete node
    # ------------------------------------------------------------------

    def delete_node(self, node: StepNode) -> None:
        """Remove *node* from the tree, updating raw step lists."""
        if node.parent is not None:
            node.remove()
        else:
            try:
                idx = next(i for i, n in enumerate(self.root_nodes) if n is node)
                self.root_nodes.pop(idx)
                self.steps.pop(idx)
            except StopIteration:
                pass

    # ------------------------------------------------------------------
    # Move step
    # ------------------------------------------------------------------

    def move_step(self, node: StepNode, direction: int) -> bool:
        """Move *node* by *direction* (-1=up, 1=down). Returns True if moved.

        Handles: sibling swap, entering/leaving block children, and
        crossing between sibling branches (then/else, row/col, etc.).

        All mutations go through raw step dicts to keep caches coherent.
        """
        if node.parent is None:
            return self._move_root(node, direction)

        key = node.sibling_key()
        raw = node.parent.step.get(key, [])
        idx = -1
        for i, s in enumerate(raw):
            if s is node.step:
                idx = i
                break
        if idx < 0:
            return False

        new_idx = idx + direction

        # Case 1: Move into a neighboring block's child list.
        if 0 <= new_idx < len(raw):
            neighbor_step = raw[new_idx]
            neighbor_type = neighbor_step.get("type", "")
            child_key = self._first_child_key(neighbor_type)
            if child_key is not None:
                dest_raw = neighbor_step.setdefault(child_key, [] if child_key != "branches" else {})
                if child_key == "branches":
                    # if_any_image: move into first branch.
                    keys = list(dest_raw.keys())
                    if not keys:
                        return False
                    dest_list = dest_raw[keys[0]]
                else:
                    dest_list = dest_raw
                raw.pop(idx)
                if direction == -1:
                    dest_list.append(node.step)
                else:
                    dest_list.insert(0, node.step)
                node.parent.clear_caches()
                return True

            # Simple swap.
            raw[idx], raw[new_idx] = raw[new_idx], raw[idx]
            node.parent.clear_caches()
            return True

        # Case 2: Move to a sibling branch (then/else, row/col, branch).
        parent_step = node.parent.step
        parent_type = parent_step.get("type", "")
        sibling_key = self._find_sibling_key_raw(parent_type, key, direction, parent_step)
        if sibling_key is not None:
            dest_raw = parent_step.setdefault(sibling_key, [])
            raw.pop(idx)
            if direction == 1:
                dest_raw.append(node.step)
            else:
                dest_raw.insert(0, node.step)
            node.parent.clear_caches()
            return True

        # Case 3: Move out of a child list into the parent's parent.
        grandparent = node.parent.parent
        if grandparent is not None:
            parent_key = node.parent.sibling_key()
            gp_raw = grandparent.step.get(parent_key, [])
            parent_idx = -1
            for i, s in enumerate(gp_raw):
                if s is node.parent.step:
                    parent_idx = i
                    break
            if parent_idx < 0:
                return False
            raw.pop(idx)
            insert_at = parent_idx if direction == -1 else parent_idx + 1
            gp_raw.insert(insert_at, node.step)
            node.parent.clear_caches()
            grandparent.clear_caches()
            return True

        # Parent is a root node → move into root_nodes.
        parent_in_roots = -1
        for i, rn in enumerate(self.root_nodes):
            if rn is node.parent:
                parent_in_roots = i
                break
        if parent_in_roots < 0:
            return False
        raw.pop(idx)
        insert_at = parent_in_roots if direction == -1 else parent_in_roots + 1
        self.root_nodes.insert(insert_at, node)
        self.steps.insert(insert_at, node.step)
        node.parent.clear_caches()
        node.parent = None
        return True

    def _move_root(self, node: StepNode, direction: int) -> bool:
        """Handle move for a root-level node."""
        try:
            idx = self.root_nodes.index(node)
        except ValueError:
            return False

        new_idx = idx + direction

        if 0 <= new_idx < len(self.root_nodes):
            neighbor = self.root_nodes[new_idx]
            neighbor_type = neighbor.step_type
            child_key = self._first_child_key(neighbor_type)
            if child_key is not None:
                dest_raw = neighbor.step.setdefault(child_key, [] if child_key != "branches" else {})
                if child_key == "branches":
                    keys = list(dest_raw.keys())
                    if not keys:
                        return False
                    dest_list = dest_raw[keys[0]]
                else:
                    dest_list = dest_raw
                self.root_nodes.pop(idx)
                self.steps.pop(idx)
                node.parent = neighbor
                if direction == -1:
                    dest_list.append(node.step)
                else:
                    dest_list.insert(0, node.step)
                neighbor.clear_caches()
                return True

            # Simple swap.
            self.root_nodes[idx], self.root_nodes[new_idx] = (
                self.root_nodes[new_idx],
                self.root_nodes[idx],
            )
            self.steps[idx], self.steps[new_idx] = self.steps[new_idx], self.steps[idx]
            return True

        return False

    @staticmethod
    def _first_child_key(step_type: str) -> str | None:
        """Return the first child-list key for a container step type."""
        from step_node import CONTAINER_CHILD_KEYS

        keys = CONTAINER_CHILD_KEYS.get(step_type, [])
        if keys:
            return keys[0]
        if step_type == "if_any_image":
            return "branches"
        return None

    @staticmethod
    def _find_sibling_key_raw(step_type: str, current_key: str, direction: int, step: dict | None = None) -> str | None:
        """Find the key of the next/prev sibling branch from raw step type."""
        from step_node import CONTAINER_CHILD_KEYS

        if step_type == "if_any_image" and step is not None:
            keys = list(step.get("branches", {}).keys())
            try:
                i = keys.index(current_key)
            except ValueError:
                return None
            next_i = i + direction
            if 0 <= next_i < len(keys):
                return keys[next_i]
            return None

        keys = CONTAINER_CHILD_KEYS.get(step_type, [])
        try:
            i = keys.index(current_key)
        except ValueError:
            return None
        next_i = i + direction
        if 0 <= next_i < len(keys):
            return keys[next_i]
        return None

    def _sync_parent_raw(self, node: StepNode) -> None:
        """After moving, clear caches and sync raw from the cached state.

        This must be called BEFORE any ``get_child_list`` or ``child_lists``
        access on the parent, because stale caches cause rebuilds from raw.
        """
        if node.parent is None:
            return
        parent = node.parent
        for key in CONTAINER_CHILD_KEYS.get(parent.step_type, []):
            cache_key = f"cached_children_{key}"
            cached = getattr(parent, cache_key, None)
            if cached is not None:
                parent.step[key] = [n.step for n in cached]
            else:
                # No cache: raw is already correct (only remove() modifies raw
                # without cache, and remove() only affects the source branch).
                pass
        if parent.step_type == "if_any_image":
            cached_branches = getattr(parent, "cached_branches", None)
            if cached_branches is not None:
                for branch_name, nodes in cached_branches.items():
                    parent.step.setdefault("branches", {})[branch_name] = [n.step for n in nodes]
        # Now clear all caches so next get_child_list rebuilds from synced raw.
        parent.clear_caches()
