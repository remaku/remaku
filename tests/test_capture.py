"""Tests for the screen capture module."""

import gc
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

import capture
from capture import Grabber
from window import Rect


class TestGrabber:
    def make_grabber(self, mock_cam):
        with patch("capture.bettercam.create", return_value=mock_cam):
            grabber = Grabber()
        return grabber

    def test_grab_success(self):
        mock_cam = MagicMock()
        mock_cam.width = 1920
        mock_cam.height = 1080
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        mock_cam.grab.return_value = frame
        grabber = self.make_grabber(mock_cam)

        result = grabber.grab(Rect(left=0, top=0, width=100, height=100))

        assert result is frame
        assert grabber.last_frame is frame
        mock_cam.grab.assert_called_once_with(region=(0, 0, 100, 100))

    def test_grab_clamps_to_screen(self):
        mock_cam = MagicMock()
        mock_cam.width = 1920
        mock_cam.height = 1080
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        mock_cam.grab.return_value = frame
        grabber = self.make_grabber(mock_cam)

        grabber.grab(Rect(left=-10, top=-10, width=2000, height=2000))

        mock_cam.grab.assert_called_once_with(region=(0, 0, 1920, 1080))

    def test_grab_invalid_rect(self):
        mock_cam = MagicMock()
        mock_cam.width = 1920
        mock_cam.height = 1080
        grabber = self.make_grabber(mock_cam)

        result = grabber.grab(Rect(left=100, top=100, width=0, height=100))
        assert result is None

        result = grabber.grab(Rect(left=100, top=100, width=100, height=0))
        assert result is None

    def test_grab_no_frame_returns_last(self):
        mock_cam = MagicMock()
        mock_cam.width = 1920
        mock_cam.height = 1080
        last_frame = np.zeros((50, 50, 3), dtype=np.uint8)
        mock_cam.grab.return_value = None
        grabber = self.make_grabber(mock_cam)
        grabber.last_frame = last_frame

        result = grabber.grab(Rect(left=0, top=0, width=100, height=100))

        assert result is last_frame

    def test_grab_no_frame_no_last_returns_none(self):
        mock_cam = MagicMock()
        mock_cam.width = 1920
        mock_cam.height = 1080
        mock_cam.grab.return_value = None
        grabber = self.make_grabber(mock_cam)

        result = grabber.grab(Rect(left=0, top=0, width=100, height=100))

        assert result is None

    def test_grab_none_for_zero_size_rect(self):
        mock_cam = MagicMock()
        mock_cam.width = 1920
        mock_cam.height = 1080
        grabber = self.make_grabber(mock_cam)

        result = grabber.grab(Rect(left=0, top=0, width=0, height=0))
        assert result is None

    def test_close(self):
        mock_cam = MagicMock()
        mock_cam.width = 1920
        mock_cam.height = 1080
        grabber = self.make_grabber(mock_cam)

        grabber.close()

    @pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning")
    def test_close_suppresses_exception(self):
        class BadCam:
            width = 1920
            height = 1080

            def __del__(self):
                raise RuntimeError("boom")

        with patch("capture.bettercam.create", return_value=BadCam()):
            grabber = Grabber()

        grabber.close()
        gc.collect()


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
