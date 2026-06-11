from pathlib import Path
from urllib.error import URLError

from remaku.services import updater
from remaku.services.updater import CheckResult, UpdateInfo


def make_release(tag: str, *, draft: bool = False, assets: list[dict] | None = None) -> dict:
    return {
        "tag_name": tag,
        "draft": draft,
        "body": "Release notes",
        "html_url": f"https://example.invalid/{tag}",
        "assets": assets if assets is not None else [make_installer_asset(tag)],
    }


def make_installer_asset(tag: str) -> dict:
    return {
        "name": f"Remaku_Setup_{tag}.exe",
        "browser_download_url": f"https://example.invalid/{tag}.exe",
    }


def test_parse_version_handles_stable_and_prerelease_tags() -> None:
    assert updater.parse_version("v1.2.3") == (1, 2, 3, 999999)
    assert updater.parse_version("1.2.3-beta.4") == (1, 2, 3, 4)
    assert updater.parse_version("bad") is None


def test_find_installer_url_returns_matching_exe() -> None:
    assets = [
        {"name": "notes.txt", "browser_download_url": "https://example.invalid/notes"},
        make_installer_asset("v2.0.0"),
    ]

    assert updater.find_installer_url(assets) == "https://example.invalid/v2.0.0.exe"


def test_compare_release_reports_available_release() -> None:
    result = updater.compare_release(make_release("v2.0.0"), current=(1, 0, 0, 999999))

    assert result.status == "available"
    assert result.info is not None
    assert result.info.tag == "v2.0.0"
    assert result.info.installer_url.endswith(".exe")


def test_compare_release_reports_up_to_date() -> None:
    result = updater.compare_release(make_release("v1.0.0"), current=(1, 0, 0, 999999))

    assert result == CheckResult(status="up_to_date")


def test_check_beta_selects_newest_non_draft_release(monkeypatch) -> None:
    monkeypatch.setattr(
        updater,
        "fetch_json",
        lambda url: [make_release("v1.2.0", draft=True), make_release("v1.1.0"), make_release("v1.3.0-beta.1")],
    )

    result = updater.check_beta(current=(1, 0, 0, 999999))

    assert result.status == "available"
    assert result.info is not None
    assert result.info.tag == "v1.3.0-beta.1"


def test_check_converts_network_error_to_error_result(monkeypatch) -> None:
    class FakeGeneral:
        update_channel = "stable"

    class FakeConfig:
        general = FakeGeneral()

    class FakeConfigModel:
        config = FakeConfig()

    def raise_url_error(current):
        raise URLError("offline")

    monkeypatch.setattr(updater, "config_model", FakeConfigModel())
    monkeypatch.setattr(updater, "parse_version", lambda tag: (1, 0, 0, 999999))
    monkeypatch.setattr(updater, "check_stable", raise_url_error)

    result = updater.check()

    assert result.status == "error"
    assert "Connection failed" in result.error


def test_remember_skip_persists_config(monkeypatch) -> None:
    calls = []

    class FakeGeneral:
        skipped_version = ""

    class FakeConfig:
        general = FakeGeneral()

    class FakeConfigModel:
        config = FakeConfig()

        def save(self) -> None:
            calls.append("save")

    fake_config_model = FakeConfigModel()
    monkeypatch.setattr(updater, "config_model", fake_config_model)

    updater.remember_skip("v2.0.0")

    assert fake_config_model.config.general.skipped_version == "v2.0.0"
    assert calls == ["save"]


def test_launch_installer_and_quit_uses_silent_flags(monkeypatch) -> None:
    popen_calls = []
    timer_calls = []

    monkeypatch.setattr(updater.subprocess, "DETACHED_PROCESS", 1, raising=False)
    monkeypatch.setattr(updater.subprocess, "CREATE_NEW_PROCESS_GROUP", 2, raising=False)
    monkeypatch.setattr(updater.subprocess, "Popen", lambda *args, **kwargs: popen_calls.append((args, kwargs)))
    monkeypatch.setattr(updater.QTimer, "singleShot", lambda delay, callback: timer_calls.append((delay, callback)))

    updater.launch_installer_and_quit("installer.exe")

    assert popen_calls[0][0][0] == ["installer.exe", "/VERYSILENT", "/SUPPRESSMSGBOXES"]
    assert popen_calls[0][1]["creationflags"] == 3
    assert timer_calls[0][0] == 200


def test_open_releases_page_uses_browser(monkeypatch) -> None:
    opened = []
    monkeypatch.setattr(updater.webbrowser, "open", opened.append)

    updater.open_releases_page("https://example.invalid/releases")

    assert opened == ["https://example.invalid/releases"]


class FakeDownloadResponse:
    def __init__(self, chunks: list[bytes], content_length: int = 0) -> None:
        self.chunks = chunks
        self.headers = {"Content-Length": str(content_length)}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        return None

    def read(self, chunk_size: int) -> bytes:
        if not self.chunks:
            return b""

        return self.chunks.pop(0)


class FakePoster:
    def __init__(self, parent) -> None:
        self.parent = parent

    def post(self, callback) -> None:
        callback()


def make_download(tmp_path: Path, *, url: str = "https://example.invalid/file.exe") -> tuple[updater.Download, list]:
    events = []
    download = updater.Download(
        parent=None,
        url=url,
        destination=str(tmp_path / "installer.exe"),
        on_progress=lambda downloaded, total: events.append(("progress", downloaded, total)),
        on_done=lambda path: events.append(("done", path)),
        on_error=lambda error: events.append(("error", error)),
    )
    download.post = lambda callback: callback()
    return download, events


def test_update_info_is_plain_data() -> None:
    info = UpdateInfo("v2.0.0", (2, 0, 0, 999999), "body", "installer", "release")

    assert info.tag == "v2.0.0"


def test_download_run_writes_file_and_posts_progress(tmp_path, monkeypatch) -> None:
    download, events = make_download(tmp_path)
    monkeypatch.setattr(updater, "ssl_context", lambda: None)
    monkeypatch.setattr(
        updater,
        "urlopen",
        lambda request, timeout, context: FakeDownloadResponse([b"abc", b"def"], content_length=6),
    )

    download.run()

    destination = tmp_path / "installer.exe"
    assert destination.read_bytes() == b"abcdef"
    assert events == [
        ("progress", 3, 6),
        ("progress", 6, 6),
        ("done", str(destination)),
    ]
    assert not (tmp_path / "installer.exe.part").exists()


def test_download_run_removes_partial_file_on_error(tmp_path, monkeypatch) -> None:
    download, events = make_download(tmp_path)
    monkeypatch.setattr(updater, "ssl_context", lambda: None)

    def raise_urlopen(request, timeout, context):
        raise OSError("network down")

    monkeypatch.setattr(updater, "urlopen", raise_urlopen)
    (tmp_path / "installer.exe.part").write_bytes(b"partial")

    download.run()

    assert not (tmp_path / "installer.exe.part").exists()
    assert events == [("error", "network down")]


def test_download_cancel_suppresses_error_callback(tmp_path, monkeypatch) -> None:
    download, events = make_download(tmp_path)
    download.cancel()
    monkeypatch.setattr(updater, "ssl_context", lambda: None)
    monkeypatch.setattr(
        updater,
        "urlopen",
        lambda request, timeout, context: FakeDownloadResponse([b"abc"], content_length=3),
    )

    download.run()

    assert events == []
    assert not (tmp_path / "installer.exe.part").exists()
