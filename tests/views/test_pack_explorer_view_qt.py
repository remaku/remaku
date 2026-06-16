from PySide6.QtCore import Qt

from remaku.models.config_model import config_model
from remaku.models.pack_model import PackCatalogEntry, PackListItem, PackStatus
from remaku.views.pack_explorer_view import PackExplorerView


def make_item(status: PackStatus = "available") -> PackListItem:
    entry = PackCatalogEntry.from_dict(
        {
            "pack_id": "fh6.sample",
            "game": "fh6",
            "label": {"en_US": "Sample Pack", "zh_TW": "範例套件", "zh_CN": "示例套件"},
            "description": {"en_US": "Sample description", "zh_TW": "範例描述", "zh_CN": "示例描述"},
            "author": "Remaku",
            "version": "1.0.0",
            "release_tag": "v2",
            "default_language": "en_US",
            "assets": {"zip_url": "https://example.invalid/sample.zip"},
            "language_assets": {
                "en_US": {"zip_url": "https://example.invalid/sample-en_US.zip"},
                "zh_TW": {"zip_url": "https://example.invalid/sample-zh_TW.zip"},
            },
        }
    )
    return PackListItem(entry=entry, status=status, game_label="Forza Horizon 6")


def test_pack_explorer_view_sets_pack_list(qtbot) -> None:
    config_model.config.general.language = "en_US"
    view = PackExplorerView()
    qtbot.addWidget(view)

    view.set_pack_items([make_item()])

    assert view.pack_list.count() == 1
    assert view.pack_list.item(0).text() == "Sample Pack"
    assert view.empty_label.isHidden()


def test_pack_explorer_view_sets_loading_status(qtbot) -> None:
    view = PackExplorerView()
    qtbot.addWidget(view)

    view.set_loading()

    assert view.status_label.text() == "Loading packs..."
    assert not view.status_label.isHidden()


def test_pack_explorer_view_updates_detail_and_buttons(qtbot) -> None:
    config_model.config.general.language = "en_US"
    view = PackExplorerView()
    qtbot.addWidget(view)
    item = make_item("available")

    view.set_selected_pack(item)

    assert view.current_pack_id == "fh6.sample"
    assert view.name_label.text() == "Sample Pack"
    assert "version" not in view.info_labels
    assert view.info_labels["game"].text() == "Forza Horizon 6"
    assert view.info_labels["compatibility"].text() == "Compatible"
    assert view.language_combo.currentData() == "en_US"
    assert view.import_button.isEnabled() is True


def test_pack_explorer_view_disables_import_for_incompatible_pack(qtbot) -> None:
    view = PackExplorerView()
    qtbot.addWidget(view)
    item = make_item("incompatible")

    view.set_selected_pack(item)

    assert view.import_button.isEnabled() is False


def test_pack_explorer_view_disables_import_while_importing(qtbot) -> None:
    view = PackExplorerView()
    qtbot.addWidget(view)

    view.set_selected_pack(make_item())
    view.set_importing(True)

    assert view.import_button.isEnabled() is False

    view.set_importing(False)

    assert view.import_button.isEnabled() is True


def test_pack_explorer_view_language_combo_defaults_to_current_language(qtbot) -> None:
    config_model.config.general.language = "zh_TW"
    view = PackExplorerView()
    qtbot.addWidget(view)

    view.set_selected_pack(make_item())

    assert not view.language_combo.isHidden()
    assert view.language_combo.currentData() == "zh_TW"


def test_pack_explorer_view_language_combo_falls_back_to_default_language(qtbot) -> None:
    config_model.config.general.language = "zh_CN"
    view = PackExplorerView()
    qtbot.addWidget(view)

    view.set_selected_pack(make_item())

    assert view.language_combo.currentData() == "en_US"


def test_pack_explorer_view_preserves_language_when_same_pack_refreshes(qtbot) -> None:
    config_model.config.general.language = "zh_TW"
    view = PackExplorerView()
    qtbot.addWidget(view)
    item = make_item()

    view.set_selected_pack(item)
    view.language_combo.setCurrentIndex(view.language_combo.findData("en_US"))
    view.set_selected_pack(item)

    assert view.language_combo.currentData() == "en_US"
    assert view.current_pack_language == "en_US"


def test_pack_explorer_view_preserves_language_when_pack_changes(qtbot) -> None:
    config_model.config.general.language = "zh_TW"
    view = PackExplorerView()
    qtbot.addWidget(view)
    first_item = make_item()
    second_item = make_item()
    second_item.entry.pack_id = "fh6.other"

    view.set_selected_pack(first_item)
    view.language_combo.setCurrentIndex(view.language_combo.findData("en_US"))
    view.set_selected_pack(second_item)

    assert view.language_combo.currentData() == "en_US"


def test_pack_explorer_view_preserves_language_after_pack_list_refresh(qtbot) -> None:
    config_model.config.general.language = "zh_TW"
    view = PackExplorerView()
    qtbot.addWidget(view)
    item = make_item()
    view.pack_selected.connect(lambda _pack_id: view.set_selected_pack(item))

    view.set_pack_items([item])
    view.language_combo.setCurrentIndex(view.language_combo.findData("en_US"))
    view.set_pack_items([item], selected_pack_id="fh6.sample")

    assert view.language_combo.currentData() == "en_US"
    assert view.current_pack_language == "en_US"


def test_pack_explorer_view_hides_language_combo_for_legacy_pack(qtbot) -> None:
    view = PackExplorerView()
    qtbot.addWidget(view)
    item = make_item()
    item.entry.default_language = ""
    item.entry.language_assets = {}

    view.set_selected_pack(item)

    assert view.language_combo.isHidden()
    assert view.current_pack_language == ""


def test_pack_explorer_view_import_emits_selected_language(qtbot) -> None:
    config_model.config.general.language = "en_US"
    view = PackExplorerView()
    qtbot.addWidget(view)
    view.set_selected_pack(make_item())
    view.language_combo.setCurrentIndex(view.language_combo.findData("zh_TW"))

    with qtbot.waitSignal(view.import_requested) as blocker:
        view.import_button.click()

    assert blocker.args == ["fh6.sample", "zh_TW"]


def test_pack_explorer_view_uses_selected_language(qtbot) -> None:
    config_model.config.general.language = "zh_TW"
    view = PackExplorerView()
    qtbot.addWidget(view)

    view.set_selected_pack(make_item())

    assert view.name_label.text() == "範例套件"
    assert view.description_label.text() == "範例描述"


def test_pack_explorer_view_keeps_status_separate_from_description(qtbot) -> None:
    config_model.config.general.language = "en_US"
    view = PackExplorerView()
    qtbot.addWidget(view)

    view.set_selected_pack(make_item())
    view.set_status_text("Downloading pack...")

    assert view.description_label.text() == "Sample description"
    assert view.status_label.text() == "Downloading pack..."
    assert not view.status_label.isHidden()


def test_pack_explorer_view_shows_loading_status(qtbot) -> None:
    view = PackExplorerView()
    qtbot.addWidget(view)

    view.set_loading()

    assert view.status_label.text() == "Loading packs..."
    assert not view.status_label.isHidden()


def test_pack_explorer_view_emits_selection(qtbot) -> None:
    view = PackExplorerView()
    qtbot.addWidget(view)
    view.set_pack_items([make_item()])

    view.pack_list.clearSelection()

    with qtbot.waitSignal(view.pack_selected) as blocker:
        view.pack_list.setCurrentRow(0)

    assert blocker.args == ["fh6.sample"]


def test_pack_explorer_view_clears_empty_detail(qtbot) -> None:
    view = PackExplorerView()
    qtbot.addWidget(view)

    view.set_pack_items([])

    assert view.pack_list.isHidden()
    assert not view.empty_label.isHidden()
    assert view.current_pack_id == ""
    assert view.import_button.isEnabled() is False


def test_pack_explorer_view_selects_requested_pack_and_labels_incompatible(qtbot) -> None:
    config_model.config.general.language = "en_US"
    view = PackExplorerView()
    qtbot.addWidget(view)
    available_item = make_item("available")
    incompatible_item = make_item("incompatible")
    incompatible_item.entry.pack_id = "fh6.incompatible"

    view.set_pack_items([available_item, incompatible_item], selected_pack_id="fh6.incompatible")

    assert view.pack_list.currentItem().data(Qt.ItemDataRole.UserRole) == "fh6.incompatible"
    assert view.pack_list.item(1).text() == "Sample Pack (Incompatible)"


def test_pack_explorer_view_resets_missing_filter_to_all(qtbot) -> None:
    view = PackExplorerView()
    qtbot.addWidget(view)

    view.update_filter(view.game_filter, "All games", [("fh6", "Forza Horizon 6")])
    view.game_filter.setCurrentIndex(view.game_filter.findData("fh6"))
    view.update_filter(view.game_filter, "All games", [])

    assert view.current_filter_value(view.game_filter) == "all"


def test_pack_explorer_view_emits_filter_changes(qtbot) -> None:
    view = PackExplorerView()
    qtbot.addWidget(view)
    view.set_filter_options([("fh6", "Forza Horizon 6")])

    with qtbot.waitSignal(view.game_filter_changed) as game_blocker:
        view.game_filter.setCurrentIndex(view.game_filter.findData("fh6"))

    with qtbot.waitSignal(view.compatibility_filter_changed) as compatibility_blocker:
        view.compatibility_filter.setCurrentIndex(view.compatibility_filter.findData("incompatible"))

    assert game_blocker.args == ["fh6"]
    assert compatibility_blocker.args == ["incompatible"]


def test_pack_explorer_view_ignores_empty_selection(qtbot) -> None:
    view = PackExplorerView()
    qtbot.addWidget(view)
    emissions = []
    view.pack_selected.connect(emissions.append)

    view.handle_selection_changed()

    assert emissions == []


def test_pack_explorer_view_clears_selected_pack_none(qtbot) -> None:
    view = PackExplorerView()
    qtbot.addWidget(view)
    view.set_selected_pack(make_item())

    view.set_selected_pack(None)

    assert view.current_pack_id == ""
    assert view.name_label.text() == "Select a pack"


def test_pack_explorer_view_formats_compatibility_ranges(qtbot) -> None:
    view = PackExplorerView()
    qtbot.addWidget(view)
    item = make_item()

    item.entry.compatibility.remaku_min = "1.0.0"
    item.entry.compatibility.remaku_max = "2.0.0"
    assert view.compatibility_text(item.entry) == "Requires Remaku 1.0.0 to 2.0.0"

    item.entry.compatibility.remaku_max = ""
    assert view.compatibility_text(item.entry) == "Requires Remaku 1.0.0 or newer"

    item.entry.compatibility.remaku_min = ""
    item.entry.compatibility.remaku_max = "2.0.0"
    assert view.compatibility_text(item.entry) == "Requires Remaku 2.0.0 or older"
