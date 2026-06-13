import threading
from collections.abc import Callable
from pathlib import Path
from urllib.error import URLError

from remaku.models.config_model import config_model
from remaku.models.macro_model import MacroModel
from remaku.models.pack_model import PackCatalog, PackCatalogEntry, PackListItem
from remaku.paths import pack_download_path
from remaku.services.macro_import_service import ImportMacroOptions, ImportMacroResult, install_macro_archive
from remaku.services.updater import Download, Poster, fetch_json
from remaku.version import __version__

PACKS_REPO_URL = "https://github.com/remaku/remaku-packs"
DEFAULT_CATALOG_URL = "https://raw.githubusercontent.com/remaku/remaku-packs/main/catalog.json"
PackVersion = tuple[int, int, int, str]


def fetch_catalog_async(parent, on_done: Callable[[PackCatalog], None], on_error: Callable[[str], None]) -> None:
    poster = Poster(parent)
    poster.posted.connect(lambda fn: fn())

    def worker() -> None:
        try:
            catalog = fetch_catalog()
        except ValueError as error:
            poster.posted.emit(lambda message=str(error): on_error(message))
            return

        poster.posted.emit(lambda: on_done(catalog))

    threading.Thread(target=worker, name="pack-catalog-fetch", daemon=True).start()


def fetch_catalog(url: str = DEFAULT_CATALOG_URL) -> PackCatalog:
    try:
        data = fetch_json(url)
    except (URLError, OSError, ValueError, KeyError) as error:
        raise ValueError(f"Unable to load pack catalog: {error}") from error

    if not isinstance(data, dict):
        raise ValueError("Pack catalog must be an object")

    return PackCatalog.from_dict(data)


def parse_pack_version(version: str) -> PackVersion:
    main, _, suffix = version.partition("-")
    parts = main.split(".")
    numbers = []

    for part in parts[:3]:
        try:
            numbers.append(int(part))
        except ValueError:
            numbers.append(0)

    while len(numbers) < 3:
        numbers.append(0)

    return (numbers[0], numbers[1], numbers[2], suffix)


def compare_pack_versions(installed: str, available: str) -> int:
    installed_version = parse_pack_version(installed)
    available_version = parse_pack_version(available)

    if installed_version < available_version:
        return -1

    if installed_version > available_version:
        return 1

    return 0


def is_remaku_version_compatible(entry: PackCatalogEntry, current_version: str = __version__) -> bool:
    minimum = entry.compatibility.remaku_min
    maximum = entry.compatibility.remaku_max

    if minimum and compare_pack_versions(current_version, minimum) < 0:
        return False

    return not (maximum and compare_pack_versions(current_version, maximum) > 0)


def build_pack_items(catalog: PackCatalog) -> list[PackListItem]:
    game_labels = {game.id: game.display_label() for game in catalog.games}
    items: list[PackListItem] = []

    for entry in catalog.packs:
        status = "available" if is_remaku_version_compatible(entry) else "incompatible"
        items.append(PackListItem(entry=entry, status=status, game_label=game_labels.get(entry.game, entry.game)))

    return items


def download_pack(parent, entry: PackCatalogEntry, on_progress, on_done, on_error) -> Download:
    destination = pack_download_path(entry.pack_id, entry.version)
    destination.parent.mkdir(parents=True, exist_ok=True)

    return Download(
        parent,
        entry.assets.zip_url,
        str(destination),
        on_progress,
        on_done,
        on_error,
    )


def import_pack_as_macro(archive_path: Path, macro_model: MacroModel) -> ImportMacroResult:
    result = install_macro_archive(archive_path, macro_model, ImportMacroOptions())

    if result.macro_id not in config_model.config.general.macro_order:
        config_model.config.general.macro_order.append(result.macro_id)
        config_model.save()

    return result
