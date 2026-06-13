import pytest

from remaku.models.pack_model import PackAssets, PackCatalog, PackCatalogEntry, PackCompatibility, PackGame, PackSource


def make_pack_data() -> dict:
    return {
        "pack_id": "fh6.sample",
        "game": "fh6",
        "label": {"en_US": "Sample Pack", "zh_TW": "範例套件", "zh_CN": "示例套件"},
        "description": {"en_US": "Sample description", "zh_TW": "範例描述", "zh_CN": "示例描述"},
        "author": "Remaku",
        "version": "1.0.0",
        "release_tag": "v2",
        "source": {"repo_path": "packs/fh6/sample", "macro_json_path": "packs/fh6/sample/macro.json"},
        "assets": {"zip_url": "https://example.invalid/sample.zip", "preview_image_url": ""},
        "compatibility": {"remaku_min": "0.5.0", "remaku_max": ""},
    }


def test_pack_catalog_from_dict_parses_games_and_entries() -> None:
    catalog = PackCatalog.from_dict(
        {
            "schema_version": 1,
            "repo_url": "https://github.com/remaku/remaku-packs",
            "games": [{"id": "fh6", "label": "Forza Horizon 6"}],
            "packs": [make_pack_data()],
        }
    )

    assert catalog.schema_version == 1
    assert catalog.games[0].id == "fh6"
    assert catalog.games[0].display_label() == "Forza Horizon 6"
    assert catalog.packs[0].pack_id == "fh6.sample"
    assert catalog.packs[0].display_label("en_US") == "Sample Pack"
    assert catalog.packs[0].display_label("zh_TW") == "範例套件"
    assert catalog.packs[0].display_description("zh_CN") == "示例描述"
    assert catalog.packs[0].release_tag == "v2"
    assert catalog.packs[0].assets.zip_url == "https://example.invalid/sample.zip"


def test_pack_catalog_accepts_legacy_string_text() -> None:
    data = make_pack_data()
    data["label"] = "Legacy Label"
    data["description"] = "Legacy description"

    entry = PackCatalogEntry.from_dict(data)

    assert entry.display_label("zh_TW") == "Legacy Label"
    assert entry.display_description("zh_CN") == "Legacy description"


def test_pack_catalog_rejects_unsupported_schema() -> None:
    with pytest.raises(ValueError, match="Unsupported pack catalog schema"):
        PackCatalog.from_dict({"schema_version": 2, "repo_url": "https://example.invalid", "packs": []})


def test_pack_entry_requires_core_fields() -> None:
    data = make_pack_data()
    data["assets"] = {}

    with pytest.raises(ValueError, match=r"assets\.zip_url"):
        PackCatalogEntry.from_dict(data)


def test_pack_value_objects_serialize_defaults_and_labels() -> None:
    assert PackCompatibility.from_dict({}).to_dict() == {"remaku_min": "", "remaku_max": ""}
    assert PackAssets.from_dict({}).to_dict() == {"zip_url": "", "preview_image_url": ""}
    assert PackSource.from_dict({}).to_dict() == {"repo_path": "", "macro_json_path": ""}
    assert PackGame.from_dict({"id": "fh6"}).display_label() == "fh6"


def test_pack_game_requires_id() -> None:
    with pytest.raises(ValueError, match="Game id is required"):
        PackGame.from_dict({"label": "Missing id"})


def test_pack_entry_ignores_invalid_nested_objects() -> None:
    data = make_pack_data()
    data["assets"] = "invalid"
    data["source"] = "invalid"
    data["compatibility"] = "invalid"

    with pytest.raises(ValueError, match=r"assets\.zip_url"):
        PackCatalogEntry.from_dict(data)


def test_pack_entry_to_dict_includes_nested_data() -> None:
    entry = PackCatalogEntry.from_dict(make_pack_data())

    assert entry.to_dict()["source"] == {
        "repo_path": "packs/fh6/sample",
        "macro_json_path": "packs/fh6/sample/macro.json",
    }
    assert entry.to_dict()["compatibility"] == {"remaku_min": "0.5.0", "remaku_max": ""}


def test_pack_catalog_rejects_invalid_collections_and_missing_repo_url() -> None:
    with pytest.raises(ValueError, match="Pack catalog games must be a list"):
        PackCatalog.from_dict({"schema_version": 1, "repo_url": "https://example.invalid", "games": {}})

    with pytest.raises(ValueError, match="Pack catalog packs must be a list"):
        PackCatalog.from_dict({"schema_version": 1, "repo_url": "https://example.invalid", "packs": {}})

    with pytest.raises(ValueError, match="Pack catalog repo_url is required"):
        PackCatalog.from_dict({"schema_version": 1, "repo_url": "", "packs": []})


def test_pack_catalog_to_dict_skips_non_dict_items() -> None:
    catalog = PackCatalog.from_dict(
        {
            "schema_version": 1,
            "repo_url": "https://github.com/remaku/remaku-packs",
            "games": ["skip", {"id": "fh6", "label": "Forza Horizon 6"}],
            "packs": ["skip", make_pack_data()],
        }
    )

    assert catalog.to_dict()["games"] == [{"id": "fh6", "label": "Forza Horizon 6"}]
    assert catalog.to_dict()["packs"][0]["pack_id"] == "fh6.sample"
