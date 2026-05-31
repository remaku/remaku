import numpy as np

import vision


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
