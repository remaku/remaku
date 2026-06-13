from typing import Any

StepDict = dict[str, Any]


def get_step_type(step: StepDict, default: str = "") -> str:
    return str(step.get("type", default))


def get_step_list(step: StepDict, key: str) -> list[StepDict]:
    value = step.setdefault(key, [])
    if isinstance(value, list):
        return value

    step[key] = []
    return step[key]


def get_step_branches(step: StepDict) -> dict[str, list[StepDict]]:
    value = step.setdefault("branches", {})
    if isinstance(value, dict):
        return value

    step["branches"] = {}
    return step["branches"]


def get_step_branch_names(step: StepDict) -> list[str]:
    return list(get_step_branches(step).keys())


def get_step_in_list_index(steps: list[StepDict], target: StepDict) -> int:
    for index, step in enumerate(steps):
        if step is target:
            return index

    return -1


def move_step_in_list(steps: list[StepDict], source_index: int, dest_index: int) -> None:
    step = steps.pop(source_index)
    steps.insert(dest_index, step)


def get_step_str(step: StepDict, key: str, default: str = "") -> str:
    return str(step.get(key, default))


def get_step_str_list(step: StepDict, key: str) -> list[str]:
    value = step.get(key, [])
    if not isinstance(value, list):
        return []

    return [str(item) for item in value]
