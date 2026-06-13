import tomllib

from remaku.paths import root_dir

with open(root_dir() / "pyproject.toml", "rb") as f:
    __version__ = tomllib.load(f)["project"]["version"]
