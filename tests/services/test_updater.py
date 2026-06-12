import json
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


def test_find_installer_url_returns_empty_when_no_installer_asset() -> None:
    assert updater.find_installer_url([{"name": "Remaku_Setup_v2.0.0.zip"}]) == ""


def test_compare_release_reports_available_release() -> None:
    result = updater.compare_release(make_release("v2.0.0"), current=(1, 0, 0, 999999))

    assert result.status == "available"
    assert result.info is not None
    assert result.info.tag == "v2.0.0"
    assert result.info.installer_url.endswith(".exe")


def test_compare_release_reports_up_to_date() -> None:
    result = updater.compare_release(make_release("v1.0.0"), current=(1, 0, 0, 999999))

    assert result == CheckResult(status="up_to_date")


def test_compare_release_reports_parse_error() -> None:
    result = updater.compare_release(make_release("not-a-version"), current=(1, 0, 0, 999999))

    assert result.status == "error"
    assert result.error == "Cannot parse version: 'not-a-version'"


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


def test_check_beta_reports_error_for_empty_response(monkeypatch) -> None:
    monkeypatch.setattr(updater, "fetch_json", lambda url: [])

    result = updater.check_beta(current=(1, 0, 0, 999999))

    assert result == CheckResult(status="error", error="No releases found")


def test_check_beta_reports_error_when_no_valid_releases(monkeypatch) -> None:
    monkeypatch.setattr(
        updater,
        "fetch_json",
        lambda url: [make_release("bad"), make_release("v2.0.0", draft=True)],
    )

    result = updater.check_beta(current=(1, 0, 0, 999999))

    assert result == CheckResult(status="error", error="No valid releases found")


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


def test_check_reports_error_when_current_version_is_invalid(monkeypatch) -> None:
    monkeypatch.setattr(updater, "__version__", "bad")

    result = updater.check()

    assert result == CheckResult(status="error", error="Cannot parse current version: bad")


def test_check_converts_response_errors_to_error_result(monkeypatch) -> None:
    class FakeGeneral:
        update_channel = "stable"

    class FakeConfig:
        general = FakeGeneral()

    class FakeConfigModel:
        config = FakeConfig()

    def raise_value_error(current):
        raise ValueError("bad json")

    monkeypatch.setattr(updater, "config_model", FakeConfigModel())
    monkeypatch.setattr(updater, "parse_version", lambda tag: (1, 0, 0, 999999))
    monkeypatch.setattr(updater, "check_stable", raise_value_error)

    result = updater.check()

    assert result == CheckResult(status="error", error="Response format error: bad json")


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


def test_installer_temp_path_sanitizes_release_tag(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(updater.tempfile, "gettempdir", lambda: str(tmp_path))

    assert updater.installer_temp_path("v2.0.0/beta") == str(tmp_path / "Remaku_Setup_v2.0.0_beta.exe")
    assert updater.installer_temp_path("!!!") == str(tmp_path / "Remaku_Setup____.exe")


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


def test_download_cancel_during_read_removes_partial_without_done_or_error(tmp_path, monkeypatch) -> None:
    download, events = make_download(tmp_path)
    monkeypatch.setattr(updater, "ssl_context", lambda: None)

    class CancelingResponse(FakeDownloadResponse):
        def read(self, chunk_size: int) -> bytes:
            download.cancel()

            return b"abc"

    monkeypatch.setattr(
        updater,
        "urlopen",
        lambda request, timeout, context: CancelingResponse([b"abc"], content_length=3),
    )

    download.run()

    assert events == [("progress", 3, 3)]
    assert not (tmp_path / "installer.exe.part").exists()


def test_ssl_context_uses_certifi_bundle(monkeypatch) -> None:
    calls = []
    context = object()
    monkeypatch.setattr(updater.certifi, "where", lambda: "certifi.pem")
    monkeypatch.setattr(updater.ssl, "create_default_context", lambda cafile: calls.append(cafile) or context)

    assert updater.ssl_context() is context
    assert calls == ["certifi.pem"]


def test_parse_version_accepts_whitespace_and_missing_tag() -> None:
    assert updater.parse_version(" v1.2.3 ") == (1, 2, 3, 999999)
    assert updater.parse_version(None) is None


def test_fetch_json_reads_github_response(monkeypatch) -> None:
    requests = []
    payload = {"ok": True}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps(payload).encode()

    monkeypatch.setattr(updater, "ssl_context", lambda: "context")
    monkeypatch.setattr(
        updater,
        "urlopen",
        lambda request, timeout, context: requests.append((request, timeout, context)) or FakeResponse(),
    )

    assert updater.fetch_json("https://example.invalid/api") == payload
    request, timeout, context = requests[0]
    assert request.full_url == "https://example.invalid/api"
    assert request.headers == {"Accept": "application/vnd.github.v3+json"}
    assert timeout == updater.CHECK_TIMEOUT_S
    assert context == "context"


def test_check_stable_accepts_list_response(monkeypatch) -> None:
    monkeypatch.setattr(updater, "fetch_json", lambda url: [make_release("v2.0.0")])

    result = updater.check_stable(current=(1, 0, 0, 999999))

    assert result.status == "available"
    assert result.info is not None
    assert result.info.tag == "v2.0.0"


def test_check_uses_beta_channel(monkeypatch) -> None:
    class FakeGeneral:
        update_channel = "beta"

    class FakeConfig:
        general = FakeGeneral()

    class FakeConfigModel:
        config = FakeConfig()

    calls = []
    monkeypatch.setattr(updater, "config_model", FakeConfigModel())
    monkeypatch.setattr(updater, "parse_version", lambda tag: (1, 0, 0, 999999))
    monkeypatch.setattr(updater, "check_beta", lambda current: calls.append(current) or CheckResult(status="up_to_date"))

    assert updater.check() == CheckResult(status="up_to_date")
    assert calls == [(1, 0, 0, 999999)]


def test_check_async_posts_result_to_callback(monkeypatch) -> None:
    callbacks = []
    started_threads = []

    class FakePosted:
        def connect(self, callback) -> None:
            callbacks.append(callback)

        def emit(self, callback) -> None:
            callbacks[0](callback)

    class FakePoster:
        def __init__(self, parent) -> None:
            self.posted = FakePosted()

    class FakeThread:
        def __init__(self, target, name: str, daemon: bool) -> None:
            self.target = target
            self.name = name
            self.daemon = daemon

        def start(self) -> None:
            started_threads.append((self.name, self.daemon))
            self.target()

    result = CheckResult(status="up_to_date")
    received = []
    monkeypatch.setattr(updater, "Poster", FakePoster)
    monkeypatch.setattr(updater.threading, "Thread", FakeThread)
    monkeypatch.setattr(updater, "check", lambda: result)

    updater.check_async(parent="parent", callback=received.append)

    assert started_threads == [("updater-check", True)]
    assert received == [result]


def test_download_start_creates_daemon_thread(tmp_path, monkeypatch) -> None:
    download, events = make_download(tmp_path)
    started_threads = []

    class FakeThread:
        def __init__(self, target, name: str, daemon: bool) -> None:
            self.target = target
            self.name = name
            self.daemon = daemon

        def start(self) -> None:
            started_threads.append((self.target, self.name, self.daemon))

    monkeypatch.setattr(updater.threading, "Thread", FakeThread)

    download.start()

    assert events == []
    assert download.thread is not None
    assert started_threads == [(download.run, "updater-download", True)]


def test_download_post_suppresses_emit_errors(tmp_path) -> None:
    download, events = make_download(tmp_path)

    class RaisingPosted:
        def emit(self, callback) -> None:
            raise RuntimeError("deleted")

    download.post = updater.Download.post.__get__(download, updater.Download)
    download.poster.posted = RaisingPosted()

    download.post(lambda: events.append("posted"))

    assert events == []


def test_fake_download_response_returns_self_from_context_manager() -> None:
    response = FakeDownloadResponse([b"abc"])

    with response as opened:
        assert opened is response
