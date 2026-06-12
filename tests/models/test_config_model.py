import json

from remaku.models.config_model import DEFAULT_OVERLAY_POSITION, AppConfig, ConfigModel


def test_app_config_from_dict_merges_defaults_and_coerces_values() -> None:
    config = AppConfig.from_dict(
        {
            "general": {
                "always_on_top": 1,
                "macro_order": ["alpha", 123, "beta"],
                "overlay_position": [12, "34"],
            },
            "capture": {"fps": "30"},
            "input": {"jitter_ms": "75"},
        }
    )

    assert config.general.always_on_top is True
    assert config.general.macro_order == ["alpha", "beta"]
    assert config.general.overlay_position == (12, 34)
    assert config.capture.fps == 30
    assert config.input.jitter_ms == 75


def test_app_config_from_dict_uses_default_overlay_position_for_bad_shape() -> None:
    config = AppConfig.from_dict({"general": {"overlay_position": [1, 2, 3]}})

    assert config.general.overlay_position == DEFAULT_OVERLAY_POSITION


def test_config_model_creates_default_config(isolated_data_dir) -> None:
    model = ConfigModel()

    assert model.config_path == isolated_data_dir / "config.json"
    assert model.config_path.exists()
    assert json.loads(model.config_path.read_text(encoding="utf-8"))["general"]["overlay_enabled"] is True


def test_config_model_merges_missing_defaults(isolated_data_dir) -> None:
    config_path = isolated_data_dir / "config.json"
    config_path.write_text(json.dumps({"general": {"theme": "dark"}}), encoding="utf-8")

    model = ConfigModel()

    assert model.config.general.theme == "dark"
    assert model.config.capture.fps == 10
    assert "capture" in json.loads(config_path.read_text(encoding="utf-8"))


def test_config_model_recovers_from_invalid_json(isolated_data_dir) -> None:
    config_path = isolated_data_dir / "config.json"
    config_path.write_text("not json", encoding="utf-8")

    model = ConfigModel()

    assert model.config.general.theme == "system"
    assert json.loads(config_path.read_text(encoding="utf-8"))["general"]["theme"] == "system"


def test_config_model_recovers_from_non_dict_json(isolated_data_dir) -> None:
    config_path = isolated_data_dir / "config.json"
    config_path.write_text("[]", encoding="utf-8")

    model = ConfigModel()

    assert model.config.general.theme == "system"
    assert json.loads(config_path.read_text(encoding="utf-8"))["general"]["theme"] == "system"
