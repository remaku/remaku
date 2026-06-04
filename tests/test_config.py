from pathlib import Path

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

    def test_general_defaults(self):
        cfg = config.get_defaults()
        assert cfg.general.always_on_top is False
        assert cfg.general.check_update_on_startup is True
        assert cfg.general.update_channel == "stable"
        assert cfg.general.theme == "system"
        assert cfg.general.language == "auto"
        assert cfg.general.macro_order == []
        assert cfg.general.overlay_enabled is True
        assert cfg.general.overlay_position == [100, 100]

    def test_capture_defaults(self):
        cfg = config.get_defaults()
        assert cfg.capture.fps == 10

    def test_input_defaults(self):
        cfg = config.get_defaults()
        assert cfg.input.jitter_ms == 60


class TestGeneralCfgPostInit:
    def test_macro_order_none_becomes_empty(self):
        cfg = config.GeneralCfg(macro_order=None)  # type: ignore[arg-type]
        assert cfg.macro_order == []

    def test_overlay_position_none_becomes_default(self):
        cfg = config.GeneralCfg(overlay_position=None)  # type: ignore[arg-type]
        assert cfg.overlay_position == [100, 100]

    def test_macro_order_preserved(self):
        cfg = config.GeneralCfg(macro_order=["a", "b"])
        assert cfg.macro_order == ["a", "b"]

    def test_overlay_position_preserved(self):
        cfg = config.GeneralCfg(overlay_position=[200, 300])
        assert cfg.overlay_position == [200, 300]


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

    def test_reads_partial_config(self, tmp_path):
        import json

        data = {"general": {"always_on_top": True}}
        (tmp_path / "config.json").write_text(json.dumps(data), encoding="utf-8")

        cfg = config.load()
        assert cfg.general.always_on_top is True
        assert cfg.general.check_update_on_startup is True  # default

    def test_ignores_unknown_keys(self, tmp_path):
        import json

        data = {"general": {"unknown_key": "value", "target_window": "Win"}}
        (tmp_path / "config.json").write_text(json.dumps(data), encoding="utf-8")

        cfg = config.load()
        assert cfg.general.target_window == "Win"

    def test_missing_sections_use_defaults(self, tmp_path):
        import json

        data = {}
        (tmp_path / "config.json").write_text(json.dumps(data), encoding="utf-8")

        cfg = config.load()
        assert cfg.general == config.get_defaults().general
        assert cfg.capture == config.get_defaults().capture
        assert cfg.input == config.get_defaults().input

    def test_returns_defaults_when_file_is_empty(self, tmp_path):
        (tmp_path / "config.json").write_text("", encoding="utf-8")

        cfg = config.load()
        assert cfg == config.get_defaults()

    def test_returns_defaults_when_file_has_invalid_json(self, tmp_path):
        (tmp_path / "config.json").write_text("{bad json!!", encoding="utf-8")

        cfg = config.load()
        assert cfg == config.get_defaults()

    def test_returns_defaults_when_file_is_whitespace_only(self, tmp_path):
        (tmp_path / "config.json").write_text("   \n\t  ", encoding="utf-8")

        cfg = config.load()
        assert cfg == config.get_defaults()

    def test_returns_defaults_on_os_error(self, tmp_path, monkeypatch):
        (tmp_path / "config.json").write_text("{}", encoding="utf-8")

        def raise_os_error(*args, **kwargs):
            raise OSError("permission denied")

        monkeypatch.setattr("pathlib.Path.read_text", raise_os_error)

        cfg = config.load()
        assert cfg == config.get_defaults()


class TestSave:
    def test_roundtrip(self):
        cfg = config.get_defaults()
        cfg.capture.fps = 30
        config.save(cfg)

        loaded = config.load()
        assert loaded.capture.fps == 30

    def test_saves_all_sections(self):
        cfg = config.get_defaults()
        cfg.general.target_window = "Test"
        cfg.general.always_on_top = True
        cfg.capture.fps = 60
        cfg.input.jitter_ms = 100
        config.save(cfg)

        loaded = config.load()
        assert loaded.general.target_window == "Test"
        assert loaded.general.always_on_top is True
        assert loaded.capture.fps == 60
        assert loaded.input.jitter_ms == 100

    def test_saves_macro_order(self):
        cfg = config.get_defaults()
        cfg.general.macro_order = ["b", "a", "c"]
        config.save(cfg)

        loaded = config.load()
        assert loaded.general.macro_order == ["b", "a", "c"]

    def test_saves_overlay_position(self):
        cfg = config.get_defaults()
        cfg.general.overlay_position = [500, 400]
        config.save(cfg)

        loaded = config.load()
        assert loaded.general.overlay_position == [500, 400]


class TestGetDocumentsDir:
    def test_returns_path(self, monkeypatch):
        monkeypatch.undo()
        result = config.get_documents_dir()
        assert isinstance(result, Path)

    def test_fallback_on_exception(self, monkeypatch):
        monkeypatch.undo()
        monkeypatch.setattr("config.ctypes.windll", None)
        result = config.get_documents_dir()
        assert result == Path.home() / "Documents"

    def test_fallback_on_nonzero_result(self, monkeypatch):
        monkeypatch.undo()

        mock_shell = type("Shell", (), {"SHGetFolderPathW": lambda *a: 1})()
        monkeypatch.setattr("config.ctypes.windll.shell32", mock_shell)
        result = config.get_documents_dir()
        assert result == Path.home() / "Documents"


class TestUserDataDir:
    def test_creates_directory(self, tmp_path, monkeypatch):
        monkeypatch.undo()
        monkeypatch.setattr(config, "get_documents_dir", lambda: tmp_path)
        result = config.user_data_dir()
        assert result == tmp_path / "remaku"
        assert result.exists()

    def test_creates_parent_dirs(self, tmp_path, monkeypatch):
        monkeypatch.undo()
        nested = tmp_path / "a" / "b"
        monkeypatch.setattr(config, "get_documents_dir", lambda: nested)
        result = config.user_data_dir()
        assert result == nested / "remaku"
        assert result.exists()


class TestConfigPath:
    def test_returns_json_path(self, tmp_path, monkeypatch):
        monkeypatch.undo()
        monkeypatch.setattr(config, "get_documents_dir", lambda: tmp_path)
        result = config.config_path()
        assert result == tmp_path / "remaku" / "config.json"


class TestTemplatesDir:
    def test_returns_base_dir(self, tmp_path, monkeypatch):
        monkeypatch.undo()
        monkeypatch.setattr(config, "get_documents_dir", lambda: tmp_path)
        result = config.templates_dir()
        assert result == tmp_path / "remaku" / "templates"
        assert result.exists()

    def test_creates_macro_subdir(self, tmp_path, monkeypatch):
        monkeypatch.undo()
        monkeypatch.setattr(config, "get_documents_dir", lambda: tmp_path)
        result = config.templates_dir("my_macro")
        assert result == tmp_path / "remaku" / "templates" / "my_macro"
        assert result.exists()

    def test_empty_name_returns_base(self, tmp_path, monkeypatch):
        monkeypatch.undo()
        monkeypatch.setattr(config, "get_documents_dir", lambda: tmp_path)
        result = config.templates_dir("")
        assert result == tmp_path / "remaku" / "templates"


class TestMacrosDir:
    def test_creates_directory(self, tmp_path, monkeypatch):
        monkeypatch.undo()
        monkeypatch.setattr(config, "get_documents_dir", lambda: tmp_path)
        result = config.macros_dir()
        assert result == tmp_path / "remaku" / "macros"
        assert result.exists()


class TestLogsDir:
    def test_creates_directory(self, tmp_path, monkeypatch):
        monkeypatch.undo()
        monkeypatch.setattr(config, "get_documents_dir", lambda: tmp_path)
        result = config.logs_dir()
        assert result == tmp_path / "remaku" / "logs"
        assert result.exists()
