"""Tests for the application entry point."""

# pyright: reportArgumentType=false, reportAttributeAccessIssue=false

import contextlib
import runpy
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

    def test_name_main_guard(self, tmp_path: Path):
        fake_conf = self._make_conf()
        logs = tmp_path / "logs"
        logs.mkdir()

        mock_qtwidgets = MagicMock()
        mock_qtwidgets.QApplication = MagicMock()
        mock_qtgui = MagicMock()
        mock_qtgui.QIcon = MagicMock()
        mock_qtgui.QFont = MagicMock()
        mock_qtcore = MagicMock()
        mock_qtcore.Qt = MagicMock()
        mock_qfluent = MagicMock()
        mock_qfluent.setTheme = MagicMock()
        mock_theme = MagicMock()
        mock_theme.LIGHT = 0
        mock_theme.DARK = 1
        mock_theme.AUTO = 2
        mock_qfluent.Theme = mock_theme
        mock_loguru = MagicMock()
        mock_config = MagicMock()
        mock_config.load.return_value = fake_conf
        mock_config.logs_dir.return_value = logs
        mock_i18n_mod = MagicMock()
        mock_main_window_mod = MagicMock()
        mock_main_window_mod.MainWindow = MagicMock()
        mock_version_mod = MagicMock()
        mock_version_mod.__version__ = "99.0.0"
        mock_version_mod.root = Path("/fake")

        module_names = [
            "PySide6.QtWidgets",
            "PySide6.QtGui",
            "PySide6.QtCore",
            "qfluentwidgets",
            "loguru",
            "config",
            "i18n",
            "main_window",
            "version",
        ]
        mocks = {
            "PySide6.QtWidgets": mock_qtwidgets,
            "PySide6.QtGui": mock_qtgui,
            "PySide6.QtCore": mock_qtcore,
            "qfluentwidgets": mock_qfluent,
            "loguru": mock_loguru,
            "config": mock_config,
            "i18n": mock_i18n_mod,
            "main_window": mock_main_window_mod,
            "version": mock_version_mod,
        }

        saved = {name: sys.modules.get(name) for name in module_names}

        for name in module_names:
            sys.modules[name] = mocks[name]

        try:
            with patch.object(sys, "exit", _exit_raiser), contextlib.suppress(SystemExit):
                runpy.run_path(str(Path(main_mod.__file__).resolve()), run_name="__main__")

            mock_qtwidgets.QApplication.assert_called_once()
            mock_main_window_mod.MainWindow.assert_called_once()
            mock_config.load.assert_called_once()
            mock_config.logs_dir.assert_called_once()
            mock_i18n_mod.load.assert_called_once()
            mock_loguru.logger.remove.assert_called_once()
        finally:
            for name in module_names:
                if name in saved and saved[name] is not None:
                    sys.modules[name] = saved[name]
                elif name in sys.modules and name not in saved:
                    del sys.modules[name]
