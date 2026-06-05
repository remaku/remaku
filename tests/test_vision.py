from unittest.mock import MagicMock, patch

import numpy as np

import vision


class MockPath:
    def __init__(self, path: str, exists: bool = True):
        self._path = path
        self._exists = exists

    def exists(self) -> bool:
        return self._exists

    def __str__(self) -> str:
        return self._path


class TestLoadTemplates:
    def test_loads_existing_templates(self):
        names = ["btn", "icon"]
        mock_dir = MagicMock()
        mock_paths = {}

        for name in names:
            mock_paths[name] = MockPath(f"/tmp/{name}.png")

        mock_dir.__truediv__ = lambda self, name: mock_paths.get(name.replace(".png", ""), MagicMock())

        def decode(arr, flags):
            return np.zeros((10, 10), dtype=np.uint8)

        with (
            patch("vision.config.templates_dir", return_value=mock_dir),
            patch("vision.cv2.imdecode", side_effect=decode),
            patch("vision.np.fromfile", return_value=np.zeros(100, dtype=np.uint8)),
        ):
            result = vision.load_templates(names, macro_name="test")

        assert len(result) == 2
        assert "btn" in result
        assert "icon" in result

    def test_skips_missing_files(self):
        mock_dir = MagicMock()
        mock_path = MockPath("/tmp/missing.png", exists=False)
        mock_dir.__truediv__ = lambda self, name: mock_path

        with patch("vision.config.templates_dir", return_value=mock_dir):
            result = vision.load_templates(["missing"], macro_name="test")

        assert result == {}

    def test_skips_unreadable_files(self):
        mock_dir = MagicMock()
        mock_path = MockPath("/tmp/bad.png")
        mock_dir.__truediv__ = lambda self, name: mock_path

        with (
            patch("vision.config.templates_dir", return_value=mock_dir),
            patch("vision.cv2.imdecode", return_value=None),
            patch("vision.np.fromfile", return_value=np.zeros(100, dtype=np.uint8)),
        ):
            result = vision.load_templates(["bad"], macro_name="test")

        assert result == {}


class TestScaleTemplate:
    def test_no_scaling_when_same_size(self):
        template = np.zeros((10, 10), dtype=np.uint8)
        result = vision.scale_template(template, (100, 100), (100, 100))
        assert result is template

    def test_scales_down_when_frame_smaller(self):
        template = np.zeros((100, 100), dtype=np.uint8)
        result = vision.scale_template(template, (50, 50), (100, 100))
        assert result.shape == (50, 50)

    def test_scales_up_when_frame_larger(self):
        template = np.zeros((50, 50), dtype=np.uint8)
        result = vision.scale_template(template, (100, 100), (50, 50))
        assert result.shape == (100, 100)

    def test_minimum_size_one(self):
        template = np.zeros((10, 10), dtype=np.uint8)
        result = vision.scale_template(template, (1, 1), (1000, 1000))
        assert result.shape == (1, 1)


class TestToGray:
    def test_already_gray(self):
        gray = np.zeros((100, 100), dtype=np.uint8)
        result = vision.to_gray(gray)
        assert result is gray

    def test_bgr_to_gray(self):
        bgr = np.zeros((100, 100, 3), dtype=np.uint8)
        bgr[:, :, 2] = 255  # red channel
        result = vision.to_gray(bgr)
        assert result.ndim == 2
        assert result.shape == (100, 100)


class TestMatchOne:
    def test_perfect_match(self):
        rng = np.random.default_rng(42)
        frame = rng.integers(0, 256, (200, 200), dtype=np.uint8)
        template = frame[50:80, 60:90].copy()

        score, loc = vision.match_one(frame, template)
        assert score > 0.99
        assert loc == (60, 50)

    def test_no_match(self):
        rng = np.random.default_rng(42)
        frame = rng.integers(0, 128, (200, 200), dtype=np.uint8)
        template = rng.integers(128, 256, (30, 30), dtype=np.uint8)

        score, _ = vision.match_one(frame, template)
        assert score < 0.5

    def test_template_larger_than_frame(self):
        frame = np.zeros((50, 50), dtype=np.uint8)
        template = np.zeros((100, 100), dtype=np.uint8)

        # Should not crash; template is auto-scaled down
        score, _loc = vision.match_one(frame, template)
        assert isinstance(score, float)
