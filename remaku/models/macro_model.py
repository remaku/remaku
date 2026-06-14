import json
from dataclasses import asdict, dataclass, field
from typing import Any

from remaku.paths import macro_path, macros_dir

DEFAULT_THRESHOLD = 0.85
DEFAULT_IMAGE_TIMEOUT = 5000
DEFAULT_KEY_HOLD_MS = 90
DEFAULT_DELAY_MS = 500
DEFAULT_LOAD_DELAY_MS = 2000
DEFAULT_FIND_TIMEOUT_MS = 15000
DEFAULT_GONE_GRACE_MS = 1500
DEFAULT_HARD_TIMEOUT_MS = 180000
DEFAULT_REPEAT_COUNT = 1
DEFAULT_GRID_ROWS = 1
DEFAULT_GRID_START = 0
DEFAULT_ON_TIMEOUT = "stop"
DEFAULT_KEY = "enter"
DEFAULT_TEXT_INPUT_TEXT = ""
DEFAULT_TEXT_INPUT_INTERVAL_MS = 0
DEFAULT_STEP_SKIP = False
DEFAULT_STEP_NOTE = ""
DEFAULT_MOUSE_BUTTON = "left"
DEFAULT_MOUSE_X = 0
DEFAULT_MOUSE_Y = 0
DEFAULT_MOUSE_TARGET = "coordinate"
DEFAULT_MOUSE_RELATIVE = True
DEFAULT_MOUSE_SCROLL_CLICKS = 3


@dataclass(slots=True)
class MacroMeta:
    id: str = ""
    label: str = ""
    target_window: str = ""
    hotkey: str = ""
    enabled: bool = True


@dataclass(slots=True)
class TemplateInfo:
    label: str = ""
    capture_width: int = 0
    capture_height: int = 0


@dataclass(slots=True)
class KeyStep:
    type: str = "key"
    skip: bool = DEFAULT_STEP_SKIP
    note: str = DEFAULT_STEP_NOTE
    key: str = DEFAULT_KEY
    hold_ms: int = DEFAULT_KEY_HOLD_MS

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "KeyStep":
        default = cls()

        return cls(
            skip=bool(data.get("skip", default.skip)),
            note=str(data.get("note", default.note)),
            key=str(data.get("key", default.key)),
            hold_ms=int(data.get("hold_ms", default.hold_ms)),
        )

    def to_dict(self) -> dict[str, Any]:
        return step_to_dict(self)


@dataclass(slots=True)
class DelayStep:
    type: str = "delay"
    skip: bool = DEFAULT_STEP_SKIP
    note: str = DEFAULT_STEP_NOTE
    ms: int = DEFAULT_DELAY_MS

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DelayStep":
        default = cls()

        return cls(
            skip=bool(data.get("skip", default.skip)),
            note=str(data.get("note", default.note)),
            ms=int(data.get("ms", default.ms)),
        )

    def to_dict(self) -> dict[str, Any]:
        return step_to_dict(self)


@dataclass(slots=True)
class WaitImageStep:
    type: str = "wait_image"
    skip: bool = DEFAULT_STEP_SKIP
    note: str = DEFAULT_STEP_NOTE
    template: str = ""
    timeout_ms: int = DEFAULT_IMAGE_TIMEOUT
    on_timeout: str = DEFAULT_ON_TIMEOUT
    threshold: float = DEFAULT_THRESHOLD

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WaitImageStep":
        default = cls()

        return cls(
            skip=bool(data.get("skip", default.skip)),
            note=str(data.get("note", default.note)),
            template=str(data.get("template", default.template)),
            timeout_ms=int(data.get("timeout_ms", default.timeout_ms)),
            on_timeout=str(data.get("on_timeout", default.on_timeout)),
            threshold=float(data.get("threshold", default.threshold)),
        )

    def to_dict(self) -> dict[str, Any]:
        return step_to_dict(self)


@dataclass(slots=True)
class HoldKeyUntilGoneStep:
    type: str = "hold_key_until_gone"
    skip: bool = DEFAULT_STEP_SKIP
    note: str = DEFAULT_STEP_NOTE
    key: str = ""
    template: str = ""
    load_delay_ms: int = DEFAULT_LOAD_DELAY_MS
    find_timeout_ms: int = DEFAULT_FIND_TIMEOUT_MS
    gone_grace_ms: int = DEFAULT_GONE_GRACE_MS
    hard_timeout_ms: int = DEFAULT_HARD_TIMEOUT_MS
    threshold: float = DEFAULT_THRESHOLD

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HoldKeyUntilGoneStep":
        default = cls()

        return cls(
            skip=bool(data.get("skip", default.skip)),
            note=str(data.get("note", default.note)),
            key=str(data.get("key", default.key)),
            template=str(data.get("template", default.template)),
            load_delay_ms=int(data.get("load_delay_ms", default.load_delay_ms)),
            find_timeout_ms=int(data.get("find_timeout_ms", default.find_timeout_ms)),
            gone_grace_ms=int(data.get("gone_grace_ms", default.gone_grace_ms)),
            hard_timeout_ms=int(data.get("hard_timeout_ms", default.hard_timeout_ms)),
            threshold=float(data.get("threshold", default.threshold)),
        )

    def to_dict(self) -> dict[str, Any]:
        return step_to_dict(self)


@dataclass(slots=True)
class TextInputStep:
    type: str = "text_input"
    skip: bool = DEFAULT_STEP_SKIP
    note: str = DEFAULT_STEP_NOTE
    text: str = DEFAULT_TEXT_INPUT_TEXT
    interval_ms: int = DEFAULT_TEXT_INPUT_INTERVAL_MS

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TextInputStep":
        default = cls()

        return cls(
            skip=bool(data.get("skip", default.skip)),
            note=str(data.get("note", default.note)),
            text=str(data.get("text", default.text)),
            interval_ms=int(data.get("interval_ms", default.interval_ms)),
        )

    def to_dict(self) -> dict[str, Any]:
        return step_to_dict(self)


type Step = (
    KeyStep
    | DelayStep
    | WaitImageStep
    | HoldKeyUntilGoneStep
    | TextInputStep
    | RepeatStep
    | IfImageStep
    | IfAnyImageStep
    | GridNavStep
    | MouseClickStep
    | MouseMoveStep
    | MouseScrollStep
)


def step_to_dict(step: Step) -> dict[str, Any]:
    return asdict(step)


@dataclass(slots=True)
class RepeatStep:
    type: str = "repeat"
    skip: bool = DEFAULT_STEP_SKIP
    note: str = DEFAULT_STEP_NOTE
    count: int = DEFAULT_REPEAT_COUNT
    steps: list[Step] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RepeatStep":
        default = cls()

        return cls(
            skip=bool(data.get("skip", default.skip)),
            note=str(data.get("note", default.note)),
            count=int(data.get("count", default.count)),
            steps=parse_steps(data.get("steps", default.steps)),
        )

    def to_dict(self) -> dict[str, Any]:
        return step_to_dict(self)


@dataclass(slots=True)
class IfImageStep:
    type: str = "if_image"
    skip: bool = DEFAULT_STEP_SKIP
    note: str = DEFAULT_STEP_NOTE
    template: str = ""
    timeout_ms: int = DEFAULT_IMAGE_TIMEOUT
    threshold: float = DEFAULT_THRESHOLD
    then: list[Step] = field(default_factory=list)
    else_: list[Step] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IfImageStep":
        default = cls()

        return cls(
            skip=bool(data.get("skip", default.skip)),
            note=str(data.get("note", default.note)),
            template=str(data.get("template", default.template)),
            timeout_ms=int(data.get("timeout_ms", default.timeout_ms)),
            threshold=float(data.get("threshold", default.threshold)),
            then=parse_steps(data.get("then", default.then)),
            else_=parse_steps(data.get("else", default.else_)),
        )

    def to_dict(self) -> dict[str, Any]:
        return step_to_dict(self)


@dataclass(slots=True)
class IfAnyImageStep:
    type: str = "if_any_image"
    skip: bool = DEFAULT_STEP_SKIP
    note: str = DEFAULT_STEP_NOTE
    templates: list[str] = field(default_factory=list)
    timeout_ms: int = DEFAULT_IMAGE_TIMEOUT
    on_timeout: str = DEFAULT_ON_TIMEOUT
    threshold: float = DEFAULT_THRESHOLD
    branches: dict[str, list[Step]] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IfAnyImageStep":
        default = cls()
        raw_branches = data.get("branches", default.branches)

        if not isinstance(raw_branches, dict):
            raw_branches = default.branches

        return cls(
            skip=bool(data.get("skip", default.skip)),
            note=str(data.get("note", default.note)),
            templates=[str(template) for template in data.get("templates", default.templates)],
            timeout_ms=int(data.get("timeout_ms", default.timeout_ms)),
            on_timeout=str(data.get("on_timeout", default.on_timeout)),
            threshold=float(data.get("threshold", default.threshold)),
            branches={str(key): parse_steps(inner_steps) for key, inner_steps in raw_branches.items()},
        )

    def to_dict(self) -> dict[str, Any]:
        return step_to_dict(self)


@dataclass(slots=True)
class GridNavStep:
    type: str = "grid_nav"
    skip: bool = DEFAULT_STEP_SKIP
    note: str = DEFAULT_STEP_NOTE
    rows: int = DEFAULT_GRID_ROWS
    start: int = DEFAULT_GRID_START
    on_next_row: list[Step] = field(default_factory=list)
    on_next_col: list[Step] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GridNavStep":
        default = cls()

        return cls(
            skip=bool(data.get("skip", default.skip)),
            note=str(data.get("note", default.note)),
            rows=int(data.get("rows", default.rows)),
            start=int(data.get("start", default.start)),
            on_next_row=parse_steps(data.get("on_next_row", default.on_next_row)),
            on_next_col=parse_steps(data.get("on_next_col", default.on_next_col)),
        )

    def to_dict(self) -> dict[str, Any]:
        return step_to_dict(self)


@dataclass(slots=True)
class MouseClickStep:
    type: str = "mouse_click"
    skip: bool = DEFAULT_STEP_SKIP
    note: str = DEFAULT_STEP_NOTE
    button: str = DEFAULT_MOUSE_BUTTON
    target: str = DEFAULT_MOUSE_TARGET
    x: int = DEFAULT_MOUSE_X
    y: int = DEFAULT_MOUSE_Y
    relative: bool = DEFAULT_MOUSE_RELATIVE
    template: str = ""
    threshold: float = DEFAULT_THRESHOLD
    timeout_ms: int = DEFAULT_IMAGE_TIMEOUT
    on_timeout: str = DEFAULT_ON_TIMEOUT

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MouseClickStep":
        default = cls()

        return cls(
            skip=bool(data.get("skip", default.skip)),
            note=str(data.get("note", default.note)),
            button=str(data.get("button", default.button)),
            target=str(data.get("target", default.target)),
            x=int(data.get("x", default.x)),
            y=int(data.get("y", default.y)),
            relative=bool(data.get("relative", default.relative)),
            template=str(data.get("template", default.template)),
            threshold=float(data.get("threshold", default.threshold)),
            timeout_ms=int(data.get("timeout_ms", default.timeout_ms)),
            on_timeout=str(data.get("on_timeout", default.on_timeout)),
        )

    def to_dict(self) -> dict[str, Any]:
        return step_to_dict(self)


@dataclass(slots=True)
class MouseMoveStep:
    type: str = "mouse_move"
    skip: bool = DEFAULT_STEP_SKIP
    note: str = DEFAULT_STEP_NOTE
    target: str = DEFAULT_MOUSE_TARGET
    x: int = DEFAULT_MOUSE_X
    y: int = DEFAULT_MOUSE_Y
    relative: bool = DEFAULT_MOUSE_RELATIVE
    template: str = ""
    threshold: float = DEFAULT_THRESHOLD
    timeout_ms: int = DEFAULT_IMAGE_TIMEOUT
    on_timeout: str = DEFAULT_ON_TIMEOUT

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MouseMoveStep":
        default = cls()

        return cls(
            skip=bool(data.get("skip", default.skip)),
            note=str(data.get("note", default.note)),
            target=str(data.get("target", default.target)),
            x=int(data.get("x", default.x)),
            y=int(data.get("y", default.y)),
            relative=bool(data.get("relative", default.relative)),
            template=str(data.get("template", default.template)),
            threshold=float(data.get("threshold", default.threshold)),
            timeout_ms=int(data.get("timeout_ms", default.timeout_ms)),
            on_timeout=str(data.get("on_timeout", default.on_timeout)),
        )

    def to_dict(self) -> dict[str, Any]:
        return step_to_dict(self)


@dataclass(slots=True)
class MouseScrollStep:
    type: str = "mouse_scroll"
    skip: bool = DEFAULT_STEP_SKIP
    note: str = DEFAULT_STEP_NOTE
    clicks: int = DEFAULT_MOUSE_SCROLL_CLICKS
    interval_ms: int = DEFAULT_TEXT_INPUT_INTERVAL_MS

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MouseScrollStep":
        default = cls()

        return cls(
            skip=bool(data.get("skip", default.skip)),
            note=str(data.get("note", default.note)),
            clicks=int(data.get("clicks", default.clicks)),
            interval_ms=int(data.get("interval_ms", default.interval_ms)),
        )

    def to_dict(self) -> dict[str, Any]:
        return step_to_dict(self)


STEP_TYPE_REGISTRY: dict[str, type[Step]] = {
    "key": KeyStep,
    "delay": DelayStep,
    "wait_image": WaitImageStep,
    "hold_key_until_gone": HoldKeyUntilGoneStep,
    "text_input": TextInputStep,
    "repeat": RepeatStep,
    "if_image": IfImageStep,
    "if_any_image": IfAnyImageStep,
    "grid_nav": GridNavStep,
    "mouse_click": MouseClickStep,
    "mouse_move": MouseMoveStep,
    "mouse_scroll": MouseScrollStep,
}


def parse_step(raw_step: Any) -> Step:
    if not isinstance(raw_step, dict):
        raise ValueError("Step must be a dictionary.")

    step_type = str(raw_step.get("type", ""))
    step_cls = STEP_TYPE_REGISTRY.get(step_type)

    if step_cls is None:
        raise ValueError(f"Unknown step type: {step_type}")

    return step_cls.from_dict(raw_step)


def parse_steps(raw_steps: Any) -> list[Step]:
    if not isinstance(raw_steps, list):
        return []

    parsed: list[Step] = []

    for raw_step in raw_steps:
        parsed.append(parse_step(raw_step))

    return parsed


@dataclass(slots=True)
class Macro:
    meta: MacroMeta = field(default_factory=MacroMeta)
    templates: dict[str, TemplateInfo] = field(default_factory=dict)
    steps: list[Step] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Macro":
        meta_data = data.get("meta", {})

        default_meta = MacroMeta()

        meta = MacroMeta(
            id=str(meta_data.get("id", meta_data.get("name", default_meta.id))),
            label=str(meta_data.get("label", default_meta.label)),
            target_window=str(meta_data.get("target_window", default_meta.target_window)),
            hotkey=str(meta_data.get("hotkey", default_meta.hotkey)),
            enabled=bool(meta_data.get("enabled", default_meta.enabled)),
        )

        templates: dict[str, TemplateInfo] = {}

        for template_id, template_data in data.get("templates", {}).items():
            templates[str(template_id)] = TemplateInfo(
                label=str(template_data.get("label", "")),
                capture_width=int(template_data.get("capture_width", 0)),
                capture_height=int(template_data.get("capture_height", 0)),
            )

        steps = parse_steps(data.get("steps", []))

        return cls(meta=meta, templates=templates, steps=steps)

    def to_dict(self) -> dict[str, Any]:
        return {
            "meta": {
                "name": self.meta.id,
                "label": self.meta.label,
                "target_window": self.meta.target_window,
                "hotkey": self.meta.hotkey,
                "enabled": self.meta.enabled,
            },
            "templates": {
                template_id: {
                    "label": template_data.label,
                    "capture_width": template_data.capture_width,
                    "capture_height": template_data.capture_height,
                }
                for template_id, template_data in self.templates.items()
            },
            "steps": [step_to_dict(step) for step in self.steps],
        }


@dataclass(slots=True)
class MacroSummary:
    id: str = ""
    label: str = ""
    path: str = ""


class MacroModel:
    def list_macros(self) -> list[MacroSummary]:
        macros_dir().mkdir(parents=True, exist_ok=True)

        result: list[MacroSummary] = []

        for file in sorted(macros_dir().glob("*.json")):
            try:
                with file.open("r", encoding="utf-8") as f:
                    data = json.load(f)
            except (OSError, json.JSONDecodeError):
                continue

            meta = data.get("meta", {})
            label = str(meta.get("label", file.stem))
            macro_id = file.stem
            result.append(MacroSummary(id=macro_id, label=label, path=str(file)))

        return result

    def load(self, macro_id: str) -> Macro | None:
        path = macro_path(macro_id)

        if not path.exists():
            return None

        try:
            with path.open("r", encoding="utf-8") as f:
                raw_data = json.load(f)
        except (OSError, json.JSONDecodeError, ValueError):
            return None

        if not isinstance(raw_data, dict):
            return None

        macro = Macro.from_dict(raw_data)
        macro.meta.id = macro_id
        return macro

    def save(self, macro: Macro) -> None:
        macros_dir().mkdir(parents=True, exist_ok=True)

        path = macros_dir() / f"{macro.meta.id}.json"

        with path.open("w", encoding="utf-8") as f:
            json.dump(macro.to_dict(), f, indent=2, ensure_ascii=False)
            f.write("\n")

    def delete(self, macro_id: str) -> bool:
        path = macros_dir() / f"{macro_id}.json"

        if not path.exists():
            return False

        path.unlink()
        return True


def get_step_threshold(step: dict) -> float:
    return step.get("threshold", DEFAULT_THRESHOLD)


def get_step_timeout(step: dict) -> int:
    return step.get("timeout_ms", DEFAULT_IMAGE_TIMEOUT)


def get_step_key(step: dict) -> str:
    return step.get("key", DEFAULT_KEY)


def get_step_hold_ms(step: dict) -> int:
    return step.get("hold_ms", DEFAULT_KEY_HOLD_MS)


def get_step_ms(step: dict) -> int:
    return step.get("ms", DEFAULT_DELAY_MS)


def get_step_load_delay(step: dict) -> int:
    return step.get("load_delay_ms", DEFAULT_LOAD_DELAY_MS)


def get_step_find_timeout(step: dict) -> int:
    return step.get("find_timeout_ms", DEFAULT_FIND_TIMEOUT_MS)


def get_step_gone_grace(step: dict) -> int:
    return step.get("gone_grace_ms", DEFAULT_GONE_GRACE_MS)


def get_step_hard_timeout(step: dict) -> int:
    return step.get("hard_timeout_ms", DEFAULT_HARD_TIMEOUT_MS)


def get_step_count(step: dict) -> int:
    return step.get("count", DEFAULT_REPEAT_COUNT)


def get_step_rows(step: dict) -> int:
    return step.get("rows", DEFAULT_GRID_ROWS)


def get_step_start(step: dict) -> int:
    return step.get("start", DEFAULT_GRID_START)


def get_step_on_timeout(step: dict) -> str:
    return step.get("on_timeout", DEFAULT_ON_TIMEOUT)


def get_step_template(step: dict) -> str:
    return step.get("template", "")


def get_step_templates(step: dict) -> list[str]:
    return step.get("templates", [])


def get_step_text(step: dict) -> str:
    return step.get("text", DEFAULT_TEXT_INPUT_TEXT)


def get_step_interval_ms(step: dict) -> int:
    return step.get("interval_ms", DEFAULT_TEXT_INPUT_INTERVAL_MS)


def get_step_button(step: dict) -> str:
    return step.get("button", DEFAULT_MOUSE_BUTTON)


def get_step_mouse_target(step: dict) -> str:
    return step.get("target", DEFAULT_MOUSE_TARGET)


def get_step_mouse_x(step: dict) -> int:
    return step.get("x", DEFAULT_MOUSE_X)


def get_step_mouse_y(step: dict) -> int:
    return step.get("y", DEFAULT_MOUSE_Y)


def get_step_mouse_relative(step: dict) -> bool:
    return step.get("relative", DEFAULT_MOUSE_RELATIVE)


def get_step_scroll_clicks(step: dict) -> int:
    return step.get("clicks", DEFAULT_MOUSE_SCROLL_CLICKS)
