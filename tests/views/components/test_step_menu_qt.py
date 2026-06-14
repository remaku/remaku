from typing import ClassVar

from PySide6.QtWidgets import QWidget

from remaku.views.components import step_menu


class FakeMenu:
    instances: ClassVar[list["FakeMenu"]] = []

    def __init__(self, parent=None) -> None:
        self.parent = parent
        self.actions = []
        self.exec_positions = []
        FakeMenu.instances.append(self)

    def addAction(self, action) -> None:
        self.actions.append(action)

    def exec(self, position) -> None:
        self.exec_positions.append(position)


def test_step_type_items_returns_expected_step_types(qtbot) -> None:
    items = step_menu.step_type_items()

    assert [item["id"] for item in items] == [
        "key",
        "delay",
        "text_input",
        "wait_image",
        "hold_key_until_gone",
        "repeat",
        "if_image",
        "if_any_image",
        "grid_nav",
    ]
    assert [item["label"] for item in items] == [
        "Key",
        "Delay",
        "Text Input",
        "Wait Image",
        "Hold Key Until Gone",
        "Repeat",
        "If Image",
        "If Any Image",
        "Grid Navigation",
    ]


def test_show_step_menu_adds_actions_and_triggers_pick(monkeypatch, qtbot) -> None:
    FakeMenu.instances = []
    monkeypatch.setattr(step_menu, "RoundMenu", FakeMenu)
    parent = QWidget()
    anchor = QWidget(parent)
    qtbot.addWidget(parent)
    picked = []

    step_menu.show_step_menu(parent, anchor, picked.append)
    menu = FakeMenu.instances[0]

    assert len(menu.actions) == 9
    assert menu.exec_positions == [anchor.mapToGlobal(anchor.rect().bottomLeft())]

    for action in menu.actions:
        action.triggered.emit()

    assert picked == [
        "key",
        "delay",
        "text_input",
        "wait_image",
        "hold_key_until_gone",
        "repeat",
        "if_image",
        "if_any_image",
        "grid_nav",
    ]
