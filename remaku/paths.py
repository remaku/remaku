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


def macro_path(macro_name: str) -> Path:
    return macros_dir() / f"{macro_name}.json"


def templates_dir(macro_name: str = "") -> Path:
    base_dir = data_dir() / "templates"

    if macro_name:
        return base_dir / macro_name

    return base_dir


def template_path(macro_name: str, template_id: str) -> Path:
    return templates_dir(macro_name) / f"{template_id}.png"
