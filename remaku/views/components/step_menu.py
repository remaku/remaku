from collections.abc import Callable

from PySide6.QtWidgets import QWidget
from qfluentwidgets import Action, RoundMenu


def step_type_items(parent: QWidget) -> list[dict[str, str]]:
    return [
        {"id": "key", "label": parent.tr("Key")},
        {"id": "delay", "label": parent.tr("Delay")},
        {"id": "wait_image", "label": parent.tr("Wait Image")},
        {"id": "hold_key_until_gone", "label": parent.tr("Hold Key Until Gone")},
        {"id": "repeat", "label": parent.tr("Repeat")},
        {"id": "if_image", "label": parent.tr("If Image")},
        {"id": "if_any_image", "label": parent.tr("If Any Image")},
        {"id": "grid_nav", "label": parent.tr("Grid Navigation")},
    ]


def show_step_menu(parent: QWidget, anchor: QWidget, on_pick: Callable[[str], None]) -> None:
    menu = RoundMenu(parent=parent)

    for item in step_type_items(parent):
        action = Action(item["label"], parent)
        action.triggered.connect(lambda _checked, step_type=item["id"]: on_pick(step_type))
        menu.addAction(action)

    menu.exec(anchor.mapToGlobal(anchor.rect().bottomLeft()))
