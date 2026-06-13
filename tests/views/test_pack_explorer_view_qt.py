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
            "assets": {"zip_url": "https://example.invalid/sample.zip"},
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
    assert view.import_button.isEnabled() is True


def test_pack_explorer_view_disables_import_for_incompatible_pack(qtbot) -> None:
    view = PackExplorerView()
    qtbot.addWidget(view)
    item = make_item("incompatible")

    view.set_selected_pack(item)

    assert view.import_button.isEnabled() is False


def test_pack_explorer_view_uses_selected_language(qtbot) -> None:
    config_model.config.general.language = "zh_TW"
    view = PackExplorerView()
    qtbot.addWidget(view)

    view.set_selected_pack(make_item())

    assert view.name_label.text() == "範例套件"
    assert view.description_label.text() == "範例描述"


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
