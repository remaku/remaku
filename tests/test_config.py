import pytest

import config


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    """Isolate all config tests to a temporary directory."""
    monkeypatch.setattr(config, "user_data_dir", lambda: tmp_path)
    monkeypatch.setattr(config, "config_path", lambda: tmp_path / "config.json")


class TestGetDefaults:
    def test_returns_config(self):
        cfg = config.get_defaults()
        assert isinstance(cfg, config.Config)
        assert cfg.general.target_window == ""


class TestLoad:
    def test_returns_defaults_when_no_file(self):
        cfg = config.load()
        assert cfg.general.target_window == ""

    def test_reads_custom_values(self, tmp_path):
        import json

        data = {"general": {"target_window": "Notepad"}, "capture": {"fps": 30}}
        (tmp_path / "config.json").write_text(json.dumps(data), encoding="utf-8")

        cfg = config.load()
        assert cfg.general.target_window == "Notepad"
        assert cfg.capture.fps == 30


class TestSave:
    def test_roundtrip(self):
        cfg = config.get_defaults()
        cfg.capture.fps = 30
        config.save(cfg)

        loaded = config.load()
        assert loaded.capture.fps == 30
