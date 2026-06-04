"""Tests for the update checker module."""

from unittest.mock import patch

import updater
from updater import (
    find_installer_url,
    installer_temp_path,
    localized_body,
    parse_version,
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
