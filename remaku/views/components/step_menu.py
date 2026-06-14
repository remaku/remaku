from collections.abc import Callable

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QWidget
from qfluentwidgets import Action, RoundMenu


def step_type_items() -> list[dict[str, str]]:
    return [
        {"id": "key", "label": QCoreApplication.translate("StepMenu", "Key")},
        {"id": "delay", "label": QCoreApplication.translate("StepMenu", "Delay")},
        {"id": "text_input", "label": QCoreApplication.translate("StepMenu", "Text Input")},
        {"id": "wait_image", "label": QCoreApplication.translate("StepMenu", "Wait Image")},
        {"id": "hold_key_until_gone", "label": QCoreApplication.translate("StepMenu", "Hold Key Until Gone")},
        {"id": "repeat", "label": QCoreApplication.translate("StepMenu", "Repeat")},
        {"id": "if_image", "label": QCoreApplication.translate("StepMenu", "If Image")},
        {"id": "if_any_image", "label": QCoreApplication.translate("StepMenu", "If Any Image")},
        {"id": "grid_nav", "label": QCoreApplication.translate("StepMenu", "Grid Navigation")},
    ]


def show_step_menu(parent: QWidget, anchor: QWidget, on_pick: Callable[[str], None]) -> None:
    menu = RoundMenu(parent=parent)

    for item in step_type_items():
        action = Action(item["label"], parent)
        action.triggered.connect(lambda _checked, step_type=item["id"]: on_pick(step_type))
        menu.addAction(action)

    menu.exec(anchor.mapToGlobal(anchor.rect().bottomLeft()))
