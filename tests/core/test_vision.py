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


def test_to_bgr_returns_existing_bgr_frame() -> None:
    frame = np.zeros((2, 2, 3), dtype=np.uint8)

    assert vision.to_bgr(frame) is frame


def test_to_bgr_converts_gray_frame(monkeypatch) -> None:
    frame = np.zeros((2, 2), dtype=np.uint8)
    converted = np.ones((2, 2, 3), dtype=np.uint8)
    calls = []
    monkeypatch.setattr(vision.cv2, "cvtColor", lambda image, code: calls.append((image, code)) or converted)

    assert vision.to_bgr(frame) is converted
    assert calls == [(frame, vision.cv2.COLOR_GRAY2BGR)]


def test_prepare_match_inputs_uses_color_when_both_inputs_are_color() -> None:
    frame = np.zeros((2, 2, 3), dtype=np.uint8)
    template = np.ones((1, 1, 3), dtype=np.uint8)

    prepared_frame, prepared_template = vision.prepare_match_inputs(frame, template, "color")

    assert prepared_frame is frame
    assert prepared_template is template


def test_prepare_match_inputs_falls_back_to_gray_for_legacy_gray_template(monkeypatch) -> None:
    frame = np.zeros((2, 2, 3), dtype=np.uint8)
    template = np.ones((1, 1), dtype=np.uint8)
    converted = np.zeros((2, 2), dtype=np.uint8)
    calls = []

    def fake_to_gray(image):
        calls.append(image)
        return image if image.ndim == 2 else converted

    monkeypatch.setattr(vision, "to_gray", fake_to_gray)

    prepared_frame, prepared_template = vision.prepare_match_inputs(frame, template, "color")

    assert prepared_frame is converted
    assert prepared_template is template
    assert calls == [frame, template]


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


def test_match_template_passes_color_inputs_to_opencv(monkeypatch) -> None:
    frame = np.zeros((10, 10, 3), dtype=np.uint8)
    template = np.zeros((2, 2, 3), dtype=np.uint8)
    calls = []
    monkeypatch.setattr(
        vision.cv2,
        "matchTemplate",
        lambda image, templ, method: calls.append((image, templ, method)) or np.array([[0.7]], dtype=np.float32),
    )
    monkeypatch.setattr(vision.cv2, "minMaxLoc", lambda result: (0.0, 0.7, (0, 0), (1, 2)))

    score, location = vision.match_template(frame, template, "color")

    assert score == 0.7
    assert location == (1, 2)
    assert calls == [(frame, template, vision.cv2.TM_CCOEFF_NORMED)]


def test_load_templates_skips_missing_files(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(vision, "template_path", lambda macro_id, template_id: tmp_path / f"{template_id}.png")

    assert vision.load_templates(["missing"], "macro") == {}


def test_load_templates_reads_existing_files(tmp_path, monkeypatch) -> None:
    image = np.ones((2, 2), dtype=np.uint8)
    template_file = tmp_path / "button.png"
    template_file.write_bytes(b"png")
    monkeypatch.setattr(vision, "template_path", lambda macro_id, template_id: template_file)
    calls = []
    monkeypatch.setattr(vision.cv2, "imdecode", lambda data, flags: calls.append(flags) or image)

    assert vision.load_templates(["button"], "macro") == {"button": image}
    assert calls == [vision.cv2.IMREAD_UNCHANGED]


def test_load_templates_skips_unreadable_files(tmp_path, monkeypatch) -> None:
    template_file = tmp_path / "button.png"
    template_file.write_bytes(b"png")
    monkeypatch.setattr(vision, "template_path", lambda macro_id, template_id: template_file)
    monkeypatch.setattr(vision.cv2, "imdecode", lambda data, flags: None)

    assert vision.load_templates(["button"], "macro") == {}
