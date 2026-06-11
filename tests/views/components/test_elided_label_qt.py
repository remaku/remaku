from PySide6.QtCore import Qt

from remaku.views.components.elided_label import ElidedBodyLabel


def test_elided_label_tracks_full_text(qtbot) -> None:
    label = ElidedBodyLabel("Long label")
    qtbot.addWidget(label)

    label.setText("Updated label")

    assert label.text() == "Updated label"
    assert label.text_content == "Updated label"
    assert label.sizeHint().width() > 0
    assert label.minimumSizeHint().width() == 0


def test_elided_label_updates_elide_mode(qtbot) -> None:
    label = ElidedBodyLabel("Long label")
    qtbot.addWidget(label)

    label.setElideMode(Qt.TextElideMode.ElideMiddle)

    assert label.elideMode() == Qt.TextElideMode.ElideMiddle
