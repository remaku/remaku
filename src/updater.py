"""Update checker module.

Handles interaction with the GitHub API to check for new versions.
"""

import contextlib
import json
import os
import re
import subprocess
import tempfile
import threading
import webbrowser
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal
from urllib.error import URLError
from urllib.request import Request, urlopen

from loguru import logger
from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QTextBrowser,
    QVBoxLayout,
)
from qfluentwidgets import BodyLabel, CaptionLabel, PrimaryPushButton, ProgressBar, PushButton, SubtitleLabel

import config as cfg
import i18n
from i18n import t
from version import __version__

REPO = "remaku/remaku"
API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
API_URL_ALL = f"https://api.github.com/repos/{REPO}/releases?per_page=1"
RELEASES_URL = f"https://github.com/{REPO}/releases/latest"
INSTALLER_ASSET_PREFIX = "Remaku_Setup"

CHECK_TIMEOUT_S = 5
DOWNLOAD_TIMEOUT_S = 60
CHUNK_SIZE = 64 * 1024


Version = tuple[int, int, int]


@dataclass
class UpdateInfo:
    tag: str
    version: Version
    body: str
    installer_url: str


@dataclass
class CheckResult:
    status: Literal["available", "up_to_date", "error"]
    info: UpdateInfo | None = None
    error: str = ""


def localized_body(body: str) -> str:
    """Extract the section matching current_locale from a lang-tagged body."""
    sections = re.split(r"<!--\s*lang:(\w+)\s*-->", body)

    if len(sections) < 3:
        return body.strip()

    mapping: dict[str, str] = {}

    for i in range(1, len(sections), 2):
        mapping[sections[i].strip()] = sections[i + 1].strip()

    return mapping.get(i18n.current_locale) or mapping.get("en") or body.strip()


def parse_version(tag: str) -> Version | None:
    """Strictly parse 'vX.Y.Z' or 'X.Y.Z', returns None if unparseable.

    Suffixes ('-rc1', '+build', etc.) are ignored.
    """
    if not tag:
        return None

    m = re.match(r"^v?(\d+)\.(\d+)\.(\d+)", tag.strip())

    if not m:
        return None

    return (int(m.group(1)), int(m.group(2)), int(m.group(3)))


def find_installer_url(assets: list[dict]) -> str:
    for asset in assets:
        name = asset.get("name", "")
        if name.startswith(INSTALLER_ASSET_PREFIX) and name.endswith(".exe"):
            return asset.get("browser_download_url", "")

    return ""


def check() -> CheckResult:
    """Synchronous check; use check_async externally."""
    current = parse_version(__version__)

    if current is None:
        logger.warning("updater: cannot parse current version: {}", __version__)
        return CheckResult(status="error", error=f"Cannot parse current version: {__version__}")

    conf = cfg.load()
    url = API_URL_ALL if conf.general.update_channel == "beta" else API_URL

    try:
        req = Request(url, headers={"Accept": "application/vnd.github.v3+json"})

        with urlopen(req, timeout=CHECK_TIMEOUT_S) as resp:
            raw = json.loads(resp.read())
            data = raw[0] if isinstance(raw, list) else raw
    except (URLError, OSError) as e:
        logger.warning("updater: update check connection failed: {}", e)
        return CheckResult(status="error", error=f"Connection failed: {e}")
    except (ValueError, KeyError) as e:
        logger.warning("updater: update check response format error: {}", e)
        return CheckResult(status="error", error=f"Response format error: {e}")

    latest_tag = data.get("tag_name", "")
    latest = parse_version(latest_tag)

    if latest is None:
        logger.warning("updater: cannot parse latest version: {!r}", latest_tag)
        return CheckResult(status="error", error=f"Cannot parse version: {latest_tag!r}")

    if latest <= current:
        return CheckResult(status="up_to_date")

    info = UpdateInfo(
        tag=latest_tag,
        version=latest,
        body=data.get("body", "") or "",
        installer_url=find_installer_url(data.get("assets", [])),
    )

    logger.info("updater: new version found {} (current {})", latest_tag, __version__)

    return CheckResult(status="available", info=info)


def check_async(parent, callback: Callable[[CheckResult], None]) -> None:
    """Background check, result is called back on the main thread."""
    poster = Poster(parent)
    poster.posted.connect(lambda fn: fn())

    def worker() -> None:
        result = check()
        with contextlib.suppress(Exception):
            poster.posted.emit(lambda: callback(result))

    threading.Thread(target=worker, name="updater-check", daemon=True).start()


class Poster(QObject):
    """Cross-thread callback signal carrier."""

    posted = Signal(object)


class Download:
    """Background installer download, cancellable mid-way."""

    def __init__(
        self,
        parent,
        url: str,
        dest: str,
        on_progress: Callable[[int, int], None],
        on_done: Callable[[str], None],
        on_error: Callable[[str], None],
    ) -> None:
        self.parent = parent
        self.url = url
        self.destination = dest
        self.on_progress = on_progress
        self.on_done = on_done
        self.on_error = on_error
        self.cancel_evt = threading.Event()
        self.thread: threading.Thread | None = None
        # Use QObject + Signal to safely post worker thread callbacks to the main thread.
        # Poster is created on the main thread, posted signal defaults to AutoConnection,
        # cross-thread emit automatically becomes QueuedConnection.
        self.poster = Poster()
        self.poster.posted.connect(lambda fn: fn())

    def start(self) -> None:
        self.thread = threading.Thread(target=self.run, name="updater-download", daemon=True)
        self.thread.start()

    def cancel(self) -> None:
        self.cancel_evt.set()

    def post(self, fn: Callable[[], None]) -> None:
        with contextlib.suppress(Exception):
            self.poster.posted.emit(fn)

    def run(self) -> None:
        tmp_path = self.destination + ".part"

        try:
            req = Request(self.url, headers={"Accept": "application/octet-stream"})

            with urlopen(req, timeout=DOWNLOAD_TIMEOUT_S) as resp:
                total = int(resp.headers.get("Content-Length", "0") or 0)
                downloaded = 0

                with open(tmp_path, "wb") as f:
                    while True:
                        if self.cancel_evt.is_set():
                            raise OSError("Download cancelled by user")
                        chunk = resp.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        self.post(lambda d=downloaded, t=total: self.on_progress(d, t))

            os.replace(tmp_path, self.destination)
            self.post(lambda: self.on_done(self.destination))

        except Exception as e:
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except OSError:
                pass

            if self.cancel_evt.is_set():
                logger.info("updater: download cancelled by user")
                return

            logger.warning("updater: download failed: {}", e)

            self.post(lambda err=str(e): self.on_error(err))


def installer_temp_path(tag: str) -> str:
    safe_tag = re.sub(r"[^A-Za-z0-9._-]", "_", tag) or "latest"
    return os.path.join(tempfile.gettempdir(), f"Remaku_Setup_{safe_tag}.exe")


def launch_installer_and_quit(installer_path: str) -> None:
    """Launch the silent installer then close the app; the installer will restart the new version."""
    try:
        # Use detached process to ensure installer keeps running after app exits
        subprocess.Popen(
            [installer_path, "/VERYSILENT", "/SUPPRESSMSGBOXES"],
            close_fds=True,
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        )
        logger.info("updater: launched silent installer: {}", installer_path)
    except OSError as e:
        logger.error("updater: failed to launch installer: {}", e)
        raise

    QTimer.singleShot(200, QApplication.quit)


def remember_skip(tag: str) -> None:
    """Write tag to config's skipped_version."""
    conf = cfg.load()
    conf.general.skipped_version = tag
    cfg.save(conf)
    logger.info("updater: skipped version recorded: {}", tag)


def clear_skip() -> None:
    conf = cfg.load()
    conf.general.skipped_version = ""
    cfg.save(conf)
    logger.info("updater: skipped version cleared")


def open_releases_page() -> None:
    webbrowser.open(RELEASES_URL)


class UpdateDialog(QDialog):
    """New version prompt dialog: shows release notes, offers download/install, skip, or later."""

    PHASE_PROMPT = "prompt"
    PHASE_DOWNLOAD = "download"
    PHASE_ERROR = "error"

    def __init__(self, parent, info: UpdateInfo) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("updater.title"))
        self.setFixedSize(520, 460)
        # always on top
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)

        self.parent_app = parent
        self.info = info
        self.download: Download | None = None
        self.phase = self.PHASE_PROMPT

        self.build_ui()

    def build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 16, 20, 16)
        outer.setSpacing(0)

        title_lbl = SubtitleLabel(t("updater.new_version_found", tag=self.info.tag))
        outer.addWidget(title_lbl)

        outer.addSpacing(8)

        subtitle_lbl = CaptionLabel(t("updater.current_version", version=__version__))
        outer.addWidget(subtitle_lbl)

        outer.addSpacing(24)

        notes_title = BodyLabel(t("updater.release_notes"))
        outer.addWidget(notes_title)

        outer.addSpacing(4)

        self.notes_box = QTextBrowser()
        self.notes_box.setOpenExternalLinks(True)
        self.notes_box.setMarkdown(localized_body(self.info.body) or t("updater.no_notes"))
        outer.addWidget(self.notes_box, stretch=1)

        outer.addSpacing(24)

        self.status_lbl = CaptionLabel("")
        outer.addWidget(self.status_lbl)

        self.progress = ProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.hide()  # Only shown during download phase
        outer.addWidget(self.progress)

        outer.addSpacing(24)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self.btn_skip = PushButton(t("updater.skip_version"))
        self.btn_skip.setFixedWidth(110)
        self.btn_skip.clicked.connect(self.on_skip)
        btn_row.addWidget(self.btn_skip)

        btn_row.addStretch(1)

        self.btn_later = PushButton(t("updater.later"))
        self.btn_later.setFixedWidth(110)
        self.btn_later.clicked.connect(self.on_later)
        btn_row.addWidget(self.btn_later)

        self.btn_install = PrimaryPushButton(t("updater.install_now"))
        self.btn_install.setFixedWidth(110)
        self.btn_install.setDefault(True)
        self.btn_install.clicked.connect(self.on_install)
        btn_row.addWidget(self.btn_install)

        outer.addLayout(btn_row)

    def on_skip(self) -> None:
        try:
            remember_skip(self.info.tag)
        except OSError as e:
            logger.warning("updater: failed to save skipped version: {}", e)
        self.close()

    def on_later(self) -> None:
        self.close()

    def on_install(self) -> None:
        if not self.info.installer_url:
            # No installer asset: fallback to opening browser
            open_releases_page()
            self.close()
            return
        self.enter_download_phase()

    def enter_download_phase(self) -> None:
        self.phase = self.PHASE_DOWNLOAD
        self.btn_skip.setEnabled(False)
        self.btn_later.setEnabled(False)
        self.btn_install.setText(t("action.cancel"))
        with contextlib.suppress(RuntimeError):
            self.btn_install.clicked.disconnect()
        self.btn_install.clicked.connect(self.on_cancel_download)

        self.progress.show()
        self.progress.setValue(0)
        self.status_lbl.setText(t("updater.preparing"))

        destination = installer_temp_path(self.info.tag)
        # Clear stale .part files
        part = destination + ".part"
        try:
            if os.path.exists(part):
                os.remove(part)
        except OSError:
            pass

        self.download = Download(
            parent=self,
            url=self.info.installer_url,
            dest=destination,
            on_progress=self.on_progress,
            on_done=self.on_download_done,
            on_error=self.on_download_error,
        )
        self.download.start()

    def on_progress(self, downloaded: int, total: int) -> None:
        if total > 0:
            self.progress.setValue(int(downloaded * 100 / total))
            mb_downloaded = downloaded / (1024 * 1024)
            mb_total = total / (1024 * 1024)
            self.status_lbl.setText(
                t("updater.downloading", downloaded=f"{mb_downloaded:.1f}", total=f"{mb_total:.1f}")
            )
        else:
            mb_downloaded = downloaded / (1024 * 1024)
            self.status_lbl.setText(t("updater.downloading_unknown", downloaded=f"{mb_downloaded:.1f}"))

    def on_cancel_download(self) -> None:
        if self.download:
            self.download.cancel()
        self.close()

    def on_download_done(self, installer_path: str) -> None:
        self.status_lbl.setText(t("updater.installing"))
        self.progress.setValue(100)
        # Brief delay to let user see the completed state
        QTimer.singleShot(300, lambda: self.start_install(installer_path))

    def start_install(self, installer_path: str) -> None:
        try:
            launch_installer_and_quit(installer_path)
        except OSError as e:
            self.show_error(t("updater.install_failed", error=e))

    def on_download_error(self, error: str) -> None:
        self.show_error(t("updater.download_failed", error=error))

    def show_error(self, message: str) -> None:
        self.phase = self.PHASE_ERROR
        self.progress.hide()
        self.status_lbl.setText(message)

        self.btn_skip.setEnabled(True)

        self.btn_later.setEnabled(True)
        self.btn_later.setText(t("action.close"))
        with contextlib.suppress(RuntimeError):
            self.btn_later.clicked.disconnect()
        self.btn_later.clicked.connect(self.close)

        self.btn_install.setEnabled(True)
        self.btn_install.setText(t("updater.open_download_page"))
        with contextlib.suppress(RuntimeError):
            self.btn_install.clicked.disconnect()
        self.btn_install.clicked.connect(self.fallback_browser)

    def fallback_browser(self) -> None:
        open_releases_page()
        self.close()

    def closeEvent(self, event) -> None:
        if self.phase == self.PHASE_DOWNLOAD and self.download:
            self.download.cancel()

        super().closeEvent(event)


def prompt_update(parent, info: UpdateInfo) -> UpdateDialog:
    dlg = UpdateDialog(parent, info)
    dlg.show()
    return dlg
