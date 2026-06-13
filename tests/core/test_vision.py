import numpy as np

from remaku.core import vision


def test_to_gray_returns_existing_gray_frame() -> None:
    frame = np.array([[1, 2], [3, 4]], dtype=np.uint8)

    assert vision.to_gray(frame) is frame


def test_to_gray_converts_color_frame(monkeypatch) -> None:
    frame = np.zeros((2, 2, 3), dtype=np.uint8)
    converted = np.ones((2, 2), dtype=np.uint8)
    calls = []
    monkeypatch.setattr(vision.cv2, "cvtColor", lambda image, code: calls.append((image, code)) or converted)

    assert vision.to_gray(frame) is converted
    assert calls == [(frame, vision.cv2.COLOR_BGR2GRAY)]


def test_scale_template_returns_original_when_capture_matches_frame() -> None:
    template = np.ones((4, 6), dtype=np.uint8)

    assert vision.scale_template(template, (10, 20), (20, 10)) is template


def test_scale_template_resizes_by_capture_ratio(monkeypatch) -> None:
    template = np.ones((10, 20), dtype=np.uint8)
    resized = np.ones((5, 10), dtype=np.uint8)
    calls = []
    monkeypatch.setattr(vision.cv2, "resize", lambda image, size: calls.append((image, size)) or resized)

    result = vision.scale_template(template, (50, 100), (200, 100))

    assert result is resized
    assert calls == [(template, (10, 5))]


def test_match_template_resizes_oversized_template(monkeypatch) -> None:
    frame = np.zeros((10, 10), dtype=np.uint8)
    template = np.zeros((20, 20), dtype=np.uint8)
    resized = np.zeros((9, 9), dtype=np.uint8)
    calls = []
    monkeypatch.setattr(vision.cv2, "resize", lambda image, size: calls.append((image, size)) or resized)
    monkeypatch.setattr(vision.cv2, "matchTemplate", lambda image, templ, method: np.array([[0.5]], dtype=np.float32))
    monkeypatch.setattr(vision.cv2, "minMaxLoc", lambda result: (0.0, 0.5, (0, 0), (3, 4)))

    score, location = vision.match_template(frame, template)

    assert score == 0.5
    assert location == (3, 4)
    assert calls == [(template, (9, 9))]


def test_load_templates_skips_missing_files(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(vision, "template_path", lambda macro_id, template_id: tmp_path / f"{template_id}.png")

    assert vision.load_templates(["missing"], "macro") == {}


def test_load_templates_reads_existing_files(tmp_path, monkeypatch) -> None:
    image = np.ones((2, 2), dtype=np.uint8)
    template_file = tmp_path / "button.png"
    template_file.write_bytes(b"png")
    monkeypatch.setattr(vision, "template_path", lambda macro_id, template_id: template_file)
    monkeypatch.setattr(vision.cv2, "imdecode", lambda data, flags: image)

    assert vision.load_templates(["button"], "macro") == {"button": image}


def test_load_templates_skips_unreadable_files(tmp_path, monkeypatch) -> None:
    template_file = tmp_path / "button.png"
    template_file.write_bytes(b"png")
    monkeypatch.setattr(vision, "template_path", lambda macro_id, template_id: template_file)
    monkeypatch.setattr(vision.cv2, "imdecode", lambda data, flags: None)

    assert vision.load_templates(["button"], "macro") == {}
