from PySide6.QtCore import Qt

from remaku.views.components.elided_label import ElidedBodyLabel, ElidedCaptionLabel


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


def test_elided_label_accepts_parent_constructor(qtbot) -> None:
    parent = ElidedBodyLabel("Parent")
    qtbot.addWidget(parent)
    label = ElidedCaptionLabel("Child", parent)

    assert label.parent() is parent
    assert label.text_content == "Child"


def test_elided_label_paint_event_handles_narrow_width(qtbot) -> None:
    label = ElidedBodyLabel("Very long label")
    qtbot.addWidget(label)
    label.resize(8, label.sizeHint().height())
    label.show()

    qtbot.waitExposed(label)
    label.repaint()

    assert label.text_content == "Very long label"
