from pathlib import Path

from remaku import paths


def test_root_dir_uses_meipass_when_frozen(monkeypatch) -> None:
    monkeypatch.setattr(paths.sys, "frozen", True, raising=False)
    monkeypatch.setattr(paths.sys, "_MEIPASS", "C:/bundle/root", raising=False)

    assert paths.root_dir() == Path("C:/bundle/root")


def test_path_helpers_build_data_paths(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(paths, "user_documents_dir", lambda: str(tmp_path))

    assert paths.data_dir() == tmp_path / "remaku"
    assert paths.log_dir() == tmp_path / "remaku" / "logs"
    assert paths.macros_dir() == tmp_path / "remaku" / "macros"
    assert paths.macro_path("daily") == tmp_path / "remaku" / "macros" / "daily.json"
    assert paths.templates_dir() == tmp_path / "remaku" / "templates"
    assert paths.templates_dir("daily") == tmp_path / "remaku" / "templates" / "daily"
    assert paths.template_path("daily", "button") == tmp_path / "remaku" / "templates" / "daily" / "button.png"
    assert paths.pack_cache_dir() == tmp_path / "remaku" / "pack-cache"
    assert paths.safe_pack_filename("bad/name:*") == "bad_name__"
    assert paths.safe_pack_filename("") == "pack"
    assert paths.pack_download_path("bad/name", "1:0") == tmp_path / "remaku" / "pack-cache" / "bad_name-1_0.zip"
