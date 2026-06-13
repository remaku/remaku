from typing import Any, ClassVar, cast

from PySide6.QtWidgets import QWidget

from remaku.core.i18n import normalize_language_key
from remaku.models.config_model import AppConfig
from remaku.services.updater import UpdateInfo
from remaku.views.components import update_dialog
from remaku.views.components.update_dialog import UpdateDialog, localized_body


class FakeConfigModel:
    def __init__(self) -> None:
        self.config = AppConfig()


class FakeDownload:
    instances: ClassVar[list["FakeDownload"]] = []

    def __init__(self, parent, url: str, destination: str, on_progress, on_done, on_error) -> None:
        self.parent = parent
        self.url = url
        self.destination = destination
        self.on_progress = on_progress
        self.on_done = on_done
        self.on_error = on_error
        self.start_calls = 0
        self.cancel_calls = 0
        FakeDownload.instances.append(self)

    def start(self) -> None:
        self.start_calls += 1

    def cancel(self) -> None:
        self.cancel_calls += 1


def make_parent(qtbot) -> QWidget:
    parent = QWidget()
    parent.resize(800, 600)
    qtbot.addWidget(parent)
    return parent


def make_info(installer_url: str = "https://example.invalid/installer.exe") -> UpdateInfo:
    return UpdateInfo(
        tag="v2.0.0",
        version=(2, 0, 0, 999999),
        body="<!-- lang:en -->English notes<!-- lang:zh_TW -->中文說明",
        installer_url=installer_url,
        release_url="https://example.invalid/releases",
    )


def make_dialog(qtbot, info: UpdateInfo | None = None) -> tuple[QWidget, UpdateDialog]:
    parent = make_parent(qtbot)
    dialog = UpdateDialog(parent, info or make_info())
    return parent, dialog


def test_normalize_language_handles_hyphen_and_case() -> None:
    assert normalize_language_key("ZH-tw") == "zh_tw"


def test_localized_body_uses_configured_language(monkeypatch) -> None:
    fake_config = FakeConfigModel()
    fake_config.config.general.language = "zh_TW"
    monkeypatch.setattr(update_dialog, "config_model", fake_config)

    assert localized_body("<!-- lang:en -->English<!-- lang:zh_TW -->繁中") == "繁中"


def test_localized_body_returns_plain_body_without_language_sections() -> None:
    assert localized_body("  Plain release notes  ") == "Plain release notes"


def test_update_dialog_skip_remembers_version(monkeypatch, qtbot) -> None:
    remembered = []
    _parent, dialog = make_dialog(qtbot)
    monkeypatch.setattr(update_dialog, "remember_skip", remembered.append)

    dialog.handle_skip()

    assert remembered == ["v2.0.0"]


def test_update_dialog_install_without_installer_opens_release_page(monkeypatch, qtbot) -> None:
    opened = []
    _parent, dialog = make_dialog(qtbot, make_info(installer_url=""))
    monkeypatch.setattr(update_dialog, "open_releases_page", opened.append)

    dialog.handle_install()

    assert opened == ["https://example.invalid/releases"]


def test_update_dialog_enter_download_phase_starts_download(tmp_path, monkeypatch, qtbot) -> None:
    FakeDownload.instances.clear()
    part_path = tmp_path / "installer.exe.part"
    part_path.write_bytes(b"partial")
    _parent, dialog = make_dialog(qtbot)
    monkeypatch.setattr(update_dialog, "Download", FakeDownload)
    monkeypatch.setattr(update_dialog, "installer_temp_path", lambda tag: str(tmp_path / "installer.exe"))

    dialog.enter_download_phase()

    download = FakeDownload.instances[0]
    assert dialog.phase == dialog.PHASE_DOWNLOAD
    assert dialog.download is download
    assert download.url == "https://example.invalid/installer.exe"
    assert download.start_calls == 1
    assert not part_path.exists()
    assert not dialog.progress.isHidden()
    assert dialog.yesButton.text() == "Cancel"


def test_update_dialog_install_with_installer_enters_download_phase(monkeypatch, qtbot) -> None:
    _parent, dialog = make_dialog(qtbot)
    entered = []
    monkeypatch.setattr(dialog, "enter_download_phase", lambda: entered.append(True))

    dialog.handle_install()

    assert entered == [True]


def test_update_dialog_progress_updates_label(qtbot) -> None:
    _parent, dialog = make_dialog(qtbot)

    dialog.on_progress(1024 * 1024, 2 * 1024 * 1024)

    assert dialog.progress.value() == 50
    assert "1.0/2.0 MB" in dialog.status_label.text()


def test_update_dialog_progress_without_total_updates_downloaded_label(qtbot) -> None:
    _parent, dialog = make_dialog(qtbot)

    dialog.on_progress(1024 * 1024, 0)

    assert "1.0 MB" in dialog.status_label.text()


def test_update_dialog_done_schedules_install(monkeypatch, qtbot) -> None:
    _parent, dialog = make_dialog(qtbot)
    scheduled = []
    monkeypatch.setattr(update_dialog.QTimer, "singleShot", lambda delay, callback: scheduled.append((delay, callback)))

    dialog.on_download_done("installer.exe")

    assert dialog.progress.value() == 100
    assert dialog.status_label.text() == "Installing update..."
    assert scheduled[0][0] == 300


def test_update_dialog_error_enters_error_phase(qtbot) -> None:
    _parent, dialog = make_dialog(qtbot)
    dialog.progress.show()

    dialog.on_download_error("network")

    assert dialog.phase == dialog.PHASE_ERROR
    assert dialog.progress.isHidden()
    assert dialog.cancelButton.text() == "Close"
    assert dialog.yesButton.text() == "Open Download Page"
    assert "network" in dialog.status_label.text()


def test_update_dialog_cancel_download_calls_download_cancel(qtbot) -> None:
    _parent, dialog = make_dialog(qtbot)
    download = FakeDownload(dialog, "url", "dest", lambda d, t: None, lambda p: None, lambda e: None)
    cast(Any, dialog).download = download

    dialog.handle_cancel_download()

    assert download.cancel_calls == 1


def test_update_dialog_start_install_reports_launch_error(monkeypatch, qtbot) -> None:
    _parent, dialog = make_dialog(qtbot)
    monkeypatch.setattr(
        update_dialog, "launch_installer_and_quit", lambda path: (_ for _ in ()).throw(OSError("blocked"))
    )

    dialog.start_install("installer.exe")

    assert dialog.phase == dialog.PHASE_ERROR
    assert "blocked" in dialog.status_label.text()


def test_update_dialog_fallback_browser_opens_release_page(monkeypatch, qtbot) -> None:
    opened = []
    _parent, dialog = make_dialog(qtbot)
    monkeypatch.setattr(update_dialog, "open_releases_page", opened.append)

    dialog.fallback_browser()

    assert opened == ["https://example.invalid/releases"]
