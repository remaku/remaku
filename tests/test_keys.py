"""Tests for keys module."""

from unittest.mock import patch

import pytest


class TestSleepMs:
    @patch("keys.time.sleep")
    def test_sleep_no_jitter(self, mock_sleep):
        from keys import sleep_ms

        sleep_ms(100)
        mock_sleep.assert_called_once_with(0.1)

    @patch("keys.time.sleep")
    @patch("keys.random.uniform", return_value=50.0)
    def test_sleep_with_jitter(self, mock_uniform, mock_sleep):
        from keys import sleep_ms

        sleep_ms(100, jitter_ms=50)
        mock_uniform.assert_called_once_with(0, 50)
        mock_sleep.assert_called_once_with(0.15)

    @patch("keys.time.sleep")
    def test_sleep_zero_ms(self, mock_sleep):
        from keys import sleep_ms

        sleep_ms(0)
        mock_sleep.assert_called_once_with(0.0)


class TestTap:
    @patch("keys.sleep_ms")
    @patch("keys.pdi.keyUp")
    @patch("keys.pdi.keyDown")
    def test_tap_success(self, mock_down, mock_up, mock_sleep):
        from keys import tap

        tap("a", hold_ms=100, gap_ms=50, jitter_ms=0)
        mock_down.assert_called_once_with("a")
        mock_up.assert_called_once_with("a")
        assert mock_sleep.call_count == 2
        mock_sleep.assert_any_call(100, 0)
        mock_sleep.assert_any_call(50, 0)

    @patch("keys.sleep_ms")
    @patch("keys.pdi.keyUp")
    @patch("keys.pdi.keyDown", side_effect=Exception("down fail"))
    def test_tap_keydown_fails(self, mock_down, mock_up, mock_sleep):
        from keys import tap

        tap("a")
        mock_down.assert_called_once_with("a")
        mock_up.assert_not_called()
        mock_sleep.assert_not_called()

    @patch("keys.sleep_ms")
    @patch("keys.pdi.keyUp", side_effect=Exception("up fail"))
    @patch("keys.pdi.keyDown")
    def test_tap_keyup_fails(self, mock_down, mock_up, mock_sleep):
        from keys import tap

        tap("a", hold_ms=100, gap_ms=50, jitter_ms=0)
        mock_down.assert_called_once_with("a")
        mock_up.assert_called_once_with("a")
        assert mock_sleep.call_count == 2


class TestHeld:
    @patch("keys.pdi.keyUp")
    @patch("keys.pdi.keyDown")
    def test_held_success(self, mock_down, mock_up):
        from keys import held

        with held("shift"):
            mock_down.assert_called_once_with("shift")
            mock_up.assert_not_called()
        mock_up.assert_called_once_with("shift")

    @patch("keys.pdi.keyDown", side_effect=Exception("down fail"))
    def test_held_keydown_fails(self, mock_down):
        from keys import held

        with pytest.raises(Exception, match="down fail"), held("shift"):
            pass

    @patch("keys.pdi.keyUp", side_effect=Exception("up fail"))
    @patch("keys.pdi.keyDown")
    def test_held_keyup_fails(self, mock_down, mock_up):
        from keys import held

        with held("shift"):
            pass
        mock_down.assert_called_once_with("shift")
        mock_up.assert_called_once_with("shift")
