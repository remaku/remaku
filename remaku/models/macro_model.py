import json
import re
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
DEFAULT_MOUSE_DOWN_UP_DELAY_MS = 70
DEFAULT_MOUSE_SCROLL_CLICKS = 3
DEFAULT_TEMPLATE_MATCH_MODE = "grayscale"
TEMPLATE_MATCH_MODES = ("grayscale", "color")
DEFAULT_NUMBER_X = 0
DEFAULT_NUMBER_Y = 0
DEFAULT_NUMBER_WIDTH = 0
DEFAULT_NUMBER_HEIGHT = 0
DEFAULT_NUMBER_RELATIVE = True
DEFAULT_NUMBER_CAPTURE_WIDTH = 0
DEFAULT_NUMBER_CAPTURE_HEIGHT = 0
DEFAULT_NUMBER_OPERATOR = "≥"
DEFAULT_NUMBER_VALUE = 0
DEFAULT_NUMBER_STABLE_READS = 2
DEFAULT_NUMBER_CHECK_FIRST = True
NUMBER_OPERATORS = ("=", "≠", ">", "≥", "<", "≤")
VARIABLE_TYPES = ("text", "number", "boolean", "key")
VARIABLE_REF_KIND = "variable"
VARIABLE_NAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
VARIABLE_FIELD_TYPES: dict[str, str] = {
    "text": "text",
    "key": "key",
    "ms": "number",
    "hold_ms": "number",
    "timeout_ms": "number",
    "load_delay_ms": "number",
    "find_timeout_ms": "number",
    "gone_grace_ms": "number",
    "hard_timeout_ms": "number",
    "count": "number",
    "rows": "number",
    "start": "number",
    "interval_ms": "number",
    "clicks": "number",
    "down_up_delay_ms": "number",
    "x": "number",
    "y": "number",
    "width": "number",
    "height": "number",
    "capture_width": "number",
    "capture_height": "number",
    "stable_reads": "number",
    "value": "number",
}


type VariableRef = dict[str, str]
type VariableCapableInt = int | VariableRef
type VariableCapableString = str | VariableRef


def is_valid_variable_name(name: str) -> bool:
    return bool(VARIABLE_NAME_PATTERN.fullmatch(name))


def slugify_variable_name(value: str, fallback: str = "variable") -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.strip().lower())
    slug = re.sub(r"_+", "_", slug).strip("_")

    if not slug:
        slug = fallback

    if slug[0].isdigit():
        slug = f"{fallback}_{slug}"

    return slug


def variable_ref(name: str) -> VariableRef:
    return {"kind": VARIABLE_REF_KIND, "name": name}


def is_variable_ref(value: Any) -> bool:
    return isinstance(value, dict) and value.get("kind") == VARIABLE_REF_KIND and isinstance(value.get("name"), str)


def variable_ref_name(value: Any) -> str:
    if not is_variable_ref(value):
        return ""

    return str(value.get("name", ""))


def parse_variable_ref(value: Any) -> VariableRef | None:
    if not is_variable_ref(value):
        return None

    name = variable_ref_name(value)
    if not is_valid_variable_name(name):
        return None

    return variable_ref(name)


def parse_variable_capable_int(value: Any, default: int) -> VariableCapableInt:
    ref = parse_variable_ref(value)
    if ref is not None:
        return ref

    return int(value if value is not None else default)


def parse_variable_capable_string(value: Any, default: str) -> VariableCapableString:
    ref = parse_variable_ref(value)
    if ref is not None:
        return ref

    return str(value if value is not None else default)


def parse_variable_value(variable_type: str, value: Any) -> str | int | bool:
    if variable_type == "number":
        return int(value)

    if variable_type == "boolean":
        return parse_bool(value)

    return str(value)


@dataclass(slots=True)
class MacroVariable:
    label: str = ""
    type: str = "text"
    value: str | int | bool = ""

    @classmethod
    def from_dict(cls, data: Any) -> "MacroVariable | None":
        if not isinstance(data, dict):
            return None

        variable_type = str(data.get("type", "text"))
        if variable_type not in VARIABLE_TYPES:
            return None

        try:
            value = parse_variable_value(variable_type, data.get("value", default_variable_value(variable_type)))
        except (TypeError, ValueError):
            value = default_variable_value(variable_type)

        return cls(
            label=str(data.get("label", "")),
            type=variable_type,
            value=value,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "type": self.type,
            "value": self.value,
        }


def default_variable_value(variable_type: str) -> str | int | bool:
    if variable_type == "number":
        return 0

    if variable_type == "boolean":
        return False

    return ""


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
    match_mode: str = DEFAULT_TEMPLATE_MATCH_MODE


@dataclass(slots=True)
class KeyStep:
    type: str = "key"
    skip: bool = DEFAULT_STEP_SKIP
    note: str = DEFAULT_STEP_NOTE
    key: VariableCapableString = DEFAULT_KEY
    hold_ms: VariableCapableInt = DEFAULT_KEY_HOLD_MS

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "KeyStep":
        default = cls()

        return cls(
            skip=bool(data.get("skip", default.skip)),
            note=str(data.get("note", default.note)),
            key=parse_variable_capable_string(data.get("key"), DEFAULT_KEY),
            hold_ms=parse_variable_capable_int(data.get("hold_ms"), DEFAULT_KEY_HOLD_MS),
        )

    def to_dict(self) -> dict[str, Any]:
        return step_to_dict(self)


@dataclass(slots=True)
class DelayStep:
    type: str = "delay"
    skip: bool = DEFAULT_STEP_SKIP
    note: str = DEFAULT_STEP_NOTE
    ms: VariableCapableInt = DEFAULT_DELAY_MS

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DelayStep":
        default = cls()

        return cls(
            skip=bool(data.get("skip", default.skip)),
            note=str(data.get("note", default.note)),
            ms=parse_variable_capable_int(data.get("ms"), DEFAULT_DELAY_MS),
        )

    def to_dict(self) -> dict[str, Any]:
        return step_to_dict(self)


@dataclass(slots=True)
class WaitImageStep:
    type: str = "wait_image"
    skip: bool = DEFAULT_STEP_SKIP
    note: str = DEFAULT_STEP_NOTE
    template: str = ""
    timeout_ms: VariableCapableInt = DEFAULT_IMAGE_TIMEOUT
    on_timeout: str = DEFAULT_ON_TIMEOUT
    threshold: float = DEFAULT_THRESHOLD

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WaitImageStep":
        default = cls()

        return cls(
            skip=bool(data.get("skip", default.skip)),
            note=str(data.get("note", default.note)),
            template=str(data.get("template", default.template)),
            timeout_ms=parse_variable_capable_int(data.get("timeout_ms"), DEFAULT_IMAGE_TIMEOUT),
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
    key: VariableCapableString = ""
    template: str = ""
    load_delay_ms: VariableCapableInt = DEFAULT_LOAD_DELAY_MS
    find_timeout_ms: VariableCapableInt = DEFAULT_FIND_TIMEOUT_MS
    gone_grace_ms: VariableCapableInt = DEFAULT_GONE_GRACE_MS
    hard_timeout_ms: VariableCapableInt = DEFAULT_HARD_TIMEOUT_MS
    threshold: float = DEFAULT_THRESHOLD

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HoldKeyUntilGoneStep":
        default = cls()

        return cls(
            skip=bool(data.get("skip", default.skip)),
            note=str(data.get("note", default.note)),
            key=parse_variable_capable_string(data.get("key"), ""),
            template=str(data.get("template", default.template)),
            load_delay_ms=parse_variable_capable_int(data.get("load_delay_ms"), DEFAULT_LOAD_DELAY_MS),
            find_timeout_ms=parse_variable_capable_int(data.get("find_timeout_ms"), DEFAULT_FIND_TIMEOUT_MS),
            gone_grace_ms=parse_variable_capable_int(data.get("gone_grace_ms"), DEFAULT_GONE_GRACE_MS),
            hard_timeout_ms=parse_variable_capable_int(data.get("hard_timeout_ms"), DEFAULT_HARD_TIMEOUT_MS),
            threshold=float(data.get("threshold", default.threshold)),
        )

    def to_dict(self) -> dict[str, Any]:
        return step_to_dict(self)


@dataclass(slots=True)
class TextInputStep:
    type: str = "text_input"
    skip: bool = DEFAULT_STEP_SKIP
    note: str = DEFAULT_STEP_NOTE
    text: VariableCapableString = DEFAULT_TEXT_INPUT_TEXT
    interval_ms: VariableCapableInt = DEFAULT_TEXT_INPUT_INTERVAL_MS

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TextInputStep":
        default = cls()

        return cls(
            skip=bool(data.get("skip", default.skip)),
            note=str(data.get("note", default.note)),
            text=parse_variable_capable_string(data.get("text"), DEFAULT_TEXT_INPUT_TEXT),
            interval_ms=parse_variable_capable_int(data.get("interval_ms"), DEFAULT_TEXT_INPUT_INTERVAL_MS),
        )

    def to_dict(self) -> dict[str, Any]:
        return step_to_dict(self)


def parse_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        return value.lower() == "true"

    if value is None:
        return default

    return bool(value)


def parse_number_operator(value: Any) -> str:
    operator = str(value)
    if operator not in NUMBER_OPERATORS:
        return DEFAULT_NUMBER_OPERATOR

    return operator


@dataclass(slots=True)
class WaitNumberStep:
    type: str = "wait_number"
    skip: bool = DEFAULT_STEP_SKIP
    note: str = DEFAULT_STEP_NOTE
    x: VariableCapableInt = DEFAULT_NUMBER_X
    y: VariableCapableInt = DEFAULT_NUMBER_Y
    width: VariableCapableInt = DEFAULT_NUMBER_WIDTH
    height: VariableCapableInt = DEFAULT_NUMBER_HEIGHT
    relative: bool = DEFAULT_NUMBER_RELATIVE
    capture_width: VariableCapableInt = DEFAULT_NUMBER_CAPTURE_WIDTH
    capture_height: VariableCapableInt = DEFAULT_NUMBER_CAPTURE_HEIGHT
    operator: str = DEFAULT_NUMBER_OPERATOR
    value: VariableCapableInt = DEFAULT_NUMBER_VALUE
    timeout_ms: VariableCapableInt = DEFAULT_IMAGE_TIMEOUT
    stable_reads: VariableCapableInt = DEFAULT_NUMBER_STABLE_READS

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WaitNumberStep":
        default = cls()

        return cls(
            skip=parse_bool(data.get("skip"), default.skip),
            note=str(data.get("note", default.note)),
            x=parse_variable_capable_int(data.get("x"), DEFAULT_NUMBER_X),
            y=parse_variable_capable_int(data.get("y"), DEFAULT_NUMBER_Y),
            width=parse_variable_capable_int(data.get("width"), DEFAULT_NUMBER_WIDTH),
            height=parse_variable_capable_int(data.get("height"), DEFAULT_NUMBER_HEIGHT),
            relative=parse_bool(data.get("relative"), default.relative),
            capture_width=parse_variable_capable_int(data.get("capture_width"), DEFAULT_NUMBER_CAPTURE_WIDTH),
            capture_height=parse_variable_capable_int(data.get("capture_height"), DEFAULT_NUMBER_CAPTURE_HEIGHT),
            operator=parse_number_operator(data.get("operator", default.operator)),
            value=parse_variable_capable_int(data.get("value"), DEFAULT_NUMBER_VALUE),
            timeout_ms=parse_variable_capable_int(data.get("timeout_ms"), DEFAULT_IMAGE_TIMEOUT),
            stable_reads=parse_variable_capable_int(data.get("stable_reads"), DEFAULT_NUMBER_STABLE_READS),
        )

    def to_dict(self) -> dict[str, Any]:
        return step_to_dict(self)


@dataclass(slots=True)
class IfNumberStep:
    type: str = "if_number"
    skip: bool = DEFAULT_STEP_SKIP
    note: str = DEFAULT_STEP_NOTE
    x: VariableCapableInt = DEFAULT_NUMBER_X
    y: VariableCapableInt = DEFAULT_NUMBER_Y
    width: VariableCapableInt = DEFAULT_NUMBER_WIDTH
    height: VariableCapableInt = DEFAULT_NUMBER_HEIGHT
    relative: bool = DEFAULT_NUMBER_RELATIVE
    capture_width: VariableCapableInt = DEFAULT_NUMBER_CAPTURE_WIDTH
    capture_height: VariableCapableInt = DEFAULT_NUMBER_CAPTURE_HEIGHT
    operator: str = DEFAULT_NUMBER_OPERATOR
    value: VariableCapableInt = DEFAULT_NUMBER_VALUE
    timeout_ms: VariableCapableInt = DEFAULT_IMAGE_TIMEOUT
    stable_reads: VariableCapableInt = DEFAULT_NUMBER_STABLE_READS
    then: list["Step"] = field(default_factory=list)
    else_: list["Step"] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IfNumberStep":
        default = cls()

        return cls(
            skip=parse_bool(data.get("skip"), default.skip),
            note=str(data.get("note", default.note)),
            x=parse_variable_capable_int(data.get("x"), DEFAULT_NUMBER_X),
            y=parse_variable_capable_int(data.get("y"), DEFAULT_NUMBER_Y),
            width=parse_variable_capable_int(data.get("width"), DEFAULT_NUMBER_WIDTH),
            height=parse_variable_capable_int(data.get("height"), DEFAULT_NUMBER_HEIGHT),
            relative=parse_bool(data.get("relative"), default.relative),
            capture_width=parse_variable_capable_int(data.get("capture_width"), DEFAULT_NUMBER_CAPTURE_WIDTH),
            capture_height=parse_variable_capable_int(data.get("capture_height"), DEFAULT_NUMBER_CAPTURE_HEIGHT),
            operator=parse_number_operator(data.get("operator", default.operator)),
            value=parse_variable_capable_int(data.get("value"), DEFAULT_NUMBER_VALUE),
            timeout_ms=parse_variable_capable_int(data.get("timeout_ms"), DEFAULT_IMAGE_TIMEOUT),
            stable_reads=parse_variable_capable_int(data.get("stable_reads"), DEFAULT_NUMBER_STABLE_READS),
            then=parse_steps(data.get("then", default.then)),
            else_=parse_steps(data.get("else", default.else_)),
        )

    def to_dict(self) -> dict[str, Any]:
        return step_to_dict(self)


@dataclass(slots=True)
class RepeatUntilNumberStep:
    type: str = "repeat_until_number"
    skip: bool = DEFAULT_STEP_SKIP
    note: str = DEFAULT_STEP_NOTE
    x: VariableCapableInt = DEFAULT_NUMBER_X
    y: VariableCapableInt = DEFAULT_NUMBER_Y
    width: VariableCapableInt = DEFAULT_NUMBER_WIDTH
    height: VariableCapableInt = DEFAULT_NUMBER_HEIGHT
    relative: bool = DEFAULT_NUMBER_RELATIVE
    capture_width: VariableCapableInt = DEFAULT_NUMBER_CAPTURE_WIDTH
    capture_height: VariableCapableInt = DEFAULT_NUMBER_CAPTURE_HEIGHT
    operator: str = DEFAULT_NUMBER_OPERATOR
    value: VariableCapableInt = DEFAULT_NUMBER_VALUE
    timeout_ms: VariableCapableInt = DEFAULT_IMAGE_TIMEOUT
    stable_reads: VariableCapableInt = DEFAULT_NUMBER_STABLE_READS
    count: VariableCapableInt = DEFAULT_REPEAT_COUNT
    check_first: bool = DEFAULT_NUMBER_CHECK_FIRST
    steps: list["Step"] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RepeatUntilNumberStep":
        default = cls()

        return cls(
            skip=parse_bool(data.get("skip"), default.skip),
            note=str(data.get("note", default.note)),
            x=parse_variable_capable_int(data.get("x"), DEFAULT_NUMBER_X),
            y=parse_variable_capable_int(data.get("y"), DEFAULT_NUMBER_Y),
            width=parse_variable_capable_int(data.get("width"), DEFAULT_NUMBER_WIDTH),
            height=parse_variable_capable_int(data.get("height"), DEFAULT_NUMBER_HEIGHT),
            relative=parse_bool(data.get("relative"), default.relative),
            capture_width=parse_variable_capable_int(data.get("capture_width"), DEFAULT_NUMBER_CAPTURE_WIDTH),
            capture_height=parse_variable_capable_int(data.get("capture_height"), DEFAULT_NUMBER_CAPTURE_HEIGHT),
            operator=parse_number_operator(data.get("operator", default.operator)),
            value=parse_variable_capable_int(data.get("value"), DEFAULT_NUMBER_VALUE),
            timeout_ms=parse_variable_capable_int(data.get("timeout_ms"), DEFAULT_IMAGE_TIMEOUT),
            stable_reads=parse_variable_capable_int(data.get("stable_reads"), DEFAULT_NUMBER_STABLE_READS),
            count=parse_variable_capable_int(data.get("count"), DEFAULT_REPEAT_COUNT),
            check_first=parse_bool(data.get("check_first"), default.check_first),
            steps=parse_steps(data.get("steps", default.steps)),
        )

    def to_dict(self) -> dict[str, Any]:
        return step_to_dict(self)


type Step = (
    KeyStep
    | DelayStep
    | WaitImageStep
    | HoldKeyUntilGoneStep
    | TextInputStep
    | WaitNumberStep
    | IfNumberStep
    | RepeatUntilNumberStep
    | RepeatStep
    | IfImageStep
    | IfAnyImageStep
    | GridNavStep
    | MouseClickStep
    | MouseMoveStep
    | MouseScrollStep
)


def step_to_dict(step: Step) -> dict[str, Any]:
    return normalize_step_keys(asdict(step))


def normalize_step_keys(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            ("else" if key == "else_" else key): normalize_step_keys(inner_value) for key, inner_value in value.items()
        }

    if isinstance(value, list):
        return [normalize_step_keys(item) for item in value]

    return value


@dataclass(slots=True)
class RepeatStep:
    type: str = "repeat"
    skip: bool = DEFAULT_STEP_SKIP
    note: str = DEFAULT_STEP_NOTE
    count: VariableCapableInt = DEFAULT_REPEAT_COUNT
    steps: list[Step] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RepeatStep":
        default = cls()

        return cls(
            skip=bool(data.get("skip", default.skip)),
            note=str(data.get("note", default.note)),
            count=parse_variable_capable_int(data.get("count"), DEFAULT_REPEAT_COUNT),
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
    timeout_ms: VariableCapableInt = DEFAULT_IMAGE_TIMEOUT
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
            timeout_ms=parse_variable_capable_int(data.get("timeout_ms"), DEFAULT_IMAGE_TIMEOUT),
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
    timeout_ms: VariableCapableInt = DEFAULT_IMAGE_TIMEOUT
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
            timeout_ms=parse_variable_capable_int(data.get("timeout_ms"), DEFAULT_IMAGE_TIMEOUT),
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
    rows: VariableCapableInt = DEFAULT_GRID_ROWS
    start: VariableCapableInt = DEFAULT_GRID_START
    on_next_row: list[Step] = field(default_factory=list)
    on_next_col: list[Step] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GridNavStep":
        default = cls()

        return cls(
            skip=bool(data.get("skip", default.skip)),
            note=str(data.get("note", default.note)),
            rows=parse_variable_capable_int(data.get("rows"), DEFAULT_GRID_ROWS),
            start=parse_variable_capable_int(data.get("start"), DEFAULT_GRID_START),
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
    x: VariableCapableInt = DEFAULT_MOUSE_X
    y: VariableCapableInt = DEFAULT_MOUSE_Y
    relative: bool = DEFAULT_MOUSE_RELATIVE
    template: str = ""
    threshold: float = DEFAULT_THRESHOLD
    timeout_ms: VariableCapableInt = DEFAULT_IMAGE_TIMEOUT
    on_timeout: str = DEFAULT_ON_TIMEOUT
    down_up_delay_ms: VariableCapableInt = DEFAULT_MOUSE_DOWN_UP_DELAY_MS

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MouseClickStep":
        default = cls()

        return cls(
            skip=bool(data.get("skip", default.skip)),
            note=str(data.get("note", default.note)),
            button=str(data.get("button", default.button)),
            target=str(data.get("target", default.target)),
            x=parse_variable_capable_int(data.get("x"), DEFAULT_MOUSE_X),
            y=parse_variable_capable_int(data.get("y"), DEFAULT_MOUSE_Y),
            relative=bool(data.get("relative", default.relative)),
            template=str(data.get("template", default.template)),
            threshold=float(data.get("threshold", default.threshold)),
            timeout_ms=parse_variable_capable_int(data.get("timeout_ms"), DEFAULT_IMAGE_TIMEOUT),
            on_timeout=str(data.get("on_timeout", default.on_timeout)),
            down_up_delay_ms=parse_variable_capable_int(data.get("down_up_delay_ms"), DEFAULT_MOUSE_DOWN_UP_DELAY_MS),
        )

    def to_dict(self) -> dict[str, Any]:
        return step_to_dict(self)


@dataclass(slots=True)
class MouseMoveStep:
    type: str = "mouse_move"
    skip: bool = DEFAULT_STEP_SKIP
    note: str = DEFAULT_STEP_NOTE
    target: str = DEFAULT_MOUSE_TARGET
    x: VariableCapableInt = DEFAULT_MOUSE_X
    y: VariableCapableInt = DEFAULT_MOUSE_Y
    relative: bool = DEFAULT_MOUSE_RELATIVE
    template: str = ""
    threshold: float = DEFAULT_THRESHOLD
    timeout_ms: VariableCapableInt = DEFAULT_IMAGE_TIMEOUT
    on_timeout: str = DEFAULT_ON_TIMEOUT

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MouseMoveStep":
        default = cls()

        return cls(
            skip=bool(data.get("skip", default.skip)),
            note=str(data.get("note", default.note)),
            target=str(data.get("target", default.target)),
            x=parse_variable_capable_int(data.get("x"), DEFAULT_MOUSE_X),
            y=parse_variable_capable_int(data.get("y"), DEFAULT_MOUSE_Y),
            relative=bool(data.get("relative", default.relative)),
            template=str(data.get("template", default.template)),
            threshold=float(data.get("threshold", default.threshold)),
            timeout_ms=parse_variable_capable_int(data.get("timeout_ms"), DEFAULT_IMAGE_TIMEOUT),
            on_timeout=str(data.get("on_timeout", default.on_timeout)),
        )

    def to_dict(self) -> dict[str, Any]:
        return step_to_dict(self)


@dataclass(slots=True)
class MouseScrollStep:
    type: str = "mouse_scroll"
    skip: bool = DEFAULT_STEP_SKIP
    note: str = DEFAULT_STEP_NOTE
    clicks: VariableCapableInt = DEFAULT_MOUSE_SCROLL_CLICKS
    interval_ms: VariableCapableInt = DEFAULT_TEXT_INPUT_INTERVAL_MS

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MouseScrollStep":
        default = cls()

        return cls(
            skip=bool(data.get("skip", default.skip)),
            note=str(data.get("note", default.note)),
            clicks=parse_variable_capable_int(data.get("clicks"), DEFAULT_MOUSE_SCROLL_CLICKS),
            interval_ms=parse_variable_capable_int(data.get("interval_ms"), DEFAULT_TEXT_INPUT_INTERVAL_MS),
        )

    def to_dict(self) -> dict[str, Any]:
        return step_to_dict(self)


STEP_TYPE_REGISTRY: dict[str, type[Step]] = {
    "key": KeyStep,
    "delay": DelayStep,
    "wait_image": WaitImageStep,
    "hold_key_until_gone": HoldKeyUntilGoneStep,
    "text_input": TextInputStep,
    "wait_number": WaitNumberStep,
    "if_number": IfNumberStep,
    "repeat_until_number": RepeatUntilNumberStep,
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
    gaming_mode: bool = True
    background_input: bool = True
    keep_target_focused: bool = False
    variables: dict[str, MacroVariable] = field(default_factory=dict)
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
        variables: dict[str, MacroVariable] = {}

        raw_variables = data.get("variables", {})
        if isinstance(raw_variables, dict):
            for variable_name, variable_data in raw_variables.items():
                name = str(variable_name)
                if not is_valid_variable_name(name):
                    continue

                variable = MacroVariable.from_dict(variable_data)
                if variable is not None:
                    variables[name] = variable

        for template_id, template_data in data.get("templates", {}).items():
            match_mode = str(template_data.get("match_mode", DEFAULT_TEMPLATE_MATCH_MODE))
            if match_mode not in TEMPLATE_MATCH_MODES:
                match_mode = DEFAULT_TEMPLATE_MATCH_MODE

            templates[str(template_id)] = TemplateInfo(
                label=str(template_data.get("label", "")),
                capture_width=int(template_data.get("capture_width", 0)),
                capture_height=int(template_data.get("capture_height", 0)),
                match_mode=match_mode,
            )

        steps = parse_steps(data.get("steps", []))

        return cls(
            meta=meta,
            gaming_mode=bool(data.get("gaming_mode", True)),
            background_input=bool(data.get("background_input", True)),
            keep_target_focused=bool(data.get("keep_target_focused", False)),
            variables=variables,
            templates=templates,
            steps=steps,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "meta": {
                "name": self.meta.id,
                "label": self.meta.label,
                "target_window": self.meta.target_window,
                "hotkey": self.meta.hotkey,
                "enabled": self.meta.enabled,
            },
            "gaming_mode": self.gaming_mode,
            "background_input": self.background_input,
            "keep_target_focused": self.keep_target_focused,
            "variables": {name: variable.to_dict() for name, variable in self.variables.items()},
            "templates": {
                template_id: {
                    "label": template_data.label,
                    "capture_width": template_data.capture_width,
                    "capture_height": template_data.capture_height,
                    "match_mode": template_data.match_mode,
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


def variable_dict(variables: dict[str, MacroVariable] | dict[str, Any]) -> dict[str, MacroVariable]:
    result: dict[str, MacroVariable] = {}

    for name, variable in variables.items():
        if isinstance(variable, MacroVariable):
            result[name] = variable
            continue

        parsed = MacroVariable.from_dict(variable)
        if parsed is not None:
            result[name] = parsed

    return result


def resolve_variable_reference(
    field: str,
    value: Any,
    variables: dict[str, MacroVariable] | dict[str, Any],
) -> tuple[Any, str]:
    if not is_variable_ref(value):
        return value, ""

    expected_type = VARIABLE_FIELD_TYPES.get(field)
    if expected_type is None:
        return value, f"field '{field}' does not support variables"

    name = variable_ref_name(value)
    parsed_variables = variable_dict(variables)
    variable = parsed_variables.get(name)
    if variable is None:
        return value, f"missing variable '{name}' for field '{field}'"

    if variable.type != expected_type:
        return value, f"variable '{name}' for field '{field}' must be {expected_type}"

    try:
        return parse_variable_value(variable.type, variable.value), ""
    except (TypeError, ValueError):
        return value, f"variable '{name}' for field '{field}' has invalid value"


def resolve_step_variables(
    steps: list[dict],
    variables: dict[str, MacroVariable] | dict[str, Any],
    offset: int = 0,
) -> tuple[list[dict], list[str]]:
    resolved_steps: list[dict] = []
    errors: list[str] = []

    for index, step in enumerate(steps, start=offset + 1):
        resolved_step: dict[str, Any] = {}

        for key, value in step.items():
            if key in ("steps", "then", "else", "on_next_row", "on_next_col") and isinstance(value, list):
                nested_steps, nested_errors = resolve_step_variables(value, variables, offset=index)
                resolved_step[key] = nested_steps
                errors.extend(nested_errors)
                continue

            if key == "branches" and isinstance(value, dict):
                branches: dict[str, list[dict]] = {}

                for branch_key, branch_steps in value.items():
                    if isinstance(branch_steps, list):
                        nested_steps, nested_errors = resolve_step_variables(branch_steps, variables, offset=index)
                        branches[str(branch_key)] = nested_steps
                        errors.extend(nested_errors)

                resolved_step[key] = branches
                continue

            resolved_value, error = resolve_variable_reference(key, value, variables)
            resolved_step[key] = resolved_value

            if error:
                errors.append(f"Step {index}: {error}")

        resolved_steps.append(resolved_step)

    return resolved_steps, errors


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


def get_step_down_up_delay_ms(step: dict) -> int:
    return step.get("down_up_delay_ms", DEFAULT_MOUSE_DOWN_UP_DELAY_MS)


def get_step_scroll_clicks(step: dict) -> int:
    return step.get("clicks", DEFAULT_MOUSE_SCROLL_CLICKS)


def get_step_number_x(step: dict) -> int:
    return step.get("x", DEFAULT_NUMBER_X)


def get_step_number_y(step: dict) -> int:
    return step.get("y", DEFAULT_NUMBER_Y)


def get_step_number_width(step: dict) -> int:
    return step.get("width", DEFAULT_NUMBER_WIDTH)


def get_step_number_height(step: dict) -> int:
    return step.get("height", DEFAULT_NUMBER_HEIGHT)


def get_step_number_relative(step: dict) -> bool:
    return step.get("relative", DEFAULT_NUMBER_RELATIVE)


def get_step_number_capture_width(step: dict) -> int:
    return step.get("capture_width", DEFAULT_NUMBER_CAPTURE_WIDTH)


def get_step_number_capture_height(step: dict) -> int:
    return step.get("capture_height", DEFAULT_NUMBER_CAPTURE_HEIGHT)


def get_step_number_operator(step: dict) -> str:
    return parse_number_operator(step.get("operator", DEFAULT_NUMBER_OPERATOR))


def get_step_number_value(step: dict) -> int:
    return step.get("value", DEFAULT_NUMBER_VALUE)


def get_step_number_stable_reads(step: dict) -> int:
    return step.get("stable_reads", DEFAULT_NUMBER_STABLE_READS)


def get_step_number_check_first(step: dict) -> bool:
    return step.get("check_first", DEFAULT_NUMBER_CHECK_FIRST)
