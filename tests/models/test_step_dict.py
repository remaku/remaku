from remaku.models.step_dict import (
    get_step_branch_names,
    get_step_branches,
    get_step_in_list_index,
    get_step_list,
    get_step_str,
    get_step_str_list,
    get_step_type,
    move_step_in_list,
)


def test_get_step_type_and_string_helpers_coerce_values() -> None:
    step = {"type": 123, "label": 456, "items": ["a", 2, None]}

    assert get_step_type(step) == "123"
    assert get_step_str(step, "label") == "456"
    assert get_step_str_list(step, "items") == ["a", "2", "None"]


def test_get_step_list_replaces_bad_value() -> None:
    step = {"steps": "bad"}

    result = get_step_list(step, "steps")

    assert result == []
    assert step["steps"] is result


def test_get_step_branches_replaces_bad_value() -> None:
    step = {"branches": []}

    result = get_step_branches(step)

    assert result == {}
    assert step["branches"] is result


def test_get_step_in_list_index_uses_identity() -> None:
    target = {"type": "key"}
    same_value = {"type": "key"}

    assert get_step_in_list_index([same_value, target], target) == 1
    assert get_step_in_list_index([same_value], target) == -1


def test_move_step_in_list_moves_item() -> None:
    steps = [{"id": "a"}, {"id": "b"}, {"id": "c"}]

    move_step_in_list(steps, 0, 2)

    assert [step["id"] for step in steps] == ["b", "c", "a"]


def test_get_step_branch_names_returns_branch_keys() -> None:
    assert get_step_branch_names({"branches": {"one": [], "two": []}}) == ["one", "two"]


def test_get_step_str_list_returns_empty_for_non_list() -> None:
    assert get_step_str_list({"items": "bad"}, "items") == []
