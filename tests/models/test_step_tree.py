import pytest

from remaku.models.step_tree import StepTree


def test_flatten_and_find_node_by_path(sample_steps: list[dict]) -> None:
    tree = StepTree(sample_steps)

    flat = tree.flatten()
    nested_wait = tree.find_node_by_path((("steps", 1), ("steps", 1)))

    assert [node.step["type"] for node in flat] == ["key", "repeat", "delay", "wait_image", "if_image", "key", "delay"]
    assert nested_wait is not None
    assert nested_wait.step["template"] == "start"


def test_add_step_to_root_and_container(sample_steps: list[dict]) -> None:
    tree = StepTree(sample_steps)
    repeat_node = tree.root_nodes[1]

    root_node = tree.add_step(None, {"type": "key", "key": "esc"})
    child_node = tree.add_step(repeat_node, {"type": "key", "key": "tab"})

    assert tree.steps[-1] is root_node.step
    assert sample_steps[1]["steps"][-1] is child_node.step
    assert child_node.parent is repeat_node


def test_wrap_root_nodes_in_repeat_reflects_derived_steps(sample_steps: list[dict]) -> None:
    tree = StepTree(sample_steps)

    repeat_node = tree.wrap_in_repeat([tree.root_nodes[0], tree.root_nodes[1]])

    assert tree.steps[0] is repeat_node.step
    assert repeat_node.step["type"] == "repeat"
    assert [step["type"] for step in repeat_node.step["steps"]] == ["key", "repeat"]


def test_duplicate_nodes_inserts_deep_copy(sample_steps: list[dict]) -> None:
    tree = StepTree(sample_steps)
    original = tree.root_nodes[0]

    duplicates = tree.duplicate_nodes([original])

    assert len(duplicates) == 1
    assert tree.steps[1] is duplicates[0].step
    assert duplicates[0].step == original.step
    assert duplicates[0].step is not original.step


def test_delete_root_node_reflects_derived_steps(sample_steps: list[dict]) -> None:
    tree = StepTree(sample_steps)
    deleted = tree.root_nodes[0]

    tree.delete_node(deleted)

    assert [step["type"] for step in tree.steps] == ["repeat", "if_image"]
    assert deleted.parent is None


def test_nested_container_steps_reflect_node_tree() -> None:
    steps = [
        {"type": "if_image", "then": [{"type": "key", "key": "enter"}], "else": []},
        {"type": "grid_nav", "on_next_row": [], "on_next_col": []},
    ]
    tree = StepTree(steps)
    if_node = tree.root_nodes[0]
    grid_node = tree.root_nodes[1]

    then_node = tree.add_step_to_branch(if_node, "then", {"type": "delay", "ms": 10})
    else_node = tree.add_step_to_branch(if_node, "else", {"type": "key", "key": "esc"})
    row_node = tree.add_step_to_branch(grid_node, "on_next_row", {"type": "key", "key": "down"})
    col_node = tree.add_step_to_branch(grid_node, "on_next_col", {"type": "key", "key": "right"})

    assert tree.steps[0]["then"][-1] is then_node.step
    assert tree.steps[0]["else"][-1] is else_node.step
    assert tree.steps[1]["on_next_row"][-1] is row_node.step
    assert tree.steps[1]["on_next_col"][-1] is col_node.step


def test_if_any_image_branches_reflect_node_tree() -> None:
    step = {"type": "if_any_image", "templates": ["one", "two"], "branches": {"two": []}}
    tree = StepTree([step])
    parent = tree.root_nodes[0]

    one_node = tree.add_step_to_any_branch(parent, "one", {"type": "key", "key": "enter"})
    two_node = tree.add_step_to_any_branch(parent, "two", {"type": "delay", "ms": 25})

    assert list(tree.steps[0]["branches"]) == ["two", "one"]
    assert tree.steps[0]["branches"]["one"][0] is one_node.step
    assert tree.steps[0]["branches"]["two"][0] is two_node.step


def test_if_image_else_raw_key_survives_tree_round_trip() -> None:
    tree = StepTree([{"type": "if_image", "then": [], "else": [{"type": "delay", "ms": 50}]}])

    assert "else" in tree.steps[0]
    assert "else_" not in tree.steps[0]
    assert tree.steps[0]["else"][0]["ms"] == 50


def test_collect_template_refs_includes_single_and_multi_template_steps() -> None:
    steps = [
        {"type": "wait_image", "template": "one"},
        {"type": "if_any_image", "templates": ["two", "three"], "branches": {}},
    ]

    assert StepTree(steps).collect_template_refs() == {"one", "two", "three"}


def test_move_root_into_neighbor_container(sample_steps: list[dict]) -> None:
    tree = StepTree(sample_steps)
    first = tree.root_nodes[0]

    moved = tree.move_step(first, 1)

    assert moved is True
    assert first.parent is tree.root_nodes[0]
    assert tree.steps[0]["steps"][0]["type"] == "key"


def test_from_macro_uses_macro_steps_list() -> None:
    macro = {"steps": [{"type": "key", "key": "enter"}]}

    tree = StepTree.from_macro(macro)

    assert tree.steps == macro["steps"]
    assert tree.root_nodes[0].step["key"] == "enter"


def test_insert_steps_after_preserves_insert_order(sample_steps: list[dict]) -> None:
    tree = StepTree(sample_steps)
    target = tree.root_nodes[0]

    inserted = tree.insert_steps_after(target, [{"type": "delay", "ms": 1}, {"type": "key", "key": "tab"}])

    assert [node.step["type"] for node in inserted] == ["delay", "key"]
    assert [step["type"] for step in tree.steps[:3]] == ["key", "delay", "key"]


def test_steps_property_reflects_reordered_root_nodes(sample_steps: list[dict]) -> None:
    tree = StepTree(sample_steps)
    tree.root_nodes[0], tree.root_nodes[1] = tree.root_nodes[1], tree.root_nodes[0]

    assert [step["type"] for step in tree.steps[:2]] == ["repeat", "key"]


def test_steps_property_reflects_child_node_order() -> None:
    steps = [{"type": "repeat", "steps": [{"type": "key", "key": "a"}, {"type": "key", "key": "b"}]}]
    tree = StepTree(steps)
    repeat_node = tree.root_nodes[0]
    children = repeat_node.get_child_list("steps")
    children[0], children[1] = children[1], children[0]

    assert [step["key"] for step in tree.steps[0]["steps"]] == ["b", "a"]


def test_can_move_reports_root_and_nested_boundaries(sample_steps: list[dict]) -> None:
    tree = StepTree(sample_steps)
    first = tree.root_nodes[0]
    repeat_child = tree.root_nodes[1].get_child_list("steps")[0]

    assert tree.can_move(first, -1) is False
    assert tree.can_move(first, 1) is True
    assert tree.can_move(repeat_child, -1) is True


def test_move_between_if_image_branches() -> None:
    step = {
        "type": "if_image",
        "then": [{"type": "key", "key": "enter"}],
        "else": [{"type": "key", "key": "esc"}],
    }
    tree = StepTree([step])
    then_node = tree.root_nodes[0].get_child_list("then")[0]

    moved = tree.move_step(then_node, 1)

    serialized = tree.steps[0]

    assert moved is True
    assert serialized["then"] == []
    assert [child["key"] for child in serialized["else"]] == ["enter", "esc"]


def test_steps_property_writes_cached_if_any_branches() -> None:
    step = {"type": "if_any_image", "templates": ["one"], "branches": {"one": [{"type": "key", "key": "a"}]}}
    tree = StepTree([step])
    parent = tree.root_nodes[0]
    child = parent.get_child_list("one")[0]
    child.step["key"] = "b"

    assert tree.steps[0]["branches"]["one"][0]["key"] == "b"


def test_find_node_by_path_rejects_invalid_paths(sample_steps: list[dict]) -> None:
    tree = StepTree(sample_steps)

    assert tree.find_node_by_path(()) is None
    assert tree.find_node_by_path((("then", 0),)) is None
    assert tree.find_node_by_path((("steps", 99),)) is None


def test_node_at_and_find_node_miss(sample_steps: list[dict]) -> None:
    tree = StepTree(sample_steps)

    assert tree.node_at(-1) is None
    assert tree.node_at(999) is None
    assert tree.find_node({"type": "key", "key": "missing"}) is None


def test_wrap_in_repeat_rejects_empty_or_unrelated_nodes(sample_steps: list[dict]) -> None:
    tree = StepTree(sample_steps)
    unrelated = StepTree([{"type": "key"}]).root_nodes[0]

    with pytest.raises(ValueError, match="Cannot wrap an empty list of nodes"):
        tree.wrap_in_repeat([])

    with pytest.raises(ValueError, match="Cannot wrap nodes from different sibling lists"):
        tree.wrap_in_repeat([unrelated])


def test_move_step_out_of_nested_container_to_root() -> None:
    tree = StepTree([{"type": "repeat", "steps": [{"type": "key", "key": "a"}]}])
    child = tree.root_nodes[0].get_child_list("steps")[0]

    assert tree.move_step(child, 1) is True
    assert child.parent is None
    assert [step["type"] for step in tree.steps] == ["repeat", "key"]


def test_move_step_rejects_missing_node() -> None:
    tree = StepTree([{"type": "key", "key": "a"}])
    missing = StepTree([{"type": "key", "key": "b"}]).root_nodes[0]

    assert tree.move_step(missing, 1) is False
    assert tree.can_move(missing, 1) is False


def test_move_root_and_can_move_root_boundaries(sample_steps: list[dict]) -> None:
    tree = StepTree(sample_steps)
    first = tree.root_nodes[0]
    child = tree.root_nodes[1].get_child_list("steps")[0]

    assert tree.move_root(child, 1) is False
    assert tree.can_move_root(child, 1) is False
    assert tree.can_move_root(first, -1) is False
    assert tree.move_root(first, 1) is True
    assert first.parent is tree.root_nodes[0]


def test_next_prev_sibling_and_insert_node_after_fallback(sample_steps: list[dict]) -> None:
    tree = StepTree(sample_steps)
    first = tree.root_nodes[0]
    second = tree.root_nodes[1]
    inserted = StepTree([{"type": "delay", "ms": 1}]).root_nodes[0]

    assert tree.next_sibling(first) is second
    assert tree.prev_sibling(second) is first

    tree.insert_node_after(None, inserted)

    assert tree.root_nodes[-1] is inserted
    assert inserted.parent is None


def test_default_child_key_and_find_sibling_key_for_if_any() -> None:
    tree = StepTree([{"type": "if_any_image", "templates": ["one", "two"], "branches": {}}])
    parent = tree.root_nodes[0]

    assert tree.default_child_key(parent) == "one"
    assert tree.find_sibling_key(parent, "one", 1) == "two"
    assert tree.find_sibling_key(parent, "missing", 1) is None


def test_try_move_into_container_rejects_leaf_neighbor(sample_steps: list[dict]) -> None:
    tree = StepTree(sample_steps)
    source_list = tree.root_nodes
    leaf_neighbor = source_list[0]

    assert tree.try_move_into_container(source_list, 1, leaf_neighbor, 1) is False
