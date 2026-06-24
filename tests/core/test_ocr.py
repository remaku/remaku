import numpy as np
import pytest

from remaku.core import ocr


def test_compare_number_operators() -> None:
    assert ocr.compare_number(999, "≥", 999)
    assert ocr.compare_number(1000, ">", 999)
    assert ocr.compare_number(9, "<", 10)
    assert ocr.compare_number(9, "≤", 9)
    assert ocr.compare_number(9, "=", 9)
    assert ocr.compare_number(8, "≠", 9)
    assert not ocr.compare_number(999, ">=", 999)
    assert not ocr.compare_number(8, "bad", 9)


def test_parse_digits_returns_integer_or_none() -> None:
    assert ocr.parse_digits("Skill Points: 999") == 999
    assert ocr.parse_digits("9 8 7") == 987
    assert ocr.parse_digits("no digits") is None


def test_resolve_region_scales_and_clamps() -> None:
    region = ocr.NumberRegion(x=1800, y=1000, width=400, height=200, capture_width=1920, capture_height=1080)

    resolved = ocr.resolve_region(region, (540, 960, 3))

    assert resolved == ocr.NumberRegion(900, 500, 60, 40, True, 960, 540)


def test_resolve_region_converts_absolute_coordinates() -> None:
    region = ocr.NumberRegion(x=110, y=220, width=30, height=40, relative=False)

    resolved = ocr.resolve_region(region, (200, 300, 3), origin_left=100, origin_top=200)

    assert resolved == ocr.NumberRegion(10, 20, 30, 40, True, 300, 200)


def test_crop_region_returns_empty_for_invalid_size() -> None:
    frame = np.ones((10, 10, 3), dtype=np.uint8)

    assert ocr.crop_region(frame, ocr.NumberRegion(0, 0, 0, 10)).size == 0


def test_read_number_uses_adapter_and_parses_digits() -> None:
    frame = np.ones((10, 20, 3), dtype=np.uint8) * 255
    calls = []

    def adapter(image: np.ndarray) -> str:
        calls.append(image)
        return "999"

    assert ocr.read_number(frame, ocr.NumberRegion(0, 0, 20, 10), adapter=adapter) == 999
    assert calls


def test_read_number_resolves_absolute_region_with_origin(monkeypatch) -> None:
    frame = np.ones((30, 30, 3), dtype=np.uint8) * 255
    calls = []
    monkeypatch.setattr(ocr, "preprocess_number_image", lambda image: image)

    def adapter(image: np.ndarray) -> str:
        calls.append(image)
        return "42"

    region = ocr.NumberRegion(110, 220, 2, 3, relative=False)

    assert ocr.read_number(frame, region, adapter=adapter, origin_left=100, origin_top=200) == 42
    assert calls[0].shape == (3, 2, 3)


def test_read_number_returns_none_for_unreadable_text() -> None:
    frame = np.ones((10, 20, 3), dtype=np.uint8) * 255

    assert ocr.read_number(frame, ocr.NumberRegion(0, 0, 20, 10), adapter=lambda image: "??") is None


def test_rapidocr_result_text_handles_recognition_only_result() -> None:
    assert ocr.rapidocr_result_text([["999", 0.99]]) == "999"


def test_rapidocr_result_text_sorts_detected_boxes_left_to_right() -> None:
    result = [
        [[[20, 0], [30, 0], [30, 10], [20, 10]], "9", 0.99],
        [[[0, 0], [10, 0], [10, 10], [0, 10]], "8", 0.99],
    ]

    assert ocr.rapidocr_result_text(result) == "89"


def test_rapidocr_digits_raises_when_engine_is_unavailable(monkeypatch) -> None:
    class BrokenRapidOCR:
        def __init__(self) -> None:
            raise RuntimeError("broken")

    monkeypatch.setattr(ocr, "rapidocr_engine", None)
    monkeypatch.setattr(ocr, "RapidOCR", BrokenRapidOCR)

    with pytest.raises(ocr.OcrUnavailableError):
        ocr.rapidocr_digits(np.ones((10, 10), dtype=np.uint8))


def test_rapidocr_digits_reuses_initialized_engine(monkeypatch) -> None:
    calls = []

    class FakeRapidOCR:
        def __init__(self) -> None:
            calls.append("init")

        def __call__(self, image: np.ndarray, use_det: bool, use_cls: bool):
            return [["999", 0.99]], None

    monkeypatch.setattr(ocr, "rapidocr_engine", None)
    monkeypatch.setattr(ocr, "RapidOCR", FakeRapidOCR)

    assert ocr.rapidocr_digits(np.ones((10, 10), dtype=np.uint8)) == "999"
    assert ocr.rapidocr_digits(np.ones((10, 10), dtype=np.uint8)) == "999"
    assert calls == ["init"]
