from collections.abc import Callable

from PySide6.QtWidgets import QWidget
from qfluentwidgets import Action, RoundMenu


def step_type_items() -> list[dict[str, str]]:
    return [
        {"id": "key", "label": "Key"},
        {"id": "delay", "label": "Delay"},
        {"id": "wait_image", "label": "Wait Image"},
        {"id": "hold_key_until_gone", "label": "Hold Key Until Gone"},
        {"id": "repeat", "label": "Repeat"},
        {"id": "if_image", "label": "If Image"},
        {"id": "if_any_image", "label": "If Any Image"},
        {"id": "grid_nav", "label": "Grid Navigation"},
    ]


def show_step_menu(parent: QWidget, anchor: QWidget, on_pick: Callable[[str], None]) -> None:
    menu = RoundMenu(parent=parent)

    for item in step_type_items():
        action = Action(parent.tr(item["label"]), parent)
        action.triggered.connect(lambda _checked, step_type=item["id"]: on_pick(step_type))
        menu.addAction(action)

    menu.exec(anchor.mapToGlobal(anchor.rect().bottomLeft()))
