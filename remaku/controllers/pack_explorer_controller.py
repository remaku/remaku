from pathlib import Path

from PySide6.QtCore import QObject

from remaku.core.dialogs import show_message_dialog
from remaku.core.event_bus import event_bus
from remaku.models.config_model import config_model
from remaku.models.macro_model import MacroModel
from remaku.models.pack_model import PackCatalog, PackListItem
from remaku.services import pack_service
from remaku.views.pack_explorer_view import PackExplorerView


class PackExplorerController(QObject):
    def __init__(self, view: PackExplorerView, macro_model: MacroModel):
        super().__init__(view)

        self.view = view
        self.macro_model = macro_model
        self.catalog: PackCatalog | None = None
        self.items: list[PackListItem] = []
        self.filtered_items: list[PackListItem] = []
        self.current_search = ""
        self.current_game_filter = "all"
        self.current_compatibility_filter = "all"
        self.current_download = None
        self.pending_status_text = ""
        self.loaded = False
        self.loading = False

        self.view.pack_selected.connect(self.handle_pack_selected)
        self.view.import_requested.connect(self.import_pack)
        self.view.search_changed.connect(self.filter_packs)
        self.view.game_filter_changed.connect(self.filter_by_game)
        self.view.compatibility_filter_changed.connect(self.filter_by_compatibility)

    def ensure_loaded(self) -> None:
        if self.loaded or self.loading:
            return

        self.refresh()

    def refresh(self) -> None:
        self.view.set_loading()
        self.loading = True

        pack_service.fetch_catalog_async(self.view, self.handle_catalog_loaded, self.handle_catalog_error)

    def handle_catalog_loaded(self, catalog: PackCatalog) -> None:
        self.catalog = catalog
        self.items = pack_service.build_pack_items(catalog)
        self.loaded = True
        self.loading = False
        self.update_filter_options()
        self.filter_packs(self.current_search)
        self.show_pending_status()

    def handle_catalog_error(self, error: str) -> None:
        self.catalog = None
        self.items = []
        self.filtered_items = []
        self.view.set_pack_items([])
        self.view.set_status_text(error)
        self.loaded = True
        self.loading = False

    def update_filter_options(self) -> None:
        games = [(game.id, game.display_label()) for game in self.catalog.games] if self.catalog is not None else []
        self.view.set_filter_options(games)

    def filter_by_game(self, value: str) -> None:
        self.current_game_filter = value
        self.apply_filters()

    def filter_by_compatibility(self, value: str) -> None:
        self.current_compatibility_filter = value
        self.apply_filters()

    def filter_packs(self, text: str) -> None:
        self.current_search = text.strip().lower()
        self.apply_filters()

    def apply_filters(self) -> None:
        self.filtered_items = [item for item in self.items if self.matches_filters(item)]

        selected_pack_id = self.view.current_pack_id
        self.view.set_pack_items(self.filtered_items, selected_pack_id)

    def matches_filters(self, item: PackListItem) -> bool:
        if self.current_game_filter != "all" and item.entry.game != self.current_game_filter:
            return False

        if self.current_compatibility_filter == "compatible" and item.status == "incompatible":
            return False

        if self.current_compatibility_filter == "incompatible" and item.status != "incompatible":
            return False

        return not self.current_search or self.matches_search(item, self.current_search)

    def pack_label(self, item: PackListItem) -> str:
        return item.entry.display_label(config_model.config.general.language)

    def pack_description(self, item: PackListItem) -> str:
        return item.entry.display_description(config_model.config.general.language)

    def matches_search(self, item: PackListItem, text: str) -> bool:
        entry = item.entry
        values = [
            entry.pack_id,
            entry.game,
            item.game_label,
            self.pack_label(item),
            self.pack_description(item),
            entry.release_tag,
        ]
        return any(text in value.lower() for value in values)

    def find_item(self, pack_id: str) -> PackListItem | None:
        for item in self.items:
            if item.entry.pack_id == pack_id:
                return item

        return None

    def handle_pack_selected(self, pack_id: str) -> None:
        self.view.set_selected_pack(self.find_item(pack_id))

    def show_pending_status(self) -> None:
        if not self.pending_status_text:
            return

        self.view.set_status_text(self.pending_status_text)
        self.pending_status_text = ""

    def import_pack(self, pack_id: str) -> None:
        item = self.find_item(pack_id)
        if item is None or item.status == "incompatible":
            return

        self.start_download(item)

    def start_download(self, item: PackListItem) -> None:
        self.view.set_importing(True)
        self.view.set_status_text(self.tr("Downloading pack..."))

        def on_progress(downloaded: int, total: int) -> None:
            if total > 0:
                percent = int(downloaded / total * 100)
                self.view.set_status_text(self.tr("Downloading pack... {percent}%").format(percent=percent))
            else:
                self.view.set_status_text(self.tr("Downloading pack..."))

        def on_done(path: str) -> None:
            try:
                pack_service.import_pack_as_macro(Path(path), self.macro_model)
                self.pending_status_text = self.tr("Imported macro: {name}").format(name=self.pack_label(item))
            except ValueError as error:
                show_message_dialog(self.view.window(), self.tr("Pack import failed"), str(error))
                self.view.set_importing(False)
                self.view.set_status_text(str(error))
                return

            self.view.set_importing(False)
            event_bus.macros_changed.emit()
            self.refresh()

        def on_error(error: str) -> None:
            show_message_dialog(self.view.window(), self.tr("Pack download failed"), error)
            self.view.set_importing(False)
            self.view.set_status_text(error)

        self.current_download = pack_service.download_pack(self.view, item.entry, on_progress, on_done, on_error)
        self.current_download.start()
