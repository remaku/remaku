"""Tests for the update checker module."""

import os
import ssl
from unittest.mock import MagicMock, patch
from urllib.error import URLError

import pytest

import updater
from updater import (
    CheckResult,
    Download,
    UpdateDialog,
    UpdateInfo,
    check_async,
    clear_skip,
    find_installer_url,
    installer_temp_path,
    launch_installer_and_quit,
    localized_body,
    open_releases_page,
    parse_version,
    remember_skip,
    ssl_context,
)


def make_release(
    tag: str,
    body: str = "",
    assets: list[dict] | None = None,
    html_url: str = "",
    draft: bool = False,
) -> dict:
    return {
        "tag_name": tag,
        "body": body,
        "assets": assets or [],
        "html_url": html_url,
        "draft": draft,
    }


def make_installer_asset(tag: str, url: str = "https://example.com/setup.exe") -> dict:
    return {"name": f"Remaku_Setup_{tag}.exe", "browser_download_url": url}


class TestParseVersion:
    def test_stable(self):
        assert parse_version("v0.3.0") == (0, 3, 0, 999999)

    def test_stable_no_v_prefix(self):
        assert parse_version("0.3.0") == (0, 3, 0, 999999)

    def test_beta(self):
        assert parse_version("v0.4.0-beta.1") == (0, 4, 0, 1)

    def test_beta_2(self):
        assert parse_version("v0.4.0-beta.2") == (0, 4, 0, 2)

    def test_rc(self):
        assert parse_version("v1.0.0-rc.1") == (1, 0, 0, 1)

    def test_beta_less_than_stable(self):
        beta = parse_version("v0.4.0-beta.1")
        stable = parse_version("v0.4.0")
        assert beta is not None
        assert stable is not None
        assert beta < stable

    def test_beta_1_less_than_beta_2(self):
        beta1 = parse_version("v0.4.0-beta.1")
        beta2 = parse_version("v0.4.0-beta.2")
        assert beta1 is not None
        assert beta2 is not None
        assert beta1 < beta2

    def test_empty_returns_none(self):
        assert parse_version("") is None

    def test_none_returns_none(self):
        assert parse_version(None) is None  # type: ignore[arg-type]

    def test_invalid_format(self):
        assert parse_version("not-a-version") is None

    def test_major_only(self):
        assert parse_version("v1") is None


class TestLocalizedBody:
    def test_no_lang_tags_returns_raw(self):
        body = "Some plain text"
        assert localized_body(body) == "Some plain text"

    def test_extracts_current_locale(self, monkeypatch):
        monkeypatch.setattr(updater.i18n, "current_locale", "zh_tw")
        body = "<!-- lang:en -->\nHello\n<!-- lang:zh_tw -->\n你好"
        assert localized_body(body) == "你好"

    def test_falls_back_to_en(self, monkeypatch):
        monkeypatch.setattr(updater.i18n, "current_locale", "ja")
        body = "<!-- lang:en -->\nHello\n<!-- lang:zh_tw -->\n你好"
        assert localized_body(body) == "Hello"

    def test_falls_back_to_raw_when_no_en(self, monkeypatch):
        monkeypatch.setattr(updater.i18n, "current_locale", "ja")
        body = "<!-- lang:zh_tw -->\n你好"
        assert localized_body(body) == "<!-- lang:zh_tw -->\n你好"


class TestFindInstallerUrl:
    def test_finds_matching_asset(self):
        assets = [make_installer_asset("v0.3.0")]
        assert find_installer_url(assets) == "https://example.com/setup.exe"

    def test_empty_assets(self):
        assert find_installer_url([]) == ""

    def test_ignores_non_matching(self):
        assets = [{"name": "source.zip", "browser_download_url": "https://example.com/zip"}]
        assert find_installer_url(assets) == ""

    def test_picks_first_match(self):
        assets = [
            make_installer_asset("v0.3.0", "https://first.exe"),
            make_installer_asset("v0.3.0", "https://second.exe"),
        ]
        assert find_installer_url(assets) == "https://first.exe"


class TestInstallerTempPath:
    def test_contains_tag(self):
        path = installer_temp_path("v0.3.0")
        assert "v0.3.0" in path
        assert path.endswith(".exe")

    def test_sanitizes_special_chars(self):
        path = installer_temp_path("v0.4.0-beta.1")
        assert "beta" in path

    def test_empty_tag(self):
        path = installer_temp_path("")
        assert "latest" in path


class TestCompareRelease:
    def test_newer_stable(self):
        data = make_release("v99.0.0", body="notes", assets=[make_installer_asset("v99.0.0")])
        result = updater._compare_release(data, (0, 3, 0, 999999))
        assert result.status == "available"
        assert result.info is not None
        assert result.info.tag == "v99.0.0"
        assert result.info.body == "notes"
        assert result.info.installer_url == "https://example.com/setup.exe"

    def test_same_version(self):
        data = make_release("v0.3.0")
        result = updater._compare_release(data, (0, 3, 0, 999999))
        assert result.status == "up_to_date"

    def test_older_version(self):
        data = make_release("v0.1.0")
        result = updater._compare_release(data, (0, 3, 0, 999999))
        assert result.status == "up_to_date"

    def test_unparseable_tag(self):
        data = make_release("not-a-version")
        result = updater._compare_release(data, (0, 3, 0, 999999))
        assert result.status == "error"
        assert "Cannot parse" in result.error

    def test_uses_html_url(self):
        data = make_release("v99.0.0", html_url="https://github.com/releases/tag/v99.0.0")
        result = updater._compare_release(data, (0, 3, 0, 999999))
        assert result.info is not None
        assert result.info.release_url == "https://github.com/releases/tag/v99.0.0"

    def test_fallback_release_url(self):
        data = make_release("v99.0.0")
        result = updater._compare_release(data, (0, 3, 0, 999999))
        assert result.info is not None
        assert "v99.0.0" in result.info.release_url


class TestCheckStable:
    @patch("updater._fetch_json")
    def test_new_version_available(self, mock_fetch):
        mock_fetch.return_value = make_release("v99.0.0", assets=[make_installer_asset("v99.0.0")])
        result = updater._check_stable((0, 3, 0, 999999))
        assert result.status == "available"
        mock_fetch.assert_called_once()

    @patch("updater._fetch_json")
    def test_up_to_date(self, mock_fetch):
        mock_fetch.return_value = make_release("v0.3.0")
        result = updater._check_stable((0, 3, 0, 999999))
        assert result.status == "up_to_date"


class TestCheckBeta:
    @patch("updater._fetch_json")
    def test_picks_highest_version(self, mock_fetch):
        mock_fetch.return_value = [
            make_release("v0.3.0"),
            make_release("v0.4.0-beta.1"),
            make_release("v0.4.0-beta.2"),
        ]
        result = updater._check_beta((0, 3, 0, 999999))
        assert result.status == "available"
        assert result.info is not None
        assert result.info.tag == "v0.4.0-beta.2"

    @patch("updater._fetch_json")
    def test_skips_drafts(self, mock_fetch):
        mock_fetch.return_value = [
            make_release("v99.0.0", draft=True),
            make_release("v0.4.0-beta.1"),
        ]
        result = updater._check_beta((0, 3, 0, 999999))
        assert result.status == "available"
        assert result.info is not None
        assert result.info.tag == "v0.4.0-beta.1"

    @patch("updater._fetch_json")
    def test_empty_list(self, mock_fetch):
        mock_fetch.return_value = []
        result = updater._check_beta((0, 3, 0, 999999))
        assert result.status == "error"
        assert "No releases" in result.error

    @patch("updater._fetch_json")
    def test_all_unparseable(self, mock_fetch):
        mock_fetch.return_value = [make_release("not-a-version")]
        result = updater._check_beta((0, 3, 0, 999999))
        assert result.status == "error"
        assert "No valid" in result.error

    @patch("updater._fetch_json")
    def test_up_to_date(self, mock_fetch):
        mock_fetch.return_value = [make_release("v0.3.0")]
        result = updater._check_beta((0, 3, 0, 999999))
        assert result.status == "up_to_date"


class TestCheck:
    @patch("updater._fetch_json")
    @patch("updater.cfg")
    def test_stable_channel(self, mock_cfg, mock_fetch):
        mock_cfg.load.return_value.general.update_channel = "stable"
        mock_fetch.return_value = make_release("v99.0.0")
        result = updater.check()
        assert result.status == "available"

    @patch("updater._fetch_json")
    @patch("updater.cfg")
    def test_beta_channel(self, mock_cfg, mock_fetch):
        mock_cfg.load.return_value.general.update_channel = "beta"
        mock_fetch.return_value = [make_release("v99.0.0-beta.1")]
        result = updater.check()
        assert result.status == "available"

    @patch("updater._fetch_json")
    @patch("updater.cfg")
    def test_network_error(self, mock_cfg, mock_fetch):
        mock_cfg.load.return_value.general.update_channel = "stable"
        mock_fetch.side_effect = OSError("connection refused")
        result = updater.check()
        assert result.status == "error"
        assert "Connection failed" in result.error

    @patch("updater._fetch_json")
    @patch("updater.cfg")
    def test_malformed_response(self, mock_cfg, mock_fetch):
        mock_cfg.load.return_value.general.update_channel = "stable"
        mock_fetch.side_effect = ValueError("bad json")
        result = updater.check()
        assert result.status == "error"
        assert "Response format error" in result.error

    @patch("updater._fetch_json")
    @patch("updater.cfg")
    def test_ssl_error(self, mock_cfg, mock_fetch):
        mock_cfg.load.return_value.general.update_channel = "stable"
        mock_fetch.side_effect = OSError("[SSL: CERTIFICATE_VERIFY_FAILED]")
        result = updater.check()
        assert result.status == "error"
        assert "Connection failed" in result.error

    @patch("updater.cfg")
    def test_unparseable_current_version(self, mock_cfg):
        mock_cfg.load.return_value.general.update_channel = "stable"
        with patch("updater.__version__", "not-a-version"):
            result = updater.check()
        assert result.status == "error"
        assert "Cannot parse current version" in result.error


# ---------------------------------------------------------------------------
# ssl_context
# ---------------------------------------------------------------------------


class TestSslContext:
    def test_returns_ssl_context(self):
        ctx = ssl_context()
        assert isinstance(ctx, ssl.SSLContext)

    def test_uses_certifi(self):
        with (
            patch("updater.certifi.where", return_value="/fake/certs.pem"),
            patch("ssl.create_default_context") as mock_create,
        ):
            ssl_context()
        mock_create.assert_called_once_with(cafile="/fake/certs.pem")


# ---------------------------------------------------------------------------
# _fetch_json
# ---------------------------------------------------------------------------


class TestFetchJson:
    @patch("updater.urlopen")
    def test_makes_request_with_headers(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"tag_name":"v1.0.0"}'
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        result = updater._fetch_json("https://api.github.com/repos/test/releases/latest")

        assert result == {"tag_name": "v1.0.0"}
        call_args = mock_urlopen.call_args
        req = call_args[0][0]
        assert req.headers == {"Accept": "application/vnd.github.v3+json"}

    @patch("updater.urlopen")
    def test_passes_timeout_and_context(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"[]"
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        with patch("updater.ssl_context") as mock_ssl:
            mock_ctx = MagicMock()
            mock_ssl.return_value = mock_ctx
            updater._fetch_json("https://example.com")

        assert mock_urlopen.call_args.kwargs["timeout"] == updater.CHECK_TIMEOUT_S
        assert mock_urlopen.call_args.kwargs["context"] is mock_ctx


# ---------------------------------------------------------------------------
# check_async
# ---------------------------------------------------------------------------


class TestCheckAsync:
    def test_calls_callback_on_main_thread(self, qtbot):
        from PySide6.QtCore import QObject

        result = CheckResult(status="up_to_date")
        parent = QObject()

        with patch("updater.check", return_value=result):
            callback = MagicMock()
            check_async(parent, callback)
            qtbot.waitUntil(lambda: callback.called, timeout=10000)

        callback.assert_called_once_with(result)


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------


class TestDownload:
    def test_start_creates_daemon_thread(self):
        dl = Download(None, "http://example.com", "/tmp/setup.exe", MagicMock(), MagicMock(), MagicMock())
        with patch("threading.Thread") as mock_thread:
            instance = MagicMock()
            mock_thread.return_value = instance
            dl.start()
        mock_thread.assert_called_once_with(target=dl.run, name="updater-download", daemon=True)
        instance.start.assert_called_once()

    def test_cancel_sets_event(self):
        dl = Download(None, "http://example.com", "/tmp/setup.exe", MagicMock(), MagicMock(), MagicMock())
        assert not dl.cancel_evt.is_set()
        dl.cancel()
        assert dl.cancel_evt.is_set()

    def test_post_emits_via_poster(self):
        dl = Download(None, "http://example.com", "/tmp/setup.exe", MagicMock(), MagicMock(), MagicMock())
        fn = MagicMock()
        with patch.object(dl.poster, "posted") as mock_posted:
            dl.post(fn)
        mock_posted.emit.assert_called_once_with(fn)

    def test_post_suppresses_exception(self):
        dl = Download(None, "http://example.com", "/tmp/setup.exe", MagicMock(), MagicMock(), MagicMock())
        with patch.object(dl.poster, "posted", side_effect=RuntimeError("boom")):
            dl.post(lambda: None)

    def test_run_success(self, tmp_path):
        dest = str(tmp_path / "setup.exe")
        on_progress = MagicMock()
        on_done = MagicMock()
        on_error = MagicMock()
        dl = Download(None, "http://example.com/setup.exe", dest, on_progress, on_done, on_error)

        mock_resp = MagicMock()
        mock_resp.headers.get.return_value = "10"
        mock_resp.read.side_effect = [b"12345", b"67890", b""]
        mock_resp.__enter__.return_value = mock_resp

        with patch("updater.urlopen", return_value=mock_resp):
            dl.run()

        assert os.path.exists(dest)
        on_done.assert_called_once_with(dest)
        assert on_progress.call_count == 2
        on_error.assert_not_called()

    def test_run_no_content_length(self, tmp_path):
        dest = str(tmp_path / "setup.exe")
        on_progress = MagicMock()
        on_done = MagicMock()
        dl = Download(None, "http://example.com/setup.exe", dest, on_progress, on_done, MagicMock())

        mock_resp = MagicMock()
        mock_resp.headers.get.return_value = None
        mock_resp.read.side_effect = [b"12345", b""]
        mock_resp.__enter__.return_value = mock_resp

        with patch("updater.urlopen", return_value=mock_resp):
            dl.run()

        on_done.assert_called_once_with(dest)
        calls = on_progress.call_args_list
        assert calls[-1].args[1] == 0

    def test_run_cancelled_midway(self, tmp_path):
        dest = str(tmp_path / "setup.exe")
        on_done = MagicMock()
        on_error = MagicMock()
        dl = Download(None, "http://example.com/setup.exe", dest, MagicMock(), on_done, on_error)

        mock_resp = MagicMock()
        mock_resp.headers.get.return_value = "100"
        mock_resp.read.side_effect = [b"12345", b"67890"]
        mock_resp.__enter__.return_value = mock_resp

        def cancel_after_first():
            dl.cancel()
            return b"12345"

        mock_resp.read.side_effect = [cancel_after_first(), b"67890"]

        with patch("updater.urlopen", return_value=mock_resp):
            dl.run()

        assert not os.path.exists(dest)
        assert not os.path.exists(dest + ".part")
        on_done.assert_not_called()
        on_error.assert_not_called()

    def test_run_error(self, tmp_path):
        dest = str(tmp_path / "setup.exe")
        on_error = MagicMock()
        dl = Download(None, "http://example.com/setup.exe", dest, MagicMock(), MagicMock(), on_error)

        with patch("updater.urlopen", side_effect=URLError("network fail")):
            dl.run()

        on_error.assert_called_once()
        assert not os.path.exists(dest)
        assert not os.path.exists(dest + ".part")

    def test_run_cleans_stale_part_on_error(self, tmp_path):
        dest = str(tmp_path / "setup.exe")
        part = dest + ".part"
        with open(part, "wb") as f:
            f.write(b"stale data")

        on_error = MagicMock()
        dl = Download(None, "http://example.com/setup.exe", dest, MagicMock(), MagicMock(), on_error)

        with patch("updater.urlopen", side_effect=URLError("fail")):
            dl.run()

        assert not os.path.exists(part)

    def test_run_cleans_stale_part_remove_fails(self, tmp_path):
        dest = str(tmp_path / "setup.exe")
        part = dest + ".part"
        with open(part, "wb") as f:
            f.write(b"stale data")

        on_error = MagicMock()
        dl = Download(None, "http://example.com/setup.exe", dest, MagicMock(), MagicMock(), on_error)

        with (
            patch("updater.urlopen", side_effect=URLError("fail")),
            patch("updater.os.remove", side_effect=OSError("locked")),
        ):
            dl.run()

        on_error.assert_called_once()
        assert os.path.exists(part)


# ---------------------------------------------------------------------------
# installer_temp_path
# ---------------------------------------------------------------------------


class TestInstallerTempPathEdge:
    def test_replaces_special_chars(self):
        path = installer_temp_path("v1.0.0/beta")
        assert "/" not in path
        assert "_" in path

    def test_replaces_colons(self):
        path = installer_temp_path("v1.0.0:beta")
        filename = os.path.basename(path)
        assert ":" not in filename

    def test_replaces_spaces(self):
        path = installer_temp_path("v1.0.0 beta")
        assert " " not in path


# ---------------------------------------------------------------------------
# launch_installer_and_quit
# ---------------------------------------------------------------------------


class TestLaunchInstallerAndQuit:
    def test_subprocess_args(self):
        with patch("updater.subprocess.Popen") as mock_popen, patch("updater.QTimer.singleShot"):
            launch_installer_and_quit("C:\\Temp\\setup.exe")

        mock_popen.assert_called_once()
        args = mock_popen.call_args[0][0]
        assert args[0] == "C:\\Temp\\setup.exe"
        assert "/VERYSILENT" in args
        assert "/SUPPRESSMSGBOXES" in args
        assert mock_popen.call_args.kwargs["close_fds"] is True
        assert "creationflags" in mock_popen.call_args.kwargs

    def test_oserror_raises(self):
        with (
            patch("updater.subprocess.Popen", side_effect=OSError("permission denied")),
            pytest.raises(OSError, match="permission denied"),
        ):
            launch_installer_and_quit("C:\\Temp\\setup.exe")

    def test_quit_timer_scheduled(self):
        with patch("updater.subprocess.Popen"), patch("updater.QTimer.singleShot") as mock_timer:
            launch_installer_and_quit("C:\\Temp\\setup.exe")
        mock_timer.assert_called_once_with(200, updater.QApplication.quit)


# ---------------------------------------------------------------------------
# remember_skip / clear_skip
# ---------------------------------------------------------------------------


class TestRememberSkip:
    def test_writes_skipped_version(self):
        mock_conf = MagicMock()
        with patch("updater.cfg.load", return_value=mock_conf), patch("updater.cfg.save") as mock_save:
            remember_skip("v1.0.0")

        assert mock_conf.general.skipped_version == "v1.0.0"
        mock_save.assert_called_once_with(mock_conf)


class TestClearSkip:
    def test_clears_skipped_version(self):
        mock_conf = MagicMock()
        mock_conf.general.skipped_version = "v1.0.0"
        with patch("updater.cfg.load", return_value=mock_conf), patch("updater.cfg.save") as mock_save:
            clear_skip()

        assert mock_conf.general.skipped_version == ""
        mock_save.assert_called_once_with(mock_conf)


# ---------------------------------------------------------------------------
# open_releases_page
# ---------------------------------------------------------------------------


class TestOpenReleasesPage:
    def test_calls_webbrowser(self):
        with patch("updater.webbrowser.open") as mock_open:
            open_releases_page("https://example.com/releases")
        mock_open.assert_called_once_with("https://example.com/releases")

    def test_uses_default_url(self):
        with patch("updater.webbrowser.open") as mock_open:
            open_releases_page()
        mock_open.assert_called_once_with(updater.RELEASES_URL)


# ---------------------------------------------------------------------------
# UpdateDialog
# ---------------------------------------------------------------------------


class TestUpdateDialog:
    @pytest.fixture
    def dialog(self, qtbot):
        info = UpdateInfo(
            tag="v1.0.0",
            version=(1, 0, 0, 999999),
            body="notes",
            installer_url="https://example.com/setup.exe",
            release_url="https://example.com/releases",
        )
        dlg = UpdateDialog(None, info)
        qtbot.addWidget(dlg)
        return dlg

    def test_on_skip(self, dialog):
        with patch("updater.remember_skip") as mock_remember:
            dialog.show()
            dialog.on_skip()
            mock_remember.assert_called_once_with("v1.0.0")
        assert not dialog.isVisible()

    def test_on_skip_failure_ignored(self, dialog):
        with patch("updater.remember_skip", side_effect=OSError("disk full")):
            dialog.show()
            dialog.on_skip()
        assert not dialog.isVisible()

    def test_on_later(self, dialog):
        dialog.show()
        dialog.on_later()
        assert not dialog.isVisible()

    def test_on_install_no_url(self, dialog):
        dialog.info.installer_url = ""
        with patch("updater.open_releases_page") as mock_open:
            dialog.show()
            dialog.on_install()
            mock_open.assert_called_once_with("https://example.com/releases")
        assert not dialog.isVisible()

    def test_on_install_with_url(self, dialog):
        with patch.object(dialog, "enter_download_phase") as mock_enter:
            dialog.on_install()
        mock_enter.assert_called_once()

    def test_on_progress_with_total(self, dialog):
        dialog.on_progress(50, 100)
        assert dialog.progress.value() == 50
        assert "0.0" in dialog.status_lbl.text()

    def test_on_progress_no_total(self, dialog):
        dialog.on_progress(50, 0)
        assert dialog.status_lbl.text() != ""

    def test_on_download_done(self, dialog, qtbot):
        with patch.object(dialog, "start_install") as mock_start:
            dialog.on_download_done("/tmp/setup.exe")
            qtbot.wait(500)
            mock_start.assert_called_once_with("/tmp/setup.exe")
        assert dialog.progress.value() == 100

    def test_start_install_success(self, dialog):
        with patch("updater.launch_installer_and_quit") as mock_launch:
            dialog.start_install("/tmp/setup.exe")
        mock_launch.assert_called_once_with("/tmp/setup.exe")

    def test_start_install_failure(self, dialog):
        with patch("updater.launch_installer_and_quit", side_effect=OSError("fail")):
            dialog.start_install("/tmp/setup.exe")
        assert dialog.phase == dialog.PHASE_ERROR
        assert "fail" in dialog.status_lbl.text()

    def test_on_download_error(self, dialog):
        dialog.on_download_error("network error")
        assert dialog.phase == dialog.PHASE_ERROR
        assert "network error" in dialog.status_lbl.text()

    def test_show_error(self, dialog):
        from i18n import t

        dialog.show_error("error msg")
        assert dialog.phase == dialog.PHASE_ERROR
        assert not dialog.progress.isVisible()
        assert dialog.status_lbl.text() == "error msg"
        assert dialog.btn_later.text() == t("action.close")
        assert dialog.btn_install.text() == t("updater.open_download_page")

    def test_fallback_browser(self, dialog):
        with patch("updater.open_releases_page") as mock_open:
            dialog.show()
            dialog.fallback_browser()
            mock_open.assert_called_once_with("https://example.com/releases")
        assert not dialog.isVisible()

    def test_close_event_cancels_download(self, dialog):
        dialog.phase = dialog.PHASE_DOWNLOAD
        dialog.download = MagicMock()
        dialog.close()
        dialog.download.cancel.assert_called_once()

    def test_close_event_no_download(self, dialog):
        dialog.phase = dialog.PHASE_DOWNLOAD
        dialog.download = None
        dialog.show()
        dialog.close()
        assert not dialog.isVisible()

    def test_on_cancel_download(self, dialog):
        dialog.download = MagicMock()
        dialog.show()
        dialog.on_cancel_download()
        dialog.download.cancel.assert_called_once()
        assert not dialog.isVisible()

    def test_enter_download_phase(self, dialog):
        dialog.show()
        with patch("updater.Download") as mock_dl_cls:
            instance = MagicMock()
            mock_dl_cls.return_value = instance
            dialog.enter_download_phase()
        assert dialog.phase == dialog.PHASE_DOWNLOAD
        assert not dialog.btn_skip.isEnabled()
        assert not dialog.btn_later.isEnabled()
        assert dialog.progress.isVisible()
        assert dialog.progress.value() == 0
        mock_dl_cls.assert_called_once()
        instance.start.assert_called_once()

    def test_enter_download_phase_clears_stale_part(self, dialog):
        dialog.show()
        with patch("updater.Download") as mock_dl_cls:
            mock_dl_cls.return_value = MagicMock()
            dialog.enter_download_phase()
        assert dialog.phase == dialog.PHASE_DOWNLOAD

    def test_enter_download_phase_stale_part_remove_fails(self, dialog):
        import os

        part = installer_temp_path(dialog.info.tag) + ".part"
        with open(part, "wb") as f:
            f.write(b"stale")
        try:
            dialog.show()
            with patch("updater.os.remove", side_effect=OSError("locked")), patch("updater.Download") as mock_dl_cls:
                mock_dl_cls.return_value = MagicMock()
                dialog.enter_download_phase()
            assert dialog.phase == dialog.PHASE_DOWNLOAD
        finally:
            if os.path.exists(part):
                os.remove(part)

    def test_beta_channel_label(self, qtbot):
        info = UpdateInfo(tag="v0.4.0-beta.1", version=(0, 4, 0, 1), body="", installer_url="", release_url="")
        with patch("updater.cfg.load") as mock_load:
            conf = MagicMock()
            conf.general.update_channel = "beta"
            mock_load.return_value = conf
            dialog = UpdateDialog(None, info)
            qtbot.addWidget(dialog)
        assert dialog.channel == "beta"


class TestPromptUpdate:
    def test_returns_dialog(self, qtbot):
        info = UpdateInfo(tag="v1.0.0", version=(1, 0, 0, 999999), body="", installer_url="", release_url="")
        with patch("updater.cfg.load") as mock_load:
            conf = MagicMock()
            conf.general.update_channel = "stable"
            mock_load.return_value = conf
            dlg = updater.prompt_update(None, info)
            qtbot.addWidget(dlg)
        assert isinstance(dlg, UpdateDialog)
        assert dlg.isVisible()
        dlg.close()
