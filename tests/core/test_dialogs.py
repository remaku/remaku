from typing import ClassVar, cast

from PySide6.QtWidgets import QWidget

from remaku.core import dialogs


class FakeMessageDialog:
    instances: ClassVar[list["FakeMessageDialog"]] = []

    def __init__(self, title: str, content: str, parent) -> None:
        self.title = title
        self.content = content
        self.parent = parent
        self.exec_calls = 0
        FakeMessageDialog.instances.append(self)

    def exec(self) -> int:
        self.exec_calls += 1
        return 0


class FakeButton:
    def __init__(self) -> None:
        self.text = ""

    def setText(self, text: str) -> None:
        self.text = text


class FakeConfirmDialog:
    instances: ClassVar[list["FakeConfirmDialog"]] = []
    exec_result: ClassVar[int] = 1

    def __init__(self, title: str, content: str, parent) -> None:
        self.title = title
        self.content = content
        self.parent = parent
        self.yesButton = FakeButton()
        self.exec_calls = 0
        FakeConfirmDialog.instances.append(self)

    def exec(self) -> int:
        self.exec_calls += 1
        return self.exec_result


def test_show_message_dialog_executes_dialog(monkeypatch) -> None:
    FakeMessageDialog.instances.clear()
    parent = cast(QWidget, object())
    monkeypatch.setattr(dialogs, "MessageDialog", FakeMessageDialog)

    dialogs.show_message_dialog(parent, "Title", "Content")

    dialog = FakeMessageDialog.instances[0]
    assert dialog.parent is parent
    assert dialog.title == "Title"
    assert dialog.content == "Content"
    assert dialog.exec_calls == 1


def test_show_confirm_dialog_sets_yes_text_and_returns_result(monkeypatch) -> None:
    FakeConfirmDialog.instances.clear()
    FakeConfirmDialog.exec_result = 1
    parent = cast(QWidget, object())
    monkeypatch.setattr(dialogs, "ConfirmDialog", FakeConfirmDialog)

    result = dialogs.show_confirm_dialog(parent, "Title", "Content", yes_text="Delete")

    dialog = FakeConfirmDialog.instances[0]
    assert result is True
    assert dialog.parent is parent
    assert dialog.yesButton.text == "Delete"
    assert dialog.exec_calls == 1


def test_show_confirm_dialog_returns_false_for_rejected_dialog(monkeypatch) -> None:
    FakeConfirmDialog.instances.clear()
    FakeConfirmDialog.exec_result = 0
    monkeypatch.setattr(dialogs, "ConfirmDialog", FakeConfirmDialog)

    assert dialogs.show_confirm_dialog(cast(QWidget, object()), "Title", "Content") is False
