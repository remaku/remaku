import contextlib
import json
import os
import re
import ssl
import subprocess
import tempfile
import threading
import webbrowser
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal
from urllib.error import URLError
from urllib.request import Request, urlopen

import certifi
from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QApplication

from remaku.models.config_model import config_model
from remaku.version import __version__

REPO = "remaku/remaku"
API_URL_STABLE = f"https://api.github.com/repos/{REPO}/releases/latest"
API_URL_BETA = f"https://api.github.com/repos/{REPO}/releases?per_page=10"
RELEASES_URL = f"https://github.com/{REPO}/releases/latest"
INSTALLER_ASSET_PREFIX = "Remaku_Setup"
CHECK_TIMEOUT_S = 5
DOWNLOAD_TIMEOUT_S = 60
CHUNK_SIZE = 64 * 1024
Version = tuple[int, int, int, int]


@dataclass(slots=True)
class UpdateInfo:
    tag: str
    version: Version
    body: str
    installer_url: str
    release_url: str


@dataclass(slots=True)
class CheckResult:
    status: Literal["available", "up_to_date", "error"]
    info: UpdateInfo | None = None
    error: str = ""


class Poster(QObject):
    posted = Signal(object)


def ssl_context() -> ssl.SSLContext:
    return ssl.create_default_context(cafile=certifi.where())


def parse_version(tag: str | None) -> Version | None:
    if not tag:
        return None

    match = re.match(r"^v?(\d+)\.(\d+)\.(\d+)(?:-[a-zA-Z]+\.?(\d+))?", tag.strip())

    if match is None:
        return None

    pre_num = int(match.group(4)) if match.group(4) else 999999
    return (int(match.group(1)), int(match.group(2)), int(match.group(3)), pre_num)


def find_installer_url(assets: list[dict]) -> str:
    for asset in assets:
        name = str(asset.get("name", ""))
        if name.startswith(INSTALLER_ASSET_PREFIX) and name.endswith(".exe"):
            return str(asset.get("browser_download_url", ""))

    return ""


def fetch_json(url: str) -> dict | list:
    request = Request(url, headers={"Accept": "application/vnd.github.v3+json"})
    with urlopen(request, timeout=CHECK_TIMEOUT_S, context=ssl_context()) as response:
        return json.loads(response.read())


def compare_release(data: dict, current: Version) -> CheckResult:
    latest_tag = str(data.get("tag_name", ""))
    latest = parse_version(latest_tag)
    if latest is None:
        return CheckResult(status="error", error=f"Cannot parse version: {latest_tag!r}")

    if latest <= current:
        return CheckResult(status="up_to_date")

    info = UpdateInfo(
        tag=latest_tag,
        version=latest,
        body=str(data.get("body", "") or ""),
        installer_url=find_installer_url(data.get("assets", [])),
        release_url=str(data.get("html_url") or f"https://github.com/{REPO}/releases/tag/{latest_tag}"),
    )

    return CheckResult(status="available", info=info)


def check_stable(current: Version) -> CheckResult:
    data = fetch_json(API_URL_STABLE)
    release = data[0] if isinstance(data, list) else data
    return compare_release(release, current)


def check_beta(current: Version) -> CheckResult:
    releases = fetch_json(API_URL_BETA)
    if not isinstance(releases, list) or not releases:
        return CheckResult(status="error", error="No releases found")

    best_release = None
    best_version: Version | None = None
    for release in releases:
        if release.get("draft", False):
            continue

        version = parse_version(str(release.get("tag_name", "")))
        if version is None:
            continue

        if best_version is None or version > best_version:
            best_version = version
            best_release = release

    if best_release is None or best_version is None:
        return CheckResult(status="error", error="No valid releases found")

    return compare_release(best_release, current)


def check() -> CheckResult:
    current = parse_version(__version__)
    if current is None:
        return CheckResult(status="error", error=f"Cannot parse current version: {__version__}")

    channel = config_model.config.general.update_channel
    try:
        return check_beta(current) if channel == "beta" else check_stable(current)
    except (URLError, OSError) as error:
        return CheckResult(status="error", error=f"Connection failed: {error}")
    except (ValueError, KeyError) as error:
        return CheckResult(status="error", error=f"Response format error: {error}")


def check_async(parent, callback: Callable[[CheckResult], None]) -> None:
    poster = Poster(parent)
    poster.posted.connect(lambda fn: fn())

    def worker() -> None:
        result = check()
        poster.posted.emit(lambda: callback(result))

    threading.Thread(target=worker, name="updater-check", daemon=True).start()


def installer_temp_path(tag: str) -> str:
    safe_tag = re.sub(r"[^A-Za-z0-9._-]", "_", tag) or "latest"
    return os.path.join(tempfile.gettempdir(), f"Remaku_Setup_{safe_tag}.exe")


def launch_installer_and_quit(installer_path: str) -> None:
    subprocess.Popen(
        [installer_path, "/VERYSILENT", "/SUPPRESSMSGBOXES"],
        close_fds=True,
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
    )
    QTimer.singleShot(200, QApplication.quit)


def remember_skip(tag: str) -> None:
    config_model.config.general.skipped_version = tag
    config_model.save()


def open_releases_page(url: str = RELEASES_URL) -> None:
    webbrowser.open(url)


class Download:
    def __init__(
        self,
        parent,
        url: str,
        destination: str,
        on_progress: Callable[[int, int], None],
        on_done: Callable[[str], None],
        on_error: Callable[[str], None],
    ) -> None:
        self.parent = parent
        self.url = url
        self.destination = destination
        self.on_progress = on_progress
        self.on_done = on_done
        self.on_error = on_error
        self.cancel_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.poster = Poster(parent)
        self.poster.posted.connect(lambda fn: fn())

    def start(self) -> None:
        self.thread = threading.Thread(target=self.run, name="updater-download", daemon=True)
        self.thread.start()

    def cancel(self) -> None:
        self.cancel_event.set()

    def post(self, callback: Callable[[], None]) -> None:
        with contextlib.suppress(Exception):
            self.poster.posted.emit(callback)

    def run(self) -> None:
        temp_path = self.destination + ".part"

        try:
            request = Request(self.url, headers={"Accept": "application/octet-stream"})
            with urlopen(request, timeout=DOWNLOAD_TIMEOUT_S, context=ssl_context()) as response:
                total = int(response.headers.get("Content-Length", "0") or 0)
                downloaded = 0

                with open(temp_path, "wb") as file:
                    while True:
                        if self.cancel_event.is_set():
                            raise OSError("Download cancelled by user")

                        chunk = response.read(CHUNK_SIZE)
                        if not chunk:
                            break

                        file.write(chunk)
                        downloaded += len(chunk)
                        self.post(lambda d=downloaded, t=total: self.on_progress(d, t))

            os.replace(temp_path, self.destination)
            self.post(lambda: self.on_done(self.destination))
        except Exception as error:
            with contextlib.suppress(OSError):
                if os.path.exists(temp_path):
                    os.remove(temp_path)

            if self.cancel_event.is_set():
                return

            self.post(lambda err=str(error): self.on_error(err))
