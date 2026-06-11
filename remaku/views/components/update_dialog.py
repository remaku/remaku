import contextlib
import os
import re

from PySide6.QtCore import QLocale, QTimer
from PySide6.QtWidgets import QTextBrowser, QVBoxLayout
from qfluentwidgets import BodyLabel, CaptionLabel, MessageBoxBase, ProgressBar, PushButton, SubtitleLabel

from remaku.models.config_model import config_model
from remaku.services.updater import (
    RELEASES_URL,
    Download,
    UpdateInfo,
    installer_temp_path,
    launch_installer_and_quit,
    open_releases_page,
    remember_skip,
)
from remaku.version import __version__


def normalize_language(language: str) -> str:
    return language.strip().replace("-", "_").lower()


def localized_body(body: str) -> str:
    sections = re.split(r"<!--\s*lang:([\w-]+)\s*-->", body)

    if len(sections) < 3:
        return body.strip()

    mapping: dict[str, str] = {}

    for index in range(1, len(sections), 2):
        mapping[normalize_language(sections[index])] = sections[index + 1].strip()

    language = config_model.config.general.language

    if language == "system":
        language = QLocale.system().name()

    normalized_language = normalize_language(language)
    base_language = normalized_language.split("_", 1)[0]

    return mapping.get(normalized_language) or mapping.get(base_language) or mapping.get("en") or body.strip()


class UpdateDialog(MessageBoxBase):
    PHASE_PROMPT = "prompt"
    PHASE_DOWNLOAD = "download"
    PHASE_ERROR = "error"

    def __init__(self, parent, info: UpdateInfo) -> None:
        super().__init__(parent)

        self.info = info
        self.download: Download | None = None
        self.phase = self.PHASE_PROMPT
        self.init_ui()

    def init_ui(self) -> None:
        self.widget.setMinimumWidth(550)

        self.title_label = SubtitleLabel(self.tr("New version {tag} available").format(tag=self.info.tag))
        self.current_version_label = CaptionLabel(self.tr("Current version: {version}").format(version=__version__))

        self.notes_box = QTextBrowser(self)
        self.notes_box.setOpenExternalLinks(True)
        self.notes_box.setMarkdown(localized_body(self.info.body) or self.tr("No release notes available."))
        self.notes_box.setMinimumHeight(220)

        self.status_label = CaptionLabel("")
        self.progress = ProgressBar(self)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.hide()

        self.yesButton.setText(self.tr("Install Now"))
        self.cancelButton.setText(self.tr("Later"))
        self.yesButton.clicked.disconnect()
        self.yesButton.clicked.connect(self.handle_install)

        self.viewLayout.addWidget(self.title_label)
        self.viewLayout.addSpacing(4)
        self.viewLayout.addWidget(self.current_version_label)
        self.viewLayout.addSpacing(8)
        self.viewLayout.addWidget(BodyLabel(self.tr("Release Notes"), self))

        notes_layout = QVBoxLayout()
        notes_layout.addWidget(self.notes_box)
        notes_layout.addWidget(self.status_label)
        notes_layout.addWidget(self.progress)
        self.viewLayout.addLayout(notes_layout)

        self.skip_button = PushButton(self.tr("Skip This Version"), self)
        self.buttonLayout.insertWidget(0, self.skip_button)
        self.buttonLayout.insertStretch(1, 1)
        self.skip_button.clicked.connect(self.handle_skip)

    def handle_skip(self) -> None:
        remember_skip(self.info.tag)
        self.reject()

    def handle_install(self) -> None:
        if not self.info.installer_url:
            open_releases_page(self.info.release_url or RELEASES_URL)
            self.close()
            return

        self.enter_download_phase()

    def enter_download_phase(self) -> None:
        self.phase = self.PHASE_DOWNLOAD
        self.skip_button.setEnabled(False)
        self.cancelButton.setEnabled(False)
        self.yesButton.setText(self.tr("Cancel"))
        with contextlib.suppress(RuntimeError):
            self.yesButton.clicked.disconnect()
        self.yesButton.clicked.connect(self.handle_cancel_download)

        self.progress.show()
        self.progress.setValue(0)
        self.status_label.setText(self.tr("Preparing download..."))

        destination = installer_temp_path(self.info.tag)
        part_path = destination + ".part"
        with contextlib.suppress(OSError):
            if os.path.exists(part_path):
                os.remove(part_path)

        self.download = Download(
            parent=self,
            url=self.info.installer_url,
            destination=destination,
            on_progress=self.on_progress,
            on_done=self.on_download_done,
            on_error=self.on_download_error,
        )
        self.download.start()

    def on_progress(self, downloaded: int, total: int) -> None:
        if total > 0:
            self.progress.setValue(int(downloaded * 100 / total))
            downloaded_mb = downloaded / (1024 * 1024)
            total_mb = total / (1024 * 1024)
            self.status_label.setText(
                self.tr("Downloading {downloaded:.1f}/{total:.1f} MB").format(
                    downloaded=downloaded_mb,
                    total=total_mb,
                )
            )
            return

        downloaded_mb = downloaded / (1024 * 1024)
        self.status_label.setText(self.tr("Downloading {downloaded:.1f} MB").format(downloaded_mb=downloaded_mb))

    def handle_cancel_download(self) -> None:
        if self.download is not None:
            self.download.cancel()
        self.close()

    def on_download_done(self, installer_path: str) -> None:
        self.status_label.setText(self.tr("Installing update..."))
        self.progress.setValue(100)
        QTimer.singleShot(300, lambda: self.start_install(installer_path))

    def start_install(self, installer_path: str) -> None:
        try:
            launch_installer_and_quit(installer_path)
        except OSError as error:
            self.show_error(self.tr("Failed to launch installer: {error}").format(error=error))

    def on_download_error(self, error: str) -> None:
        self.show_error(self.tr("Download failed: {error}").format(error=error))

    def show_error(self, message: str) -> None:
        self.phase = self.PHASE_ERROR
        self.progress.hide()
        self.status_label.setText(message)
        self.skip_button.setEnabled(True)
        self.cancelButton.setEnabled(True)
        self.cancelButton.setText(self.tr("Close"))
        self.yesButton.setEnabled(True)
        self.yesButton.setText(self.tr("Open Download Page"))

        with contextlib.suppress(RuntimeError):
            self.yesButton.clicked.disconnect()
        self.yesButton.clicked.connect(self.fallback_browser)

    def fallback_browser(self) -> None:
        open_releases_page(self.info.release_url or RELEASES_URL)
        self.close()
