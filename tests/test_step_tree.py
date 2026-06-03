"""Tests for step_tree module."""

import pytest

from step_node import StepNode
from step_tree import StepTree

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def simple_steps():
    return [
        {"type": "key", "key": "a"},
        {"type": "delay", "duration": 100},
        {"type": "key", "key": "b"},
    ]


@pytest.fixture
def nested_steps():
    return [
        {"type": "key", "key": "a"},
        {
            "type": "repeat",
            "count": 2,
            "steps": [
                {"type": "key", "key": "b"},
                {"type": "delay", "duration": 50},
            ],
        },
        {"type": "key", "key": "c"},
    ]


@pytest.fixture
def deeply_nested_steps():
    return [
        {
            "type": "repeat",
            "count": 1,
            "steps": [
                {
                    "type": "if_image",
                    "template": "btn",
                    "then": [{"type": "key", "key": "x"}],
                    "else": [{"type": "key", "key": "y"}],
                },
            ],
        },
    ]


# ---------------------------------------------------------------------------
# from_macro / basic construction
# ---------------------------------------------------------------------------


class TestConstruction:
    def test_from_macro(self):
        macro = {"steps": [{"type": "key", "key": "a"}]}
        tree = StepTree.from_macro(macro)
        assert len(tree.root_nodes) == 1
        assert tree.root_nodes[0].step_type == "key"

    def test_from_macro_empty(self):
        tree = StepTree.from_macro({})
        assert tree.root_nodes == []

    def test_direct_init(self, simple_steps):
        tree = StepTree(simple_steps)
        assert len(tree.root_nodes) == 3
        assert tree.steps is simple_steps


# ---------------------------------------------------------------------------
# flatten
# ---------------------------------------------------------------------------


class TestFlatten:
    def test_simple(self, simple_steps):
        tree = StepTree(simple_steps)
        flat = tree.flatten()
        assert len(flat) == 3
        assert [n.step_type for n in flat] == ["key", "delay", "key"]

    def test_nested(self, nested_steps):
        tree = StepTree(nested_steps)
        flat = tree.flatten()
        assert len(flat) == 5
        assert [n.step_type for n in flat] == ["key", "repeat", "key", "delay", "key"]

    def test_empty(self):
        tree = StepTree([])
        assert tree.flatten() == []


# ---------------------------------------------------------------------------
# find_node
# ---------------------------------------------------------------------------


class TestFindNode:
    def test_finds_by_identity(self, simple_steps):
        tree = StepTree(simple_steps)
        target = simple_steps[1]
        node = tree.find_node(target)
        assert node is not None
        assert node.step is target

    def test_returns_none_for_missing(self, simple_steps):
        tree = StepTree(simple_steps)
        other = {"type": "key", "key": "z"}
        assert tree.find_node(other) is None

    def test_finds_nested(self, nested_steps):
        tree = StepTree(nested_steps)
        inner = nested_steps[1]["steps"][0]
        node = tree.find_node(inner)
        assert node is not None
        assert node.step is inner
        assert node.parent is not None
        assert node.parent.step_type == "repeat"


# ---------------------------------------------------------------------------
# node_at
# ---------------------------------------------------------------------------


class TestNodeAt:
    def test_valid_index(self, simple_steps):
        tree = StepTree(simple_steps)
        node = tree.node_at(1)
        assert node is not None
        assert node.step_type == "delay"

    def test_out_of_range(self, simple_steps):
        tree = StepTree(simple_steps)
        assert tree.node_at(10) is None

    def test_negative_index(self, simple_steps):
        tree = StepTree(simple_steps)
        assert tree.node_at(-1) is None


# ---------------------------------------------------------------------------
# get_top_level
# ---------------------------------------------------------------------------


class TestGetTopLevel:
    def test_filters_children(self, nested_steps):
        tree = StepTree(nested_steps)
        flat = tree.flatten()
        top = tree.get_top_level(flat)
        assert len(top) == 3
        assert [n.step_type for n in top] == ["key", "repeat", "key"]

    def test_single_root(self, nested_steps):
        tree = StepTree(nested_steps)
        root = tree.root_nodes[1]
        assert tree.get_top_level([root]) == [root]


# ---------------------------------------------------------------------------
# wrap_in_repeat
# ---------------------------------------------------------------------------


class TestWrapInRepeat:
    def test_wrap_root_nodes(self, simple_steps):
        tree = StepTree(simple_steps)
        nodes = [tree.root_nodes[0], tree.root_nodes[2]]
        repeat = tree.wrap_in_repeat(nodes)
        assert repeat.step_type == "repeat"
        assert len(repeat.step["steps"]) == 2
        assert len(tree.root_nodes) == 2
        assert tree.root_nodes[0] is repeat

    def test_wrap_single_root(self, simple_steps):
        tree = StepTree(simple_steps)
        repeat = tree.wrap_in_repeat([tree.root_nodes[1]])
        assert repeat.step_type == "repeat"
        assert len(repeat.step["steps"]) == 1

    def test_wrap_all_roots(self, simple_steps):
        tree = StepTree(simple_steps)
        repeat = tree.wrap_in_repeat(list(tree.root_nodes))
        assert len(tree.root_nodes) == 1
        assert tree.root_nodes[0] is repeat
        assert len(repeat.step["steps"]) == 3

    def test_wrap_preserves_raw_steps(self, simple_steps):
        tree = StepTree(simple_steps)
        tree.wrap_in_repeat([tree.root_nodes[0], tree.root_nodes[2]])
        assert len(tree.steps) == 2
        assert tree.steps[0]["type"] == "repeat"

    def test_wrap_empty_raises(self, simple_steps):
        tree = StepTree(simple_steps)
        with pytest.raises(ValueError, match="empty"):
            tree.wrap_in_repeat([])

    def test_wrap_in_repeat_preserves_parent(self, nested_steps):
        tree = StepTree(nested_steps)
        repeat_node = tree.root_nodes[1]
        child_a = repeat_node.get_child_list("steps")[0]
        child_b = repeat_node.get_child_list("steps")[1]
        tree.wrap_in_repeat([child_a, child_b])
        new_repeat = repeat_node.get_child_list("steps")[0]
        assert new_repeat.step_type == "repeat"
        assert new_repeat.parent is repeat_node

    def test_wrap_root_level_inserts_at_correct_position(self):
        steps = [
            {"type": "key", "key": "a"},
            {"type": "key", "key": "b"},
            {"type": "key", "key": "c"},
        ]
        tree = StepTree(steps)
        tree.wrap_in_repeat([tree.root_nodes[0], tree.root_nodes[1]])
        assert tree.steps[0]["type"] == "repeat"
        assert tree.steps[1]["type"] == "key"


# ---------------------------------------------------------------------------
# duplicate_nodes
# ---------------------------------------------------------------------------


class TestDuplicateNodes:
    def test_duplicate_single(self, simple_steps):
        tree = StepTree(simple_steps)
        dups = tree.duplicate_nodes([tree.root_nodes[0]])
        assert len(dups) == 1
        assert dups[0].step_type == "key"
        assert dups[0].step is not simple_steps[0]
        assert len(tree.root_nodes) == 4

    def test_duplicate_preserves_original(self, simple_steps):
        tree = StepTree(simple_steps)
        original = tree.root_nodes[1]
        tree.duplicate_nodes([original])
        assert tree.root_nodes[1] is original
        assert tree.root_nodes[2].step_type == "delay"

    def test_duplicate_nested(self, nested_steps):
        tree = StepTree(nested_steps)
        repeat = tree.root_nodes[1]
        dups = tree.duplicate_nodes([repeat])
        assert len(dups) == 1
        assert dups[0].step_type == "repeat"
        assert len(tree.root_nodes) == 4

    def test_duplicate_multiple(self, simple_steps):
        tree = StepTree(simple_steps)
        dups = tree.duplicate_nodes([tree.root_nodes[0], tree.root_nodes[2]])
        assert len(dups) == 2
        assert len(tree.root_nodes) == 5


# ---------------------------------------------------------------------------
# sync_from_tree
# ---------------------------------------------------------------------------


class TestSyncFromTree:
    def test_sync_after_removal(self, nested_steps):
        tree = StepTree(nested_steps)
        repeat = tree.root_nodes[1]
        child = repeat.get_child_list("steps")[0]
        child.remove()
        tree.sync_from_tree()
        assert len(tree.steps) == 3
        assert len(tree.steps[1]["steps"]) == 1

    def test_sync_after_add(self, simple_steps):
        tree = StepTree(simple_steps)
        new_node = StepNode({"type": "delay", "duration": 999})
        new_node.parent = tree.root_nodes[0].parent
        tree.root_nodes.insert(1, new_node)
        tree.sync_from_tree()
        assert len(tree.steps) == 4
        assert tree.steps[1]["type"] == "delay"


# ---------------------------------------------------------------------------
# collect_template_refs
# ---------------------------------------------------------------------------


class TestCollectTemplateRefs:
    def test_collects_single(self):
        steps = [
            {"type": "wait_image", "template": "btn"},
            {"type": "key", "key": "a"},
        ]
        tree = StepTree(steps)
        refs = tree.collect_template_refs()
        assert refs == {"btn"}

    def test_collects_multiple(self):
        steps = [
            {"type": "wait_image", "template": "btn"},
            {"type": "if_any_image", "templates": ["icon", "logo"]},
        ]
        tree = StepTree(steps)
        refs = tree.collect_template_refs()
        assert refs == {"btn", "icon", "logo"}

    def test_collects_nested(self):
        steps = [
            {
                "type": "repeat",
                "count": 1,
                "steps": [{"type": "wait_image", "template": "nested"}],
            },
        ]
        tree = StepTree(steps)
        refs = tree.collect_template_refs()
        assert refs == {"nested"}

    def test_no_templates(self):
        steps = [{"type": "key", "key": "a"}]
        tree = StepTree(steps)
        assert tree.collect_template_refs() == set()

    def test_empty(self):
        tree = StepTree([])
        assert tree.collect_template_refs() == set()


# ---------------------------------------------------------------------------
# Deeply nested
# ---------------------------------------------------------------------------


class TestDeeplyNested:
    def test_flatten(self, deeply_nested_steps):
        tree = StepTree(deeply_nested_steps)
        flat = tree.flatten()
        assert len(flat) == 4
        types = [n.step_type for n in flat]
        assert types == ["repeat", "if_image", "key", "key"]

    def test_find_nested_child(self, deeply_nested_steps):
        tree = StepTree(deeply_nested_steps)
        target = deeply_nested_steps[0]["steps"][0]["then"][0]
        node = tree.find_node(target)
        assert node is not None
        assert node.step_type == "key"
        assert node.parent is not None
        assert node.parent.parent is not None
        assert node.parent.parent.parent is None

    def test_collect_refs_deep(self, deeply_nested_steps):
        deeply_nested_steps[0]["steps"][0]["template"] = "deep_btn"
        tree = StepTree(deeply_nested_steps)
        refs = tree.collect_template_refs()
        assert refs == {"deep_btn"}


# ---------------------------------------------------------------------------
# flatten_with_depth
# ---------------------------------------------------------------------------


class TestFlattenWithDepth:
    def test_simple(self, simple_steps):
        tree = StepTree(simple_steps)
        result = tree.flatten_with_depth()
        assert len(result) == 3
        assert [(n.step_type, d) for n, d in result] == [
            ("key", 0),
            ("delay", 0),
            ("key", 0),
        ]

    def test_nested(self, nested_steps):
        tree = StepTree(nested_steps)
        result = tree.flatten_with_depth()
        assert [(n.step_type, d) for n, d in result] == [
            ("key", 0),
            ("repeat", 0),
            ("key", 1),
            ("delay", 1),
            ("key", 0),
        ]

    def test_deeply_nested(self, deeply_nested_steps):
        tree = StepTree(deeply_nested_steps)
        result = tree.flatten_with_depth()
        assert [(n.step_type, d) for n, d in result] == [
            ("repeat", 0),
            ("if_image", 1),
            ("key", 2),
            ("key", 2),
        ]

    def test_if_image_branches(self):
        steps = [
            {
                "type": "if_image",
                "template": "btn",
                "then": [{"type": "key", "key": "t"}],
                "else": [{"type": "key", "key": "e"}],
            },
        ]
        tree = StepTree(steps)
        result = tree.flatten_with_depth()
        assert [(n.step_type, d) for n, d in result] == [
            ("if_image", 0),
            ("key", 1),
            ("key", 1),
        ]

    def test_grid_nav(self):
        steps = [
            {
                "type": "grid_nav",
                "rows": 2,
                "on_next_row": [{"type": "key", "key": "r"}],
                "on_next_col": [{"type": "key", "key": "c"}],
            },
        ]
        tree = StepTree(steps)
        result = tree.flatten_with_depth()
        assert [(n.step_type, d) for n, d in result] == [
            ("grid_nav", 0),
            ("key", 1),
            ("key", 1),
        ]

    def test_empty(self):
        tree = StepTree([])
        assert tree.flatten_with_depth() == []


# ---------------------------------------------------------------------------
# delete_node
# ---------------------------------------------------------------------------


class TestDeleteNode:
    def test_root_node(self, simple_steps):
        tree = StepTree(simple_steps)
        tree.delete_node(tree.root_nodes[1])
        assert len(tree.root_nodes) == 2
        assert len(tree.steps) == 2
        assert [n.step_type for n in tree.root_nodes] == ["key", "key"]

    def test_nested_node(self, nested_steps):
        tree = StepTree(nested_steps)
        repeat = tree.root_nodes[1]
        child = repeat.get_child_list("steps")[0]
        tree.delete_node(child)
        assert len(repeat.get_child_list("steps")) == 1
        assert len(repeat.step["steps"]) == 1

    def test_branch_node(self):
        then_step = {"type": "key", "key": "t"}
        steps = [{"type": "if_image", "then": [then_step], "else": []}]
        tree = StepTree(steps)
        if_node = tree.root_nodes[0]
        then_node = if_node.get_child_list("then")[0]
        tree.delete_node(then_node)
        assert len(if_node.get_child_list("then")) == 0
        assert len(if_node.step["then"]) == 0


# ---------------------------------------------------------------------------
# move_step
# ---------------------------------------------------------------------------


class TestMoveStep:
    def test_swap_with_leaf_sibling(self):
        steps = [
            {"type": "key", "key": "a"},
            {"type": "key", "key": "b"},
            {"type": "key", "key": "c"},
        ]
        tree = StepTree(steps)
        assert tree.move_step(tree.root_nodes[0], 1) is True
        assert [n.step["key"] for n in tree.root_nodes] == ["b", "a", "c"]
        assert [s["key"] for s in tree.steps] == ["b", "a", "c"]

    def test_swap_backward(self):
        steps = [
            {"type": "key", "key": "a"},
            {"type": "key", "key": "b"},
            {"type": "key", "key": "c"},
        ]
        tree = StepTree(steps)
        assert tree.move_step(tree.root_nodes[2], -1) is True
        assert [n.step["key"] for n in tree.root_nodes] == ["a", "c", "b"]
        assert [s["key"] for s in tree.steps] == ["a", "c", "b"]

    def test_move_into_block_down(self):
        steps = [
            {"type": "key", "key": "a"},
            {"type": "key", "key": "b"},
            {"type": "repeat", "count": 1, "steps": []},
        ]
        tree = StepTree(steps)
        assert tree.move_step(tree.root_nodes[1], 1) is True
        assert len(tree.root_nodes) == 2
        repeat = tree.root_nodes[1]
        assert repeat.step_type == "repeat"
        children_raw = repeat.step.get("steps", [])
        assert len(children_raw) == 1
        assert children_raw[0]["key"] == "b"

    def test_move_out_of_block_up(self, nested_steps):
        tree = StepTree(nested_steps)
        repeat = tree.root_nodes[1]
        child = repeat.get_child_list("steps")[0]
        assert tree.move_step(child, -1) is True
        assert child.parent is None
        assert len(tree.root_nodes) == 4
        assert tree.root_nodes[1] is child

    def test_move_out_of_block_down(self, nested_steps):
        tree = StepTree(nested_steps)
        repeat = tree.root_nodes[1]
        child = repeat.get_child_list("steps")[-1]
        assert tree.move_step(child, 1) is True
        assert child.parent is None
        assert tree.root_nodes[2] is child

    def test_cross_branch_then_to_else(self):
        then_step = {"type": "key", "key": "t"}
        else_step = {"type": "key", "key": "e"}
        steps = [{"type": "if_image", "then": [then_step], "else": [else_step]}]
        tree = StepTree(steps)
        if_node = tree.root_nodes[0]
        then_node = if_node.get_child_list("then")[0]
        assert tree.move_step(then_node, 1) is True
        assert if_node.step["then"] == []
        assert [s["key"] for s in if_node.step["else"]] == ["e", "t"]

    def test_cross_branch_else_to_then(self):
        then_step = {"type": "key", "key": "t"}
        else_step = {"type": "key", "key": "e"}
        steps = [{"type": "if_image", "then": [then_step], "else": [else_step]}]
        tree = StepTree(steps)
        if_node = tree.root_nodes[0]
        else_node = if_node.get_child_list("else")[0]
        assert tree.move_step(else_node, -1) is True
        assert if_node.step["else"] == []
        assert [s["key"] for s in if_node.step["then"]] == ["e", "t"]

    def test_cross_grid_nav_branches(self):
        row_step = {"type": "key", "key": "r"}
        col_step = {"type": "key", "key": "c"}
        steps = [{"type": "grid_nav", "on_next_row": [row_step], "on_next_col": [col_step]}]
        tree = StepTree(steps)
        grid = tree.root_nodes[0]
        row_node = grid.get_child_list("on_next_row")[0]
        assert tree.move_step(row_node, 1) is True
        assert grid.step["on_next_row"] == []
        assert [s["key"] for s in grid.step["on_next_col"]] == ["c", "r"]
        # Re-find col_node after cache clear and move it back.
        col_node = tree.find_node(col_step)
        assert col_node is not None
        assert tree.move_step(col_node, -1) is True
        assert [s["key"] for s in grid.step["on_next_row"]] == ["c"]
        assert [s["key"] for s in grid.step["on_next_col"]] == ["r"]

    def test_no_move_at_top_boundary(self, simple_steps):
        tree = StepTree(simple_steps)
        assert tree.move_step(tree.root_nodes[0], -1) is False

    def test_no_move_at_bottom_boundary(self, simple_steps):
        tree = StepTree(simple_steps)
        assert tree.move_step(tree.root_nodes[2], 1) is False

    def test_root_move_into_block(self):
        steps = [
            {"type": "key", "key": "a"},
            {"type": "repeat", "count": 1, "steps": []},
        ]
        tree = StepTree(steps)
        assert tree.move_step(tree.root_nodes[0], 1) is True
        assert len(tree.root_nodes) == 1
        repeat = tree.root_nodes[0]
        assert repeat.step_type == "repeat"
        children_raw = repeat.step.get("steps", [])
        assert len(children_raw) == 1
        assert children_raw[0]["key"] == "a"

    def test_raw_steps_preserved_after_moves(self):
        steps = [
            {"type": "key", "key": "a"},
            {"type": "key", "key": "b"},
            {"type": "key", "key": "c"},
        ]
        tree = StepTree(steps)
        tree.move_step(tree.root_nodes[0], 1)
        assert [s["key"] for s in tree.steps] == ["b", "a", "c"]
        tree.move_step(tree.root_nodes[2], -1)
        assert [s["key"] for s in tree.steps] == ["b", "c", "a"]

    def test_move_into_if_image_block(self):
        steps = [
            {"type": "key", "key": "a"},
            {"type": "if_image", "then": [], "else": []},
        ]
        tree = StepTree(steps)
        assert tree.move_step(tree.root_nodes[0], 1) is True
        assert len(tree.root_nodes) == 1
        if_node = tree.root_nodes[0]
        assert if_node.step_type == "if_image"
        then_raw = if_node.step.get("then", [])
        assert len(then_raw) == 1
        assert then_raw[0]["key"] == "a"
