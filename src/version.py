"""Version information.

Defines the application's current version number.
"""

import sys
import tomllib
from pathlib import Path

root = (
    Path(sys._MEIPASS)  # type: ignore[attr-defined]
    if getattr(sys, "frozen", False)
    else Path(__file__).resolve().parent.parent
)

with open(root / "pyproject.toml", "rb") as f:
    __version__ = tomllib.load(f)["project"]["version"]
