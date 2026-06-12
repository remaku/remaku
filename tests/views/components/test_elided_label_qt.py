from PySide6.QtCore import Qt

from remaku.views.components import elided_label
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


def test_elided_label_paint_event_draws_elided_text(monkeypatch, qtbot) -> None:
    label = ElidedBodyLabel("Very long label")
    qtbot.addWidget(label)
    drawn = []

    class FakePainter:
        def __init__(self, widget) -> None:
            self.widget = widget

        def setRenderHint(self, hint) -> None:
            drawn.append(("hint", hint))

        def setPen(self, color) -> None:
            drawn.append(("pen", color))

        def drawText(self, rect, alignment, text) -> None:
            drawn.append((rect, alignment, text))

    class FakeMetrics:
        def __init__(self, font) -> None:
            self.font = font

        def elidedText(self, text, mode, width):
            return f"{text}:{mode.value}:{width}"

    monkeypatch.setattr(elided_label, "QPainter", FakePainter)
    monkeypatch.setattr(elided_label, "QFontMetrics", FakeMetrics)

    label.paintEvent(None)

    assert drawn[-1][2].startswith("Very long label:")
