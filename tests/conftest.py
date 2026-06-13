import copy
import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


@pytest.fixture
def isolated_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr("remaku.paths.data_dir", lambda: tmp_path)
    monkeypatch.setattr("remaku.models.config_model.data_dir", lambda: tmp_path)
    return tmp_path


@pytest.fixture
def sample_macro_dict() -> dict:
    return {
        "meta": {
            "name": "sample",
            "label": "Sample Macro",
            "target_window": "Game Window",
            "hotkey": "Ctrl+F8",
            "enabled": True,
        },
        "templates": {
            "start": {
                "label": "Start Button",
                "capture_width": 320,
                "capture_height": 180,
            },
            "done": {
                "label": "Done Marker",
                "capture_width": 640,
                "capture_height": 360,
            },
        },
        "steps": [
            {"type": "key", "key": "enter", "hold_ms": 90},
            {
                "type": "repeat",
                "count": 2,
                "steps": [
                    {"type": "delay", "ms": 100},
                    {"type": "wait_image", "template": "start", "timeout_ms": 500},
                ],
            },
            {
                "type": "if_image",
                "template": "done",
                "then": [{"type": "key", "key": "space"}],
                "else": [{"type": "delay", "ms": 50}],
            },
        ],
    }


@pytest.fixture
def sample_steps(sample_macro_dict: dict) -> list[dict]:
    return copy.deepcopy(sample_macro_dict["steps"])
