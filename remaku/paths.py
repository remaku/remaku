import sys
from pathlib import Path


def root_dir():
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)  # type: ignore
    else:
        return Path(__file__).parent.parent
