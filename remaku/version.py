import tomllib

from remaku.paths import get_root_dir

with open(get_root_dir() / "pyproject.toml", "rb") as f:
    __version__ = tomllib.load(f)["project"]["version"]
