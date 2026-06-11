import numpy as np

from remaku.core import capture
from remaku.core.capture import CaptureBackend, Grabber
from remaku.core.window import Rect


class FakeBetterCam:
    width = 800
    height = 600

    def __init__(self, frame: np.ndarray | None = None) -> None:
        self.frame: np.ndarray | None = frame if frame is not None else np.ones((2, 2, 3), dtype=np.uint8)
        self.regions: list[tuple[int, int, int, int]] = []

    def grab(self, region: tuple[int, int, int, int]):
        self.regions.append(region)
        return self.frame


class FakeMss:
    def __init__(self) -> None:
        self.monitors = [{"width": 1024, "height": 768}]
        self.requests: list[dict] = []
        self.closed = False

    def grab(self, request: dict) -> np.ndarray:
        self.requests.append(request)
        return np.ones((request["height"], request["width"], 4), dtype=np.uint8)

    def close(self) -> None:
        self.closed = True


def test_grabber_uses_bettercam_when_initial_grab_succeeds(monkeypatch) -> None:
    fake_cam = FakeBetterCam()
    monkeypatch.setattr(capture.bettercam, "create", lambda **kwargs: fake_cam)

    grabber = Grabber()

    assert grabber.backend == CaptureBackend.BETTERCAM
    assert grabber.screen_width == 800
    assert grabber.screen_height == 600


def test_grabber_falls_back_to_mss_when_bettercam_fails(monkeypatch) -> None:
    fake_mss = FakeMss()

    def raise_create(**kwargs):
        raise RuntimeError("no camera")

    monkeypatch.setattr(capture.bettercam, "create", raise_create)
    monkeypatch.setattr(capture.mss, "mss", lambda: fake_mss)

    grabber = Grabber()

    assert grabber.backend == CaptureBackend.MSS
    assert grabber.sct is fake_mss
    assert grabber.screen_width == 1024
    assert grabber.screen_height == 768


def test_grab_clamps_rect_to_screen(monkeypatch) -> None:
    fake_cam = FakeBetterCam()
    monkeypatch.setattr(capture.bettercam, "create", lambda **kwargs: fake_cam)
    grabber = Grabber()

    frame = grabber.grab(Rect(left=-10, top=-5, width=30, height=25))

    assert frame is fake_cam.frame
    assert fake_cam.regions[-1] == (0, 0, 20, 20)


def test_grab_returns_none_for_empty_rect(monkeypatch) -> None:
    fake_cam = FakeBetterCam()
    monkeypatch.setattr(capture.bettercam, "create", lambda **kwargs: fake_cam)
    grabber = Grabber()

    assert grabber.grab(Rect(left=900, top=0, width=10, height=10)) is None


def test_grab_returns_last_frame_when_backend_returns_none(monkeypatch) -> None:
    first_frame = np.ones((2, 2, 3), dtype=np.uint8)
    fake_cam = FakeBetterCam(first_frame)
    monkeypatch.setattr(capture.bettercam, "create", lambda **kwargs: fake_cam)
    grabber = Grabber()
    grabber.last_frame = first_frame
    fake_cam.frame = None

    assert grabber.grab(Rect(left=0, top=0, width=10, height=10)) is first_frame


def test_mss_grab_returns_bgr_channels(monkeypatch) -> None:
    fake_mss = FakeMss()

    def raise_create(**kwargs):
        raise RuntimeError("no camera")

    monkeypatch.setattr(capture.bettercam, "create", raise_create)
    monkeypatch.setattr(capture.mss, "mss", lambda: fake_mss)
    grabber = Grabber()

    frame = grabber.grab_frame(1, 2, 4, 6)

    assert frame is not None
    assert frame.shape == (4, 3, 3)
    assert fake_mss.requests == [{"left": 1, "top": 2, "width": 3, "height": 4}]


def test_close_closes_mss_backend(monkeypatch) -> None:
    fake_mss = FakeMss()

    def raise_create(**kwargs):
        raise RuntimeError("no camera")

    monkeypatch.setattr(capture.bettercam, "create", raise_create)
    monkeypatch.setattr(capture.mss, "mss", lambda: fake_mss)
    grabber = Grabber()

    grabber.close()

    assert fake_mss.closed is True
