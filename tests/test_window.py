"""Tests for the window management module."""

from unittest.mock import MagicMock, patch

from window import (
    Rect,
    check_elevation_mismatch,
    client_rect,
    find_target_window,
    is_foreground,
    is_self_elevated,
    list_visible_windows,
)


class TestRect:
    def test_right_property(self):
        r = Rect(left=10, top=20, width=100, height=50)
        assert r.right == 110

    def test_bottom_property(self):
        r = Rect(left=10, top=20, width=100, height=50)
        assert r.bottom == 70


class TestListVisibleWindows:
    @patch("window.gw.getAllWindows")
    def test_returns_visible_with_titles(self, mock_get_all):
        w1 = MagicMock()
        w1.title = "Game"
        w1.visible = True
        w2 = MagicMock()
        w2.title = "  "
        w2.visible = True
        w3 = MagicMock()
        w3.title = "Editor"
        w3.visible = True
        w4 = MagicMock()
        w4.title = "Hidden"
        w4.visible = False
        mock_get_all.return_value = [w1, w2, w3, w4]

        result = list_visible_windows()
        assert result == ["Editor", "Game"]

    @patch("window.gw.getAllWindows")
    def test_empty_when_no_visible_windows(self, mock_get_all):
        mock_get_all.return_value = []
        assert list_visible_windows() == []


class TestFindTargetWindow:
    @patch("window.gw.getActiveWindow")
    def test_empty_title_returns_foreground(self, mock_get_active):
        win = MagicMock()
        mock_get_active.return_value = win
        assert find_target_window("") is win

    @patch("window.gw.getActiveWindow")
    def test_empty_title_none_when_no_foreground(self, mock_get_active):
        mock_get_active.return_value = None
        assert find_target_window("") is None

    @patch("window.gw.getWindowsWithTitle")
    def test_find_by_title(self, mock_get_windows):
        w1 = MagicMock()
        w1.title = "Game"
        w1.visible = True
        w1.width = 100
        w1.height = 100
        w2 = MagicMock()
        w2.title = "Game"
        w2.visible = True
        w2.width = 200
        w2.height = 200
        mock_get_windows.return_value = [w1, w2]

        result = find_target_window("Game")
        assert result is w2

    @patch("window.gw.getWindowsWithTitle")
    def test_no_match_returns_none(self, mock_get_windows):
        mock_get_windows.return_value = []
        assert find_target_window("NonExistent") is None

    @patch("window.gw.getWindowsWithTitle")
    def test_skips_invisible_windows(self, mock_get_windows):
        w1 = MagicMock()
        w1.title = "Game"
        w1.visible = False
        mock_get_windows.return_value = [w1]
        assert find_target_window("Game") is None


class TestClientRect:
    def test_returns_screen_coordinates(self):
        mock_win = MagicMock()
        mock_win._hWnd = 12345

        with (
            patch("window.win32gui.GetClientRect", return_value=(0, 0, 800, 600)),
            patch("window.win32gui.ClientToScreen", return_value=(100, 50)),
        ):
            result = client_rect(mock_win)

        assert result.left == 100
        assert result.top == 50
        assert result.width == 800
        assert result.height == 600


class TestIsForeground:
    def test_returns_true_when_foreground(self):
        mock_win = MagicMock()
        mock_win._hWnd = 12345
        with patch("window.win32gui.GetForegroundWindow", return_value=12345):
            assert is_foreground(mock_win) is True

    def test_returns_false_when_not_foreground(self):
        mock_win = MagicMock()
        mock_win._hWnd = 12345
        with patch("window.win32gui.GetForegroundWindow", return_value=99999):
            assert is_foreground(mock_win) is False

    def test_returns_false_on_exception(self):
        mock_win = MagicMock()
        mock_win._hWnd = 12345
        with patch("window.win32gui.GetForegroundWindow", side_effect=RuntimeError("fail")):
            assert is_foreground(mock_win) is False


class TestIsSelfElevated:
    def test_returns_true_when_admin(self):
        with patch("window.ctypes.windll.shell32.IsUserAnAdmin", return_value=1):
            assert is_self_elevated() is True

    def test_returns_false_when_not_admin(self):
        with patch("window.ctypes.windll.shell32.IsUserAnAdmin", return_value=0):
            assert is_self_elevated() is False

    def test_returns_false_on_exception(self):
        with patch("window.ctypes.windll.shell32.IsUserAnAdmin", side_effect=RuntimeError("fail")):
            assert is_self_elevated() is False


class TestCheckElevationMismatch:
    def test_returns_false_when_self_elevated(self):
        mock_win = MagicMock()
        with patch("window.is_self_elevated", return_value=True):
            assert check_elevation_mismatch(mock_win) is False

    def test_returns_true_when_target_elevated(self):
        mock_win = MagicMock()
        mock_win._hWnd = 12345

        with (
            patch("window.is_self_elevated", return_value=False),
            patch("window.win32process.GetWindowThreadProcessId", return_value=(1, 5678)),
            patch("window.win32api.OpenProcess") as mock_open,
            patch("window.win32security.OpenProcessToken") as mock_open_token,
            patch("window.win32security.GetTokenInformation", return_value=True),
            patch("window.win32api.CloseHandle"),
        ):
            mock_h = MagicMock()
            mock_open.return_value = mock_h
            mock_token = MagicMock()
            mock_open_token.return_value = mock_token

            assert check_elevation_mismatch(mock_win) is True

    def test_returns_true_when_check_fails(self):
        mock_win = MagicMock()
        mock_win._hWnd = 12345

        with (
            patch("window.is_self_elevated", return_value=False),
            patch("window.win32process.GetWindowThreadProcessId", side_effect=RuntimeError("fail")),
        ):
            assert check_elevation_mismatch(mock_win) is True

    def test_returns_false_when_target_not_elevated(self):
        mock_win = MagicMock()
        mock_win._hWnd = 12345

        with (
            patch("window.is_self_elevated", return_value=False),
            patch("window.win32process.GetWindowThreadProcessId", return_value=(1, 5678)),
            patch("window.win32api.OpenProcess") as mock_open,
            patch("window.win32security.OpenProcessToken") as mock_open_token,
            patch("window.win32security.GetTokenInformation", return_value=False),
            patch("window.win32api.CloseHandle"),
        ):
            mock_h = MagicMock()
            mock_open.return_value = mock_h
            mock_token = MagicMock()
            mock_open_token.return_value = mock_token

            assert check_elevation_mismatch(mock_win) is False
