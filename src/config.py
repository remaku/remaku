"""Application configuration module.

Handles loading, saving, and managing global settings.
"""

import ctypes
import json
from ctypes import wintypes
from dataclasses import asdict, dataclass
from pathlib import Path

APP_NAME = "remaku"


def get_documents_dir() -> Path:
    try:
        CSIDL_PERSONAL = 5
        SHGFP_TYPE_CURRENT = 0
        buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
        res = ctypes.windll.shell32.SHGetFolderPathW(None, CSIDL_PERSONAL, None, SHGFP_TYPE_CURRENT, buf)
        if res == 0 and buf.value:
            return Path(buf.value)
    except Exception:
        pass
    return Path.home() / "Documents"


def user_data_dir() -> Path:
    dir_path = get_documents_dir() / APP_NAME
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


def config_path() -> Path:
    return user_data_dir() / "config.json"


def templates_dir(macro_name: str = "") -> Path:
    dir_path = user_data_dir() / "templates"
    if macro_name:
        dir_path = dir_path / macro_name
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


def macros_dir() -> Path:
    dir_path = user_data_dir() / "macros"
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


def logs_dir() -> Path:
    dir_path = user_data_dir() / "logs"
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


@dataclass
class GeneralCfg:
    target_window: str = ""
    always_on_top: bool = False
    check_update_on_startup: bool = True
    update_channel: str = "stable"
    skipped_version: str = ""
    theme: str = "system"
    language: str = "auto"


@dataclass
class CaptureCfg:
    fps: int = 10


@dataclass
class InputCfg:
    jitter_ms: int = 60


@dataclass
class Config:
    general: GeneralCfg
    capture: CaptureCfg
    input: InputCfg


def get_defaults() -> Config:
    return Config(
        general=GeneralCfg(),
        capture=CaptureCfg(),
        input=InputCfg(),
    )


def load() -> Config:
    path = config_path()
    if not path.exists():
        return get_defaults()

    data = json.loads(path.read_text(encoding="utf-8"))
    defaults = get_defaults()

    def merge(cls, defaults_inst, section: dict):
        valid_keys = {f.name for f in cls.__dataclass_fields__.values()}
        merged = {**asdict(defaults_inst), **{k: v for k, v in section.items() if k in valid_keys}}
        return cls(**merged)

    return Config(
        general=merge(GeneralCfg, defaults.general, data.get("general", {})),
        capture=merge(CaptureCfg, defaults.capture, data.get("capture", {})),
        input=merge(InputCfg, defaults.input, data.get("input", {})),
    )


def save(conf: Config) -> None:
    path = config_path()
    path.write_text(json.dumps(asdict(conf), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
