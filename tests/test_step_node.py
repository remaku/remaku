"""Tests for step_node module."""

import pytest

from step_node import StepNode

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def key_step():
    return {"type": "key", "key": "a"}


@pytest.fixture
def delay_step():
    return {"type": "delay", "duration": 100}


@pytest.fixture
def repeat_step():
    return {
        "type": "repeat",
        "count": 3,
        "steps": [
            {"type": "key", "key": "b"},
            {"type": "delay", "duration": 50},
        ],
    }


@pytest.fixture
def if_image_step():
    return {
        "type": "if_image",
        "template": "btn",
        "then": [{"type": "key", "key": "c"}],
        "else": [{"type": "key", "key": "d"}],
    }


@pytest.fixture
def if_any_image_step():
    return {
        "type": "if_any_image",
        "branches": {
            "tpl_a": [{"type": "key", "key": "e"}],
            "tpl_b": [{"type": "key", "key": "f"}],
        },
    }


@pytest.fixture
def grid_nav_step():
    return {
        "type": "grid_nav",
        "on_next_row": [{"type": "key", "key": "g"}],
        "on_next_col": [{"type": "key", "key": "h"}],
    }


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------


class TestProperties:
    def test_step_type(self, key_step):
        node = StepNode(key_step)
        assert node.step_type == "key"

    def test_step_type_missing(self):
        node = StepNode({})
        assert node.step_type == "?"

    def test_is_container_repeat(self, repeat_step):
        assert StepNode(repeat_step).is_container is True

    def test_is_container_if_image(self, if_image_step):
        assert StepNode(if_image_step).is_container is True

    def test_is_container_if_any_image(self, if_any_image_step):
        assert StepNode(if_any_image_step).is_container is True

    def test_is_container_grid_nav(self, grid_nav_step):
        assert StepNode(grid_nav_step).is_container is True

    def test_is_leaf_key(self, key_step):
        assert StepNode(key_step).is_leaf is True

    def test_is_leaf_delay(self, delay_step):
        assert StepNode(delay_step).is_leaf is True


# ---------------------------------------------------------------------------
# child_lists
# ---------------------------------------------------------------------------


class TestChildLists:
    def test_repeat_has_one_branch(self, repeat_step):
        node = StepNode(repeat_step)
        lists = node.child_lists()
        assert len(lists) == 1
        assert lists[0][0] == "steps"
        assert len(lists[0][1]) == 2

    def test_if_image_has_two_branches(self, if_image_step):
        node = StepNode(if_image_step)
        lists = node.child_lists()
        keys = [k for k, _ in lists]
        assert "then" in keys
        assert "else" in keys
        assert len(lists) == 2

    def test_if_any_image_has_dynamic_branches(self, if_any_image_step):
        node = StepNode(if_any_image_step)
        lists = node.child_lists()
        keys = [k for k, _ in lists]
        assert "tpl_a" in keys
        assert "tpl_b" in keys
        assert len(lists) == 2

    def test_grid_nav_has_two_branches(self, grid_nav_step):
        node = StepNode(grid_nav_step)
        lists = node.child_lists()
        keys = [k for k, _ in lists]
        assert "on_next_row" in keys
        assert "on_next_col" in keys
        assert len(lists) == 2

    def test_leaf_returns_empty(self, key_step):
        node = StepNode(key_step)
        assert node.child_lists() == []


# ---------------------------------------------------------------------------
# get_child_list / set_child_list
# ---------------------------------------------------------------------------


class TestGetSetChildList:
    def test_get_child_list_repeat(self, repeat_step):
        node = StepNode(repeat_step)
        children = node.get_child_list("steps")
        assert len(children) == 2
        assert children[0].step_type == "key"
        assert children[1].step_type == "delay"

    def test_get_child_list_invalid_key(self, repeat_step):
        node = StepNode(repeat_step)
        assert node.get_child_list("nonexistent") == []

    def test_get_child_list_if_image(self, if_image_step):
        node = StepNode(if_image_step)
        assert len(node.get_child_list("then")) == 1
        assert len(node.get_child_list("else")) == 1

    def test_set_child_list_repeat(self, repeat_step):
        node = StepNode(repeat_step)
        new_children = [StepNode({"type": "key", "key": "z"})]
        node.set_child_list("steps", new_children)
        assert len(node.get_child_list("steps")) == 1
        assert node.step["steps"][0]["key"] == "z"
        assert new_children[0].parent is node

    def test_set_child_list_if_any_image(self, if_any_image_step):
        node = StepNode(if_any_image_step)
        new_branch = [StepNode({"type": "key", "key": "new"})]
        node.set_child_list("tpl_a", new_branch)
        assert len(node.get_child_list("tpl_a")) == 1
        assert node.step["branches"]["tpl_a"][0]["key"] == "new"


# ---------------------------------------------------------------------------
# all_descendants
# ---------------------------------------------------------------------------


class TestAllDescendants:
    def test_repeat_descendants(self, repeat_step):
        node = StepNode(repeat_step)
        desc = node.all_descendants()
        assert len(desc) == 2
        assert desc[0].step_type == "key"
        assert desc[1].step_type == "delay"

    def test_if_image_descendants(self, if_image_step):
        node = StepNode(if_image_step)
        desc = node.all_descendants()
        types = [d.step_type for d in desc]
        assert types.count("key") == 2

    def test_nested_descendants(self):
        inner = {"type": "repeat", "count": 1, "steps": [{"type": "key", "key": "x"}]}
        outer = {"type": "repeat", "count": 1, "steps": [inner]}
        node = StepNode(outer)
        desc = node.all_descendants()
        assert len(desc) == 2
        assert desc[0].step_type == "repeat"
        assert desc[1].step_type == "key"

    def test_leaf_no_descendants(self, key_step):
        node = StepNode(key_step)
        assert node.all_descendants() == []


# ---------------------------------------------------------------------------
# is_descendant_of
# ---------------------------------------------------------------------------


class TestIsDescendantOf:
    def test_direct_child(self, repeat_step):
        node = StepNode(repeat_step)
        child = node.get_child_list("steps")[0]
        assert child.is_descendant_of(node) is True

    def test_nested_child(self):
        inner = {"type": "repeat", "count": 1, "steps": [{"type": "key", "key": "x"}]}
        outer = {"type": "repeat", "count": 1, "steps": [inner]}
        root = StepNode(outer)
        inner_node = root.get_child_list("steps")[0]
        leaf = inner_node.get_child_list("steps")[0]
        assert leaf.is_descendant_of(root) is True
        assert leaf.is_descendant_of(inner_node) is True

    def test_not_descendant(self, repeat_step, key_step):
        root = StepNode(repeat_step)
        other = StepNode(key_step)
        child = root.get_child_list("steps")[0]
        assert child.is_descendant_of(other) is False

    def test_self_not_descendant(self, key_step):
        node = StepNode(key_step)
        assert node.is_descendant_of(node) is False

    def test_root_has_no_parent(self, key_step):
        node = StepNode(key_step)
        assert node.is_descendant_of(node) is False


# ---------------------------------------------------------------------------
# Sibling navigation
# ---------------------------------------------------------------------------


class TestSiblingNavigation:
    def test_next_sibling(self, repeat_step):
        node = StepNode(repeat_step)
        children = node.get_child_list("steps")
        assert children[0].next_sibling() is children[1]

    def test_next_sibling_last(self, repeat_step):
        node = StepNode(repeat_step)
        children = node.get_child_list("steps")
        assert children[1].next_sibling() is None

    def test_prev_sibling(self, repeat_step):
        node = StepNode(repeat_step)
        children = node.get_child_list("steps")
        assert children[1].prev_sibling() is children[0]

    def test_prev_sibling_first(self, repeat_step):
        node = StepNode(repeat_step)
        children = node.get_child_list("steps")
        assert children[0].prev_sibling() is None

    def test_index_in_parent(self, repeat_step):
        node = StepNode(repeat_step)
        children = node.get_child_list("steps")
        assert children[0].index_in_parent() == 0
        assert children[1].index_in_parent() == 1

    def test_index_in_parent_root(self, key_step):
        node = StepNode(key_step)
        assert node.index_in_parent() == -1

    def test_sibling_key(self, repeat_step):
        node = StepNode(repeat_step)
        child = node.get_child_list("steps")[0]
        assert child.sibling_key() == "steps"

    def test_sibling_key_root(self, key_step):
        node = StepNode(key_step)
        assert node.sibling_key() == ""


# ---------------------------------------------------------------------------
# Tree mutation
# ---------------------------------------------------------------------------


class TestMutation:
    def test_remove(self, repeat_step):
        node = StepNode(repeat_step)
        children = node.get_child_list("steps")
        target = children[0]
        target.remove()
        assert target.parent is None
        assert len(node.get_child_list("steps")) == 1

    def test_remove_root(self, key_step):
        node = StepNode(key_step)
        node.remove()
        assert node.parent is None

    def test_insert_after(self, repeat_step):
        node = StepNode(repeat_step)
        children = node.get_child_list("steps")
        new = StepNode({"type": "key", "key": "new"})
        new.insert_after(children[0])
        assert new.parent is node
        updated = node.get_child_list("steps")
        assert len(updated) == 3
        assert updated[1] is new

    def test_append_to(self, repeat_step):
        node = StepNode(repeat_step)
        children = node.get_child_list("steps")
        target = children[0]
        new_list: list[StepNode] = []
        target.append_to(new_list)
        assert len(new_list) == 1
        assert new_list[0] is target
        assert len(node.get_child_list("steps")) == 1

    def test_insert_in(self, repeat_step):
        node = StepNode(repeat_step)
        children = node.get_child_list("steps")
        target = children[0]
        new_list: list[StepNode] = []
        target.insert_in(new_list, 0)
        assert len(new_list) == 1
        assert new_list[0] is target


# ---------------------------------------------------------------------------
# filter_top_level
# ---------------------------------------------------------------------------


class TestFilterTopLevel:
    def test_filters_descendants(self):
        parent_step = {
            "type": "repeat",
            "count": 1,
            "steps": [{"type": "key", "key": "a"}],
        }
        parent = StepNode(parent_step)
        child = parent.get_child_list("steps")[0]
        result = StepNode.filter_top_level([parent, child])
        assert len(result) == 1
        assert result[0] is parent

    def test_keeps_all_if_no_ancestry(self):
        a = StepNode({"type": "key", "key": "a"})
        b = StepNode({"type": "key", "key": "b"})
        result = StepNode.filter_top_level([a, b])
        assert len(result) == 2

    def test_empty_list(self):
        assert StepNode.filter_top_level([]) == []

    def test_deep_nesting(self):
        inner = {"type": "repeat", "count": 1, "steps": [{"type": "key", "key": "x"}]}
        outer = {"type": "repeat", "count": 1, "steps": [inner]}
        root = StepNode(outer)
        inner_node = root.get_child_list("steps")[0]
        leaf = inner_node.get_child_list("steps")[0]
        result = StepNode.filter_top_level([root, inner_node, leaf])
        assert len(result) == 1
        assert result[0] is root


# ---------------------------------------------------------------------------
# Repr
# ---------------------------------------------------------------------------


class TestRepr:
    def test_repr(self, key_step):
        node = StepNode(key_step)
        r = repr(node)
        assert "key" in r
        assert "StepNode" in r


# ---------------------------------------------------------------------------
# all_child_lists
# ---------------------------------------------------------------------------


class TestAllChildLists:
    def test_repeat(self):
        step = {"type": "repeat", "steps": [{"type": "key", "key": "a"}]}
        node = StepNode(step)
        result = node.all_child_lists()
        assert len(result) == 1
        assert len(result[0]) == 1

    def test_if_image(self):
        step = {"type": "if_image", "then": [], "else": []}
        node = StepNode(step)
        result = node.all_child_lists()
        assert len(result) == 2

    def test_leaf(self):
        node = StepNode({"type": "key", "key": "a"})
        assert node.all_child_lists() == []


# ---------------------------------------------------------------------------
# next_sibling / prev_sibling with no parent
# ---------------------------------------------------------------------------


class TestSiblingNoParent:
    def test_next_sibling_no_parent(self):
        node = StepNode({"type": "key", "key": "a"})
        assert node.next_sibling() is None

    def test_prev_sibling_no_parent(self):
        node = StepNode({"type": "key", "key": "a"})
        assert node.prev_sibling() is None


# ---------------------------------------------------------------------------
# insert_after with no parent
# ---------------------------------------------------------------------------


class TestInsertAfterNoParent:
    def test_sibling_has_no_parent(self):
        a = StepNode({"type": "key", "key": "a"})
        b = StepNode({"type": "key", "key": "b"})
        b.insert_after(a)
        # a has no parent, so insert_after is a no-op
        assert b.parent is None


# ---------------------------------------------------------------------------
# append_to / insert_in with parent
# ---------------------------------------------------------------------------


class TestAppendToWithParent:
    def test_sets_parent(self):
        parent_step = {"type": "repeat", "steps": []}
        parent = StepNode(parent_step)
        child_list = parent.get_child_list("steps")
        new_node = StepNode({"type": "key", "key": "x"})
        new_node.append_to(child_list, parent=parent)
        assert new_node.parent is parent
        assert len(child_list) == 1

    def test_removes_from_old_parent(self):
        old_parent_step = {"type": "repeat", "steps": [{"type": "key", "key": "a"}]}
        old_parent = StepNode(old_parent_step)
        child = old_parent.get_child_list("steps")[0]

        new_parent_step = {"type": "repeat", "steps": []}
        new_parent = StepNode(new_parent_step)
        new_list = new_parent.get_child_list("steps")

        child.append_to(new_list, parent=new_parent)
        assert child.parent is new_parent
        assert len(old_parent.get_child_list("steps")) == 0


class TestInsertInWithParent:
    def test_sets_parent(self):
        parent_step = {"type": "repeat", "steps": []}
        parent = StepNode(parent_step)
        child_list = parent.get_child_list("steps")
        new_node = StepNode({"type": "key", "key": "x"})
        new_node.insert_in(child_list, 0, parent=parent)
        assert new_node.parent is parent
        assert len(child_list) == 1


# ---------------------------------------------------------------------------
# branches_map cache hit
# ---------------------------------------------------------------------------


class TestBranchesMapCache:
    def test_cache_hit(self):
        step = {"type": "if_any_image", "branches": {"a": [{"type": "key", "key": "x"}]}}
        node = StepNode(step)
        result1 = node.branches_map()
        result2 = node.branches_map()
        assert result1 is result2


# ---------------------------------------------------------------------------
# sibling_key / sibling_index edge cases
# ---------------------------------------------------------------------------


class TestSiblingKeyEdgeCases:
    def test_no_match_returns_empty(self):
        parent_step = {"type": "repeat", "steps": []}
        parent = StepNode(parent_step)
        orphan = StepNode({"type": "key", "key": "x"})
        orphan.parent = parent
        assert orphan.sibling_key() == ""


class TestSiblingIndexEdgeCases:
    def test_not_found_returns_negative(self):
        parent_step = {"type": "repeat", "steps": [{"type": "key", "key": "a"}]}
        parent = StepNode(parent_step)
        child = parent.get_child_list("steps")[0]
        other = StepNode({"type": "key", "key": "y"})
        assert other.sibling_index([child]) == -1


# ---------------------------------------------------------------------------
# clear_caches
# ---------------------------------------------------------------------------


class TestClearCaches:
    def test_clears_repeat_cache(self):
        step = {"type": "repeat", "steps": [{"type": "key", "key": "a"}]}
        node = StepNode(step)
        _ = node.get_child_list("steps")  # populate cache
        assert hasattr(node, "cached_children_steps")
        node.clear_caches()
        assert not hasattr(node, "cached_children_steps")

    def test_clears_if_image_cache(self):
        step = {"type": "if_image", "then": [], "else": []}
        node = StepNode(step)
        _ = node.get_child_list("then")
        _ = node.get_child_list("else")
        node.clear_caches()
        assert not hasattr(node, "cached_children_then")
        assert not hasattr(node, "cached_children_else")

    def test_clears_if_any_image_cache(self):
        step = {"type": "if_any_image", "branches": {"a": []}}
        node = StepNode(step)
        _ = node.branches_map()
        assert hasattr(node, "cached_branches")
        node.clear_caches()
        assert not hasattr(node, "cached_branches")

    def test_no_cache_no_error(self):
        node = StepNode({"type": "key", "key": "a"})
        node.clear_caches()  # should not raise
