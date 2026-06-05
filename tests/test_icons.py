"""Tests for the icon helper module."""

from unittest.mock import patch

from icons import SvgIconEngine


class TestSvgIconEngine:
    def test_clone_returns_new_instance(self):
        engine = SvgIconEngine(b"<svg></svg>")
        cloned = engine.clone()
        assert cloned is not engine
        assert isinstance(cloned, SvgIconEngine)
        assert cloned.raw_svg == engine.raw_svg

    def test_resolved_svg_dark_theme(self):
        with patch("icons.isDarkTheme", return_value=True):
            engine = SvgIconEngine(b'<svg fill="currentColor"></svg>')
            result = engine.resolved_svg()
            assert b"#ffffff" in result
            assert b"currentColor" not in result

    def test_resolved_svg_light_theme(self):
        with patch("icons.isDarkTheme", return_value=False):
            engine = SvgIconEngine(b'<svg fill="currentColor"></svg>')
            result = engine.resolved_svg()
            assert b"#000000" in result
            assert b"currentColor" not in result
