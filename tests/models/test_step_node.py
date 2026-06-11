from remaku.models.step_node import StepNode


def test_repeat_node_exposes_step_children() -> None:
    step = {"type": "repeat", "steps": [{"type": "key", "key": "enter"}]}
    node = StepNode(step)

    children = node.get_child_list("steps")

    assert node.is_container is True
    assert children[0].parent is node
    assert children[0].step["key"] == "enter"


def test_if_any_image_node_exposes_template_branches() -> None:
    step = {
        "type": "if_any_image",
        "templates": ["one", "two"],
        "branches": {"two": [{"type": "key", "key": "space"}]},
    }
    node = StepNode(step)

    branches = node.branches_map()

    assert list(branches) == ["one", "two"]
    assert branches["one"] == []
    assert branches["two"][0].parent is node


def test_remove_child_updates_parent_node_list() -> None:
    parent_step = {"type": "repeat", "steps": [{"type": "key", "key": "enter"}]}
    parent = StepNode(parent_step)
    child = parent.get_child_list("steps")[0]

    child.remove()

    assert parent.get_child_list("steps") == []
    assert parent_step["steps"] == [{"type": "key", "key": "enter"}]
    assert child.parent is None


def test_child_cache_tracks_node_list_after_insert_and_remove() -> None:
    parent = StepNode({"type": "repeat", "steps": [{"type": "key", "key": "enter"}]})
    first_child = parent.get_child_list("steps")[0]
    inserted = StepNode({"type": "delay", "ms": 10})

    inserted.insert_after(first_child)
    first_child.remove()

    children = parent.get_child_list("steps")

    assert children == [inserted]
    assert inserted.parent is parent


def test_filter_top_level_removes_descendants() -> None:
    parent = StepNode({"type": "repeat", "steps": [{"type": "key", "key": "enter"}]})
    child = parent.get_child_list("steps")[0]

    assert StepNode.filter_top_level([parent, child]) == [parent]
