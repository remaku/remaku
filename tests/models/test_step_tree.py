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
