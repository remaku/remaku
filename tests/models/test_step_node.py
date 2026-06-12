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


def test_leaf_node_reports_no_children_or_siblings() -> None:
    node = StepNode({"type": "key", "key": "enter"})

    assert node.is_container is False
    assert node.is_leaf is True
    assert node.child_lists() == []
    assert node.get_child_list("steps") == []
    assert node.next_sibling() is None
    assert node.prev_sibling() is None
    assert node.index_in_parent() == -1
    assert node.sibling_key() == ""


def test_child_sibling_navigation_and_index() -> None:
    parent = StepNode({"type": "repeat", "steps": [{"type": "key", "key": "a"}, {"type": "key", "key": "b"}]})
    first, second = parent.get_child_list("steps")

    assert first.next_sibling() is second
    assert second.prev_sibling() is first
    assert second.index_in_parent() == 1
    assert first.sibling_key() == "steps"


def test_set_child_list_and_append_insert_assign_parent() -> None:
    parent = StepNode({"type": "repeat", "steps": []})
    first = StepNode({"type": "key", "key": "a"})
    second = StepNode({"type": "key", "key": "b"})

    parent.set_child_list("steps", [first])
    second.insert_in(parent.get_child_list("steps"), 0, parent)

    assert parent.get_child_list("steps") == [second, first]
    assert first.parent is parent
    assert second.parent is parent

    moved = StepNode({"type": "delay"}, parent=parent)
    moved.append_to(parent.get_child_list("steps"), parent)

    assert moved.parent is parent
    assert parent.get_child_list("steps")[-1] is moved


def test_if_any_set_child_list_and_clear_caches() -> None:
    parent = StepNode({"type": "if_any_image", "templates": ["one"], "branches": {}})
    child = StepNode({"type": "key", "key": "a"})

    parent.set_child_list("one", [child])
    assert parent.get_child_list("one") == [child]
    assert child.parent is parent

    parent.clear_caches()

    assert parent.get_child_list("one") == []


def test_repr_includes_step_type() -> None:
    assert repr(StepNode({"type": "delay"})).startswith("StepNode(delay")
