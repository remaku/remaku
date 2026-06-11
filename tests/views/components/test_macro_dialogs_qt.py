from PySide6.QtWidgets import QWidget

from remaku.views.components.confirm_dialog import ConfirmDialog
from remaku.views.components.message_dialog import MessageDialog
from remaku.views.components.new_macro_dialog import NewMacroDialog
from remaku.views.components.rename_macro_dialog import RenameMacroDialog


def make_parent(qtbot) -> QWidget:
    parent = QWidget()
    parent.resize(640, 480)
    qtbot.addWidget(parent)
    return parent


def test_new_macro_dialog_returns_trimmed_value(qtbot) -> None:
    parent = make_parent(qtbot)
    dialog = NewMacroDialog(parent)

    assert dialog.label_edit is not None
    dialog.label_edit.setText("  Daily Run  ")

    assert dialog.value() == "Daily Run"
    assert dialog.yesButton.text() == "Create"
    assert dialog.cancelButton.text() == "Cancel"


def test_rename_macro_dialog_prefills_and_trims_value(qtbot) -> None:
    parent = make_parent(qtbot)
    dialog = RenameMacroDialog(parent, current_label="Old Name")

    assert dialog.label_edit is not None
    assert dialog.label_edit.text() == "Old Name"
    dialog.label_edit.setText("  New Name  ")

    assert dialog.value() == "New Name"
    assert dialog.yesButton.text() == "Save"


def test_message_dialog_hides_cancel_button(qtbot) -> None:
    parent = make_parent(qtbot)
    dialog = MessageDialog("Title", "Content", parent)

    assert dialog.title == "Title"
    assert dialog.content == "Content"
    assert dialog.yesButton.text() == "OK"
    assert dialog.cancelButton.isHidden()


def test_confirm_dialog_sets_button_text(qtbot) -> None:
    parent = make_parent(qtbot)
    dialog = ConfirmDialog("Title", "Content", parent)

    assert dialog.title == "Title"
    assert dialog.content == "Content"
    assert dialog.yesButton.text() == "OK"
    assert dialog.cancelButton.text() == "Cancel"
