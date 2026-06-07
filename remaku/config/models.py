"""Configuration data models and defaults for the Remaku application."""

from dataclasses import asdict, dataclass, field
from typing import Any

DEFAULT_OVERLAY_POSITION = (100, 100)


@dataclass(slots=True)
class GeneralConfig:
    always_on_top: bool = False
    check_update_on_startup: bool = True
    update_channel: str = "stable"
    skipped_version: str = ""
    theme: str = "system"
    language: str = "auto"
    macro_order: list[str] = field(default_factory=list)
    overlay_enabled: bool = True
    overlay_position: tuple[int, int] = DEFAULT_OVERLAY_POSITION


@dataclass(slots=True)
class CaptureConfig:
    fps: int = 10


@dataclass(slots=True)
class InputConfig:
    jitter_ms: int = 60


@dataclass(slots=True)
class AppConfig:
    general: GeneralConfig = field(default_factory=GeneralConfig)
    capture: CaptureConfig = field(default_factory=CaptureConfig)
    input: InputConfig = field(default_factory=InputConfig)

    def to_dict(self) -> dict[str, Any]:
        config_dict = asdict(self)
        config_dict["general"]["overlay_position"] = list(self.general.overlay_position)
        return config_dict

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppConfig":
        default_config = cls()
        default_general = default_config.general
        default_capture = default_config.capture
        default_input = default_config.input

        general_data = data.get("general", {})
        capture_data = data.get("capture", {})
        input_data = data.get("input", {})

        overlay_position = general_data.get(
            "overlay_position",
            default_general.overlay_position,
        )

        if not isinstance(overlay_position, list | tuple) or len(overlay_position) != 2:
            overlay_position = default_general.overlay_position

        general = GeneralConfig(
            always_on_top=bool(general_data.get("always_on_top", default_general.always_on_top)),
            check_update_on_startup=bool(
                general_data.get(
                    "check_update_on_startup",
                    default_general.check_update_on_startup,
                )
            ),
            update_channel=str(general_data.get("update_channel", default_general.update_channel)),
            skipped_version=str(general_data.get("skipped_version", default_general.skipped_version)),
            theme=str(general_data.get("theme", default_general.theme)),
            language=str(general_data.get("language", default_general.language)),
            macro_order=[
                str(item)
                for item in general_data.get("macro_order", default_general.macro_order)
                if isinstance(item, str)
            ],
            overlay_enabled=bool(general_data.get("overlay_enabled", default_general.overlay_enabled)),
            overlay_position=(int(overlay_position[0]), int(overlay_position[1])),
        )

        capture = CaptureConfig(
            fps=int(capture_data.get("fps", default_capture.fps)),
        )

        input_config = InputConfig(
            jitter_ms=int(input_data.get("jitter_ms", default_input.jitter_ms)),
        )

        return cls(general=general, capture=capture, input=input_config)
