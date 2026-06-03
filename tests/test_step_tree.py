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
