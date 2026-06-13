from dataclasses import dataclass
from typing import Any, cast

from PySide6.QtCore import QObject, Signal

from remaku.controllers import pack_explorer_controller
from remaku.controllers.pack_explorer_controller import PackExplorerController
from remaku.models.config_model import config_model
from remaku.models.pack_model import PackCatalog


class FakeView(QObject):
    pack_selected = Signal(str)
    import_requested = Signal(str)
    search_changed = Signal(str)
    game_filter_changed = Signal(str)
    compatibility_filter_changed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.current_pack_id = ""
        self.loading_calls = 0
        self.statuses: list[str] = []
        self.importing_states: list[bool] = []
        self.items = []
        self.selected = None
        self.filter_options: list[tuple[str, str]] | None = None

    def set_loading(self) -> None:
        self.loading_calls += 1

    def set_status_text(self, text: str) -> None:
        self.statuses.append(text)

    def set_importing(self, importing: bool) -> None:
        self.importing_states.append(importing)

    def set_pack_items(self, items, selected_pack_id: str = "") -> None:
        self.items = items
        self.current_pack_id = selected_pack_id

    def set_filter_options(self, games: list[tuple[str, str]]) -> None:
        self.filter_options = games

    def set_selected_pack(self, item) -> None:
        self.selected = item

    def window(self):
        return self


@dataclass
class FakeDownload:
    on_done: Any | None = None
    started: bool = False

    def start(self) -> None:
        self.started = True

    def finish(self, path: str) -> None:
        if self.on_done is not None:
            self.on_done(path)


def make_catalog() -> PackCatalog:
    return PackCatalog.from_dict(
        {
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
                    "version": "1.0.0",
                    "release_tag": "v2",
                    "assets": {"zip_url": "https://example.invalid/sample.zip"},
                }
            ],
        }
    )


def make_controller(monkeypatch) -> tuple[PackExplorerController, FakeView]:
    view = FakeView()

    def fetch_catalog_async(parent, on_done, on_error) -> None:
        on_done(make_catalog())

    monkeypatch.setattr(pack_explorer_controller.pack_service, "fetch_catalog_async", fetch_catalog_async)
    controller = PackExplorerController(cast(Any, view), cast(Any, object()))
    return controller, view


def test_ensure_loaded_fetches_catalog_once(monkeypatch) -> None:
    controller, view = make_controller(monkeypatch)

    controller.ensure_loaded()
    controller.ensure_loaded()

    assert view.loading_calls == 1
    assert len(controller.items) == 1
    assert view.items[0].entry.pack_id == "fh6.sample"
    assert view.filter_options == [("fh6", "Forza Horizon 6")]


def test_refresh_reports_catalog_error(monkeypatch) -> None:
    view = FakeView()

    def fetch_catalog_async(parent, on_done, on_error) -> None:
        on_error("bad")

    monkeypatch.setattr(pack_explorer_controller.pack_service, "fetch_catalog_async", fetch_catalog_async)

    controller = PackExplorerController(cast(Any, view), cast(Any, object()))
    controller.ensure_loaded()

    assert view.statuses == ["bad"]
    assert view.items == []


def test_ensure_loaded_does_not_start_duplicate_catalog_load(monkeypatch) -> None:
    view = FakeView()
    calls = []

    def fetch_catalog_async(parent, on_done, on_error) -> None:
        calls.append(parent)

    monkeypatch.setattr(pack_explorer_controller.pack_service, "fetch_catalog_async", fetch_catalog_async)

    controller = PackExplorerController(cast(Any, view), cast(Any, object()))
    controller.ensure_loaded()
    controller.ensure_loaded()

    assert calls == [view]
    assert view.loading_calls == 1


def test_filter_packs_uses_search_text(monkeypatch) -> None:
    controller, view = make_controller(monkeypatch)
    controller.ensure_loaded()

    controller.filter_packs("missing")

    assert view.items == []

    controller.filter_packs("v2")

    assert len(view.items) == 1


def test_filters_by_game_and_compatibility(monkeypatch) -> None:
    controller, view = make_controller(monkeypatch)
    controller.ensure_loaded()

    controller.filter_by_game("missing")

    assert view.items == []

    controller.filter_by_game("fh6")
    controller.filter_by_compatibility("compatible")

    assert len(view.items) == 1

    controller.items[0].status = "incompatible"
    controller.filter_by_compatibility("incompatible")

    assert len(view.items) == 1


def test_handle_pack_selected_updates_view(monkeypatch) -> None:
    controller, view = make_controller(monkeypatch)
    controller.ensure_loaded()

    controller.handle_pack_selected("fh6.sample")

    assert view.selected is not None
    assert view.selected.entry.pack_id == "fh6.sample"


def test_start_download_starts_download(monkeypatch) -> None:
    controller, view = make_controller(monkeypatch)
    controller.ensure_loaded()
    fake_download = FakeDownload()
    monkeypatch.setattr(
        pack_explorer_controller.pack_service,
        "download_pack",
        lambda parent, entry, on_progress, on_done, on_error: fake_download,
    )

    controller.import_pack("fh6.sample")

    assert fake_download.started is True
    assert view.importing_states == [True]


def test_import_pack_shows_imported_status_after_refresh(monkeypatch, tmp_path) -> None:
    config_model.config.general.language = "en_US"
    controller, view = make_controller(monkeypatch)
    controller.ensure_loaded()
    fake_download = FakeDownload()

    def download_pack(parent, entry, on_progress, on_done, on_error):
        fake_download.on_done = on_done
        return fake_download

    monkeypatch.setattr(pack_explorer_controller.pack_service, "download_pack", download_pack)
    monkeypatch.setattr(pack_explorer_controller.pack_service, "import_pack_as_macro", lambda path, model: object())

    controller.import_pack("fh6.sample")
    fake_download.finish(str(tmp_path / "sample.zip"))

    assert view.importing_states == [True, False]
    assert view.statuses[-1] == "Imported macro: Sample Pack"


def test_incompatible_pack_does_not_download(monkeypatch) -> None:
    controller, _view = make_controller(monkeypatch)
    controller.ensure_loaded()
    controller.items[0].status = "incompatible"
    calls = []
    monkeypatch.setattr(
        pack_explorer_controller.pack_service,
        "download_pack",
        lambda parent, entry, on_progress, on_done, on_error: calls.append(entry.pack_id),
    )

    controller.import_pack("fh6.sample")

    assert calls == []
