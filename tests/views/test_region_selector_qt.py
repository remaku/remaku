import numpy as np
from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QImage, QKeyEvent, QPixmap

from remaku.views import region_selector
from remaku.views.region_selector import RegionSelector


class FakeScreen:
    def __init__(self, pixmap: QPixmap) -> None:
        self.pixmap = pixmap

    def grabWindow(self, window_id: int) -> QPixmap:
        assert window_id == 0
        return self.pixmap


def make_pixmap(width: int = 8, height: int = 6) -> QPixmap:
    image = QImage(width, height, QImage.Format.Format_BGR888)
    image.fill(1)
    return QPixmap.fromImage(image)


def make_selector(monkeypatch, qtbot) -> RegionSelector:
    monkeypatch.setattr(region_selector.QApplication, "primaryScreen", lambda: FakeScreen(make_pixmap()))
    selector = RegionSelector("macro")
    selector.resize(4, 3)
    qtbot.addWidget(selector)
    return selector


def test_region_selector_maps_widget_rect_to_frame_rect(monkeypatch, qtbot) -> None:
    selector = make_selector(monkeypatch, qtbot)

    frame_rect = selector.to_frame_rect(QRect(1, 1, 2, 1))

    assert frame_rect == QRect(2, 2, 4, 2)


def test_region_selector_save_region_writes_template_and_emits_signal(tmp_path, monkeypatch, qtbot) -> None:
    selector = make_selector(monkeypatch, qtbot)
    encoded = np.array([1, 2, 3], dtype=np.uint8)
    monkeypatch.setattr(region_selector.time, "time", lambda: 123.0)
    monkeypatch.setattr(region_selector, "templates_dir", lambda macro_id: tmp_path / "templates" / macro_id)
    monkeypatch.setattr(region_selector.cv2, "cvtColor", lambda image, code: image[:, :, 0])
    monkeypatch.setattr(region_selector.cv2, "imencode", lambda extension, image: (True, encoded))

    with qtbot.waitSignal(selector.region_selected, timeout=100) as blocker:
        selector.save_region(QRect(0, 0, 2, 2))

    assert blocker.args == ["123", 8, 6]
    assert (tmp_path / "templates" / "macro" / "123.png").read_bytes() == encoded.tobytes()


def test_region_selector_escape_emits_cancelled(monkeypatch, qtbot) -> None:
    selector = make_selector(monkeypatch, qtbot)
    event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)

    with qtbot.waitSignal(selector.cancelled, timeout=100):
        selector.keyPressEvent(event)

    assert selector.selecting is False
