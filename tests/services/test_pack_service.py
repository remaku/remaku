from pathlib import Path
from typing import cast
from urllib.error import URLError

import pytest

from remaku.models.config_model import AppConfig
from remaku.models.macro_model import Macro, MacroModel
from remaku.models.pack_model import PackCatalog, PackCatalogEntry
from remaku.services import pack_service


class FakeConfigModel:
    def __init__(self) -> None:
        self.config = AppConfig()
        self.save_calls = 0

    def save(self) -> None:
        self.save_calls += 1


class FakeMacroModel:
    def __init__(self) -> None:
        self.macros: dict[str, Macro] = {}

    def save(self, macro: Macro) -> None:
        self.macros[macro.meta.id] = macro


def make_catalog_data() -> dict:
    return {
        "schema_version": 1,
        "repo_url": "https://github.com/remaku/remaku-packs",
        "games": [{"id": "fh6", "label": "Forza Horizon 6"}],
        "packs": [
            {
                "pack_id": "fh6.sample",
                "game": "fh6",
                "label": {"en_US": "Sample Pack", "zh_TW": "範例套件", "zh_CN": "示例套件"},
                "description": {"en_US": "Sample description", "zh_TW": "範例描述", "zh_CN": "示例描述"},
                "author": "Remaku",
                "version": "1.1.0",
                "release_tag": "v2",
                "default_language": "en_US",
                "assets": {"zip_url": "https://example.invalid/sample.zip"},
                "language_assets": {
                    "en_US": {"zip_url": "https://example.invalid/sample-en_US.zip"},
                    "zh_TW": {"zip_url": "https://example.invalid/sample-zh_TW.zip"},
                },
            }
        ],
    }


def make_entry() -> PackCatalogEntry:
    return PackCatalogEntry.from_dict(make_catalog_data()["packs"][0])


def test_fetch_catalog_parses_json(monkeypatch) -> None:
    monkeypatch.setattr(pack_service, "fetch_json", lambda url: make_catalog_data())

    catalog = pack_service.fetch_catalog("https://example.invalid/catalog.json")

    assert catalog.packs[0].pack_id == "fh6.sample"


def test_fetch_catalog_wraps_fetch_errors(monkeypatch) -> None:
    def fetch_json(url: str) -> dict:
        raise URLError("offline")

    monkeypatch.setattr(pack_service, "fetch_json", fetch_json)

    with pytest.raises(ValueError, match="Unable to load pack catalog"):
        pack_service.fetch_catalog("https://example.invalid/catalog.json")


def test_fetch_catalog_requires_object(monkeypatch) -> None:
    monkeypatch.setattr(pack_service, "fetch_json", lambda url: [])

    with pytest.raises(ValueError, match="Pack catalog must be an object"):
        pack_service.fetch_catalog("https://example.invalid/catalog.json")


def test_fetch_catalog_async_posts_catalog(monkeypatch) -> None:
    callbacks = []
    started_threads = []
    results = []

    class FakePoster:
        def __init__(self, parent) -> None:
            self.posted = self

        def connect(self, callback) -> None:
            callbacks.append(callback)

        def emit(self, callback) -> None:
            callback()

    class FakeThread:
        def __init__(self, target, name: str, daemon: bool) -> None:
            self.target = target
            self.name = name
            self.daemon = daemon

        def start(self) -> None:
            started_threads.append(self)
            self.target()

    monkeypatch.setattr(pack_service, "Poster", FakePoster)
    monkeypatch.setattr(pack_service.threading, "Thread", FakeThread)
    monkeypatch.setattr(pack_service, "fetch_catalog", lambda: PackCatalog.from_dict(make_catalog_data()))

    pack_service.fetch_catalog_async(object(), results.append, lambda error: None)

    assert callbacks
    assert started_threads[0].name == "pack-catalog-fetch"
    assert started_threads[0].daemon is True
    assert results[0].packs[0].pack_id == "fh6.sample"


def test_fetch_catalog_async_posts_error(monkeypatch) -> None:
    errors = []

    class FakePoster:
        def __init__(self, parent) -> None:
            self.posted = self

        def connect(self, callback) -> None:
            callback(lambda: None)

        def emit(self, callback) -> None:
            callback()

    class FakeThread:
        def __init__(self, target, name: str, daemon: bool) -> None:
            self.target = target

        def start(self) -> None:
            self.target()

    def fetch_catalog() -> PackCatalog:
        raise ValueError("bad catalog")

    monkeypatch.setattr(pack_service, "Poster", FakePoster)
    monkeypatch.setattr(pack_service.threading, "Thread", FakeThread)
    monkeypatch.setattr(pack_service, "fetch_catalog", fetch_catalog)

    pack_service.fetch_catalog_async(object(), lambda catalog: None, errors.append)

    assert errors == ["bad catalog"]


def test_build_pack_items_reports_available_with_game_label() -> None:
    catalog = PackCatalog.from_dict(make_catalog_data())

    items = pack_service.build_pack_items(catalog)

    assert items[0].status == "available"
    assert items[0].game_label == "Forza Horizon 6"


def test_build_pack_items_reports_incompatible() -> None:
    data = make_catalog_data()
    data["packs"][0]["compatibility"] = {"remaku_min": "99.0.0", "remaku_max": ""}
    catalog = PackCatalog.from_dict(data)

    items = pack_service.build_pack_items(catalog)

    assert items[0].status == "incompatible"


def test_is_remaku_version_compatible_respects_min_and_max() -> None:
    entry = make_entry()
    entry.compatibility.remaku_min = "0.4.0"
    entry.compatibility.remaku_max = "0.6.0"

    assert pack_service.is_remaku_version_compatible(entry, "0.5.0") is True
    assert pack_service.is_remaku_version_compatible(entry, "0.3.0") is False
    assert pack_service.is_remaku_version_compatible(entry, "0.7.0") is False


def test_compare_pack_versions() -> None:
    assert pack_service.compare_pack_versions("1.0.0", "1.1.0") == -1
    assert pack_service.compare_pack_versions("1.1.0", "1.0.0") == 1
    assert pack_service.compare_pack_versions("1.0", "1.0.0") == 0
    assert pack_service.compare_pack_versions("bad", "0.0.1") == -1


def test_download_pack_creates_cache_destination(tmp_path: Path, monkeypatch) -> None:
    downloads = []
    entry = make_entry()
    monkeypatch.setattr(
        pack_service, "pack_download_path", lambda pack_id, version: tmp_path / f"{pack_id}-{version}.zip"
    )

    class FakeDownload:
        def __init__(self, parent, url: str, destination: str, on_progress, on_done, on_error) -> None:
            downloads.append((parent, url, destination, on_progress, on_done, on_error))

    monkeypatch.setattr(pack_service, "Download", FakeDownload)

    download = pack_service.download_pack("parent", entry, "progress", "done", "error", "zh_TW")

    assert isinstance(download, FakeDownload)
    assert downloads[0][:3] == (
        "parent",
        "https://example.invalid/sample-zh_TW.zip",
        str(tmp_path / "fh6.sample-zh_TW-1.1.0.zip"),
    )
    assert (tmp_path).exists()


def test_pack_language_options_and_fallbacks() -> None:
    entry = make_entry()

    assert pack_service.pack_language_options(entry) == [
        ("en_US", "English"),
        ("zh_TW", "繁體中文"),
    ]
    assert pack_service.default_pack_language(entry, "zh_TW") == "zh_TW"
    assert pack_service.default_pack_language(entry, "zh_CN") == "en_US"
    assert pack_service.resolve_pack_language(entry, "zh_TW", "zh_CN") == "zh_TW"
    assert pack_service.resolve_pack_assets(entry, "zh_TW").zip_url == "https://example.invalid/sample-zh_TW.zip"
    assert pack_service.resolve_pack_assets(entry, "zh_CN", "zh_TW").zip_url == (
        "https://example.invalid/sample-zh_TW.zip"
    )
    assert pack_service.resolve_pack_assets(entry, "zh_CN", "zh_CN").zip_url == (
        "https://example.invalid/sample-en_US.zip"
    )


def test_pack_language_fallback_uses_legacy_assets() -> None:
    data = make_catalog_data()["packs"][0]
    data.pop("language_assets")
    data.pop("default_language")
    entry = PackCatalogEntry.from_dict(data)

    assert pack_service.pack_language_options(entry) == []
    assert pack_service.default_pack_language(entry, "zh_TW") == ""
    assert pack_service.resolve_pack_assets(entry, "zh_TW").zip_url == "https://example.invalid/sample.zip"


def test_pack_language_fallback_uses_default_language_and_sorted_language() -> None:
    data = make_catalog_data()["packs"][0]
    data["default_language"] = "missing"
    data["language_assets"] = {
        "zh_TW": {"zip_url": "https://example.invalid/sample-zh_TW.zip"},
        "zh_CN": {"zip_url": "https://example.invalid/sample-zh_CN.zip"},
    }
    entry = PackCatalogEntry.from_dict(data)

    assert pack_service.resolve_pack_language(entry, "", "") == "zh_CN"

    data["language_assets"]["en_US"] = {"zip_url": "https://example.invalid/sample-en_US.zip"}
    entry = PackCatalogEntry.from_dict(data)

    assert pack_service.resolve_pack_language(entry, "", "") == "en_US"


def test_resolve_pack_assets_falls_back_to_first_language_asset() -> None:
    data = make_catalog_data()["packs"][0]
    data["language_assets"] = {
        "en_US": {"zip_url": ""},
        "zh_TW": {"zip_url": "https://example.invalid/sample-zh_TW.zip"},
    }
    entry = PackCatalogEntry.from_dict(data)

    assert pack_service.resolve_pack_assets(entry, "en_US").zip_url == "https://example.invalid/sample-zh_TW.zip"


def test_resolve_pack_assets_scans_language_assets_when_resolved_asset_has_no_zip(monkeypatch) -> None:
    data = make_catalog_data()["packs"][0]
    data["language_assets"] = {
        "en_US": {"zip_url": ""},
        "zh_TW": {"zip_url": "https://example.invalid/sample-zh_TW.zip"},
    }
    entry = PackCatalogEntry.from_dict(data)
    monkeypatch.setattr(
        pack_service, "resolve_pack_language", lambda entry, selected_language, current_language: "en_US"
    )

    assert pack_service.resolve_pack_assets(entry).zip_url == "https://example.invalid/sample-zh_TW.zip"


def test_import_pack_as_macro_skips_existing_macro_order(tmp_path: Path, monkeypatch) -> None:
    archive_path = tmp_path / "pack.zip"
    fake_config = FakeConfigModel()
    fake_config.config.general.macro_order = ["macro-1"]
    model = FakeMacroModel()
    monkeypatch.setattr(pack_service, "config_model", fake_config)
    monkeypatch.setattr(
        pack_service,
        "install_macro_archive",
        lambda path, macro_model, options: type(
            "Result",
            (),
            {"macro_id": "macro-1", "label": "Sample", "template_refs": set(), "generated_new_id": False},
        )(),
    )

    result = pack_service.import_pack_as_macro(archive_path, cast(MacroModel, model))

    assert result.macro_id == "macro-1"
    assert fake_config.config.general.macro_order == ["macro-1"]
    assert fake_config.save_calls == 0


def test_import_pack_as_macro_updates_macro_order(tmp_path: Path, monkeypatch) -> None:
    archive_path = tmp_path / "pack.zip"
    fake_config = FakeConfigModel()
    model = FakeMacroModel()
    monkeypatch.setattr(pack_service, "config_model", fake_config)
    monkeypatch.setattr(
        pack_service,
        "install_macro_archive",
        lambda path, macro_model, options: type(
            "Result",
            (),
            {"macro_id": "macro-1", "label": "Sample", "template_refs": set(), "generated_new_id": False},
        )(),
    )

    result = pack_service.import_pack_as_macro(archive_path, cast(MacroModel, model))

    assert result.macro_id == "macro-1"
    assert fake_config.config.general.macro_order == ["macro-1"]
    assert fake_config.save_calls == 1
