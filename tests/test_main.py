"""Tests for the application entry point."""

# pyright: reportArgumentType=false, reportAttributeAccessIssue=false

import contextlib
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import config as cfg
import main as main_mod


def _exit_raiser(code=0):
    """Replace sys.exit with a function that raises SystemExit."""
    raise SystemExit(code)


class TestMain:
    @pytest.fixture(autouse=True)
    def reset_sys_argv(self):
        original = sys.argv.copy()
        yield
        sys.argv = original

    def _make_conf(self):
        conf = cfg.get_defaults()
        conf.general.language = "en"
        conf.general.theme = "system"
        return conf

    def _run_main_and_catch_exit(self):
        """Call main_mod.main(), swallowing the SystemExit raised by _exit_raiser."""
        with contextlib.suppress(SystemExit):
            main_mod.main()

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------

    def test_main_flow(self, tmp_path: Path):
        fake_conf = self._make_conf()
        logs = tmp_path / "logs"
        logs.mkdir()

        with patch.object(main_mod, "sys") as mock_sys:
            mock_sys.argv = sys.argv
            mock_sys.exit = _exit_raiser
            mock_sys.stderr = sys.stderr

            with patch.object(main_mod, "QApplication") as mock_qapp, patch.object(main_mod, "MainWindow") as mock_mw:
                mock_app = MagicMock()
                mock_qapp.return_value = mock_app
                mock_window = MagicMock()
                mock_mw.return_value = mock_window

                with (
                    patch.object(main_mod, "logger") as mock_logger,
                    patch.object(main_mod, "QIcon"),
                    patch.object(main_mod, "QFont"),
                    patch.object(main_mod, "Theme"),
                    patch.object(main_mod, "setTheme"),
                    patch.object(main_mod, "i18n"),
                    patch.object(main_mod.cfg, "load", return_value=fake_conf),
                    patch.object(main_mod.cfg, "logs_dir", return_value=logs),
                    patch.object(main_mod.os.environ, "setdefault") as mock_env,
                ):
                    self._run_main_and_catch_exit()

        mock_qapp.assert_called_once_with(sys.argv)
        mock_app.exec.assert_called_once()
        mock_mw.assert_called_once()
        mock_window.show.assert_called_once()
        mock_env.assert_called_once_with("QT_QPA_PLATFORM", "windows:fontengine=directwrite")
        mock_logger.remove.assert_called_once()

    def test_preview_update_flag(self, tmp_path: Path):
        fake_conf = self._make_conf()
        logs = tmp_path / "logs"
        logs.mkdir()

        sys.argv = ["remaku", "--preview-update"]

        with patch.object(main_mod, "sys") as mock_sys:
            mock_sys.argv = sys.argv
            mock_sys.exit = _exit_raiser
            mock_sys.stderr = sys.stderr

            with (
                patch.object(main_mod, "QApplication") as mock_qapp,
                patch.object(main_mod, "MainWindow") as mock_mw,
                patch.object(main_mod, "logger"),
                patch.object(main_mod, "QIcon"),
                patch.object(main_mod, "QFont"),
                patch.object(main_mod, "Theme"),
                patch.object(main_mod, "setTheme"),
                patch.object(main_mod, "i18n"),
                patch.object(main_mod.cfg, "load", return_value=fake_conf),
                patch.object(main_mod.cfg, "logs_dir", return_value=logs),
                patch.object(main_mod.os.environ, "setdefault"),
            ):
                mock_app = MagicMock()
                mock_qapp.return_value = mock_app
                mock_window = MagicMock()
                mock_mw.return_value = mock_window

                with patch("updater.UpdateDialog") as mock_dlg_cls:
                    mock_dlg = MagicMock()
                    mock_dlg_cls.return_value = mock_dlg
                    self._run_main_and_catch_exit()

                mock_dlg_cls.assert_called_once()
                mock_dlg.show.assert_called_once()
                mock_dlg.enter_download_phase.assert_called_once()
                mock_dlg.download.cancel.assert_called_once()
                mock_dlg.progress.show.assert_called_once()
                mock_dlg.progress.setValue.assert_called_once_with(35)
                mock_dlg.status_lbl.setText.assert_called_once_with("6.7 MB / 20.0 MB")

    def test_logging_setup(self, tmp_path: Path):
        fake_conf = self._make_conf()
        logs = tmp_path / "logs"
        logs.mkdir()

        with patch.object(main_mod, "sys") as mock_sys:
            mock_sys.argv = sys.argv
            mock_sys.exit = _exit_raiser
            mock_sys.stderr = sys.stderr

            with (
                patch.object(main_mod, "QApplication") as mock_qapp,
                patch.object(main_mod, "MainWindow"),
                patch.object(main_mod, "logger") as mock_logger,
                patch.object(main_mod, "QIcon"),
                patch.object(main_mod, "QFont"),
                patch.object(main_mod, "Theme"),
                patch.object(main_mod, "setTheme"),
                patch.object(main_mod, "i18n"),
                patch.object(main_mod.cfg, "load", return_value=fake_conf),
                patch.object(main_mod.cfg, "logs_dir", return_value=logs),
                patch.object(main_mod.os.environ, "setdefault"),
            ):
                mock_app = MagicMock()
                mock_qapp.return_value = mock_app
                self._run_main_and_catch_exit()

        mock_logger.remove.assert_called_once()
        assert mock_logger.add.call_count >= 1
        mock_logger.info.assert_called_once()
        args = mock_logger.info.call_args[0]
        assert "Remaku" in args[0]

    def test_excepthook_calls_logger(self, tmp_path: Path):
        fake_conf = self._make_conf()
        logs = tmp_path / "logs"
        logs.mkdir()

        with patch.object(main_mod, "sys") as mock_sys:
            mock_sys.argv = sys.argv
            mock_sys.exit = _exit_raiser
            mock_sys.stderr = sys.stderr

            with (
                patch.object(main_mod, "QApplication") as mock_qapp,
                patch.object(main_mod, "MainWindow"),
                patch.object(main_mod, "logger") as mock_logger,
                patch.object(main_mod, "QIcon"),
                patch.object(main_mod, "QFont"),
                patch.object(main_mod, "Theme"),
                patch.object(main_mod, "setTheme"),
                patch.object(main_mod, "i18n"),
                patch.object(main_mod.cfg, "load", return_value=fake_conf),
                patch.object(main_mod.cfg, "logs_dir", return_value=logs),
                patch.object(main_mod.os.environ, "setdefault"),
            ):
                mock_app = MagicMock()
                mock_qapp.return_value = mock_app
                self._run_main_and_catch_exit()

                hook = mock_sys.excepthook
                assert callable(hook)
                fake_args = (TypeError, TypeError("fake"), None)
                hook(*fake_args)

        mock_logger.opt.assert_called_once()
        opt_logger = mock_logger.opt.return_value
        opt_logger.critical.assert_called_once_with("Uncaught exception")

    def test_theme_light(self, tmp_path: Path):
        fake_conf = self._make_conf()
        fake_conf.general.theme = "light"
        logs = tmp_path / "logs"
        logs.mkdir()

        with patch.object(main_mod, "sys") as mock_sys:
            mock_sys.argv = sys.argv
            mock_sys.exit = _exit_raiser
            mock_sys.stderr = sys.stderr

            with (
                patch.object(main_mod, "QApplication") as mock_qapp,
                patch.object(main_mod, "MainWindow"),
                patch.object(main_mod, "logger"),
                patch.object(main_mod, "QIcon"),
                patch.object(main_mod, "QFont"),
                patch.object(main_mod, "Theme") as mock_theme,
                patch.object(main_mod, "setTheme") as mock_set_theme,
                patch.object(main_mod, "i18n"),
                patch.object(main_mod.cfg, "load", return_value=fake_conf),
                patch.object(main_mod.cfg, "logs_dir", return_value=logs),
                patch.object(main_mod.os.environ, "setdefault"),
            ):
                mock_app = MagicMock()
                mock_qapp.return_value = mock_app
                self._run_main_and_catch_exit()

        mock_set_theme.assert_called_once_with(mock_theme.LIGHT)

    def test_theme_dark(self, tmp_path: Path):
        fake_conf = self._make_conf()
        fake_conf.general.theme = "dark"
        logs = tmp_path / "logs"
        logs.mkdir()

        with patch.object(main_mod, "sys") as mock_sys:
            mock_sys.argv = sys.argv
            mock_sys.exit = _exit_raiser
            mock_sys.stderr = sys.stderr

            with (
                patch.object(main_mod, "QApplication") as mock_qapp,
                patch.object(main_mod, "MainWindow"),
                patch.object(main_mod, "logger"),
                patch.object(main_mod, "QIcon"),
                patch.object(main_mod, "QFont"),
                patch.object(main_mod, "Theme") as mock_theme,
                patch.object(main_mod, "setTheme") as mock_set_theme,
                patch.object(main_mod, "i18n"),
                patch.object(main_mod.cfg, "load", return_value=fake_conf),
                patch.object(main_mod.cfg, "logs_dir", return_value=logs),
                patch.object(main_mod.os.environ, "setdefault"),
            ):
                mock_app = MagicMock()
                mock_qapp.return_value = mock_app
                self._run_main_and_catch_exit()

        mock_set_theme.assert_called_once_with(mock_theme.DARK)
