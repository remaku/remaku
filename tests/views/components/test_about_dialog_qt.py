from qfluentwidgets import BodyLabel, SubtitleLabel

from remaku.views.components.about_dialog import AboutDialog
from tests.views.components.test_macro_dialogs_qt import make_parent


def test_about_dialog_shows_version_and_close_button(qtbot) -> None:
    parent = make_parent(qtbot)
    dialog = AboutDialog(parent, version="1.2.3")

    subtitles = dialog.findChildren(SubtitleLabel)

    assert dialog.version == "1.2.3"
    assert dialog.yesButton.text() == "Close"
    assert dialog.cancelButton.isHidden()
    assert any(label.text() == "Remaku v1.2.3" for label in subtitles)


def test_about_dialog_shows_project_links_and_contact(qtbot) -> None:
    parent = make_parent(qtbot)
    dialog = AboutDialog(parent, version="1.2.3")
    labels = dialog.findChildren(BodyLabel)
    texts = [label.text() for label in labels]
    linked_labels = [label for label in labels if label.openExternalLinks()]

    assert any("image-recognition-driven desktop macro tool" in text for text in texts)
    assert any("https://github.com/remaku/remaku" in text for text in texts)
    assert any("https://discord.gg/MZfks29yTA" in text for text in texts)
    assert any("mailto:hello@remaku.com" in text for text in texts)
    assert any("AGPL-3.0" in text for text in texts)
    assert len(linked_labels) == 3
