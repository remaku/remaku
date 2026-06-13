import sys
from pathlib import Path

from platformdirs import user_documents_dir


def root_dir():
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)  # type: ignore
    else:
        return Path(__file__).parent.parent


def data_dir():
    return Path(user_documents_dir()) / "remaku"


def log_dir() -> Path:
    return data_dir() / "logs"


def macros_dir() -> Path:
    return data_dir() / "macros"


def macro_path(macro_id: str) -> Path:
    return macros_dir() / f"{macro_id}.json"


def templates_dir(macro_id: str = "") -> Path:
    base_dir = data_dir() / "templates"

    if macro_id:
        return base_dir / macro_id

    return base_dir


def template_path(macro_id: str, template_id: str) -> Path:
    return templates_dir(macro_id) / f"{template_id}.png"


def pack_cache_dir() -> Path:
    return data_dir() / "pack-cache"


def safe_pack_filename(value: str) -> str:
    safe_value = "".join(char if char.isalnum() or char in ".-_" else "_" for char in value)
    return safe_value or "pack"


def pack_download_path(pack_id: str, version: str) -> Path:
    filename = f"{safe_pack_filename(pack_id)}-{safe_pack_filename(version)}.zip"
    return pack_cache_dir() / filename
