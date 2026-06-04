"""Tests for the screen capture module."""

from unittest.mock import MagicMock, patch

import pytest

import capture


class TestMakeGrabber:
    @patch("capture.bettercam")
    def test_creates_grabber_successfully(self, mock_bettercam):
        mock_cam = MagicMock()
        mock_cam.width = 1920
        mock_cam.height = 1080
        mock_bettercam.create.return_value = mock_cam

        grabber = capture.make_grabber()

        assert grabber.screen_width == 1920
        assert grabber.screen_height == 1080
        mock_bettercam.create.assert_called_once_with(output_color="BGR")

    @patch("capture.bettercam")
    def test_retries_on_transient_failure(self, mock_bettercam):
        mock_cam = MagicMock()
        mock_cam.width = 1920
        mock_cam.height = 1080
        mock_bettercam.create.side_effect = [OSError("E_FAIL"), mock_cam]

        grabber = capture.make_grabber(max_retries=3, retry_delay=0.01)

        assert grabber.screen_width == 1920
        assert mock_bettercam.create.call_count == 2

    @patch("capture.bettercam")
    def test_raises_after_all_retries_exhausted(self, mock_bettercam):
        mock_bettercam.create.side_effect = OSError("E_FAIL")

        with pytest.raises(RuntimeError, match="failed to create grabber after 3 attempts"):
            capture.make_grabber(max_retries=3, retry_delay=0.01)

        assert mock_bettercam.create.call_count == 3

    @patch("capture.bettercam")
    def test_raises_com_error_after_all_retries(self, mock_bettercam):
        com_error = OSError("(-2147467259, 'unspecified error')")
        mock_bettercam.create.side_effect = com_error

        with pytest.raises(RuntimeError, match="failed to create grabber"):
            capture.make_grabber(max_retries=2, retry_delay=0.01)

        assert mock_bettercam.create.call_count == 2

    @patch("capture.bettercam")
    def test_succeeds_on_first_try_no_extra_calls(self, mock_bettercam):
        mock_cam = MagicMock()
        mock_cam.width = 1920
        mock_cam.height = 1080
        mock_bettercam.create.return_value = mock_cam

        grabber = capture.make_grabber(max_retries=3, retry_delay=0.01)

        assert grabber.screen_width == 1920
        mock_bettercam.create.assert_called_once()

    @patch("capture.bettercam")
    def test_custom_retry_parameters(self, mock_bettercam):
        mock_bettercam.create.side_effect = OSError("fail")

        with pytest.raises(RuntimeError, match="failed to create grabber after 2 attempts"):
            capture.make_grabber(max_retries=2, retry_delay=0.01)

        assert mock_bettercam.create.call_count == 2
