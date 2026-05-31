"""Internationalization module.

Provides translation loading and lookup with fallback chain: requested locale -> zh_tw -> key.
"""

import json
import locale
import sys
from pathlib import Path

_strings: dict[str, str] = {}
_fallback: dict[str, str] = {}
current_locale: str = "en"

DIR = Path(getattr(sys, "_MEIPASS", "")) / "i18n" if getattr(sys, "frozen", False) else Path(__file__).parent
SUPPORTED = ("zh_tw", "zh_cn", "en")


def detect_system_locale() -> str:
    """Detect system language and map to a supported locale."""
    lang = locale.getdefaultlocale()[0] or ""
    lang = lang.lower().replace("-", "_")
    if lang.startswith("zh"):
        return "zh_cn" if "cn" in lang or "hans" in lang or "sg" in lang else "zh_tw"
    if lang.startswith("en"):
        return "en"
    return "en"


def load(language: str = "auto") -> None:
    """Load translation strings for the given locale."""
    global _strings, _fallback, current_locale

    loc = detect_system_locale() if language == "auto" else language
    current_locale = loc

    fallback_path = DIR / "zh_tw.json"
    _fallback = json.loads(fallback_path.read_text(encoding="utf-8")) if fallback_path.exists() else {}

    if loc == "zh_tw":
        _strings = _fallback
    else:
        locale_path = DIR / f"{loc}.json"
        _strings = json.loads(locale_path.read_text(encoding="utf-8")) if locale_path.exists() else {}


def t(msg: str, **kwargs) -> str:
    """Translate a key, formatting with kwargs. Fallback: locale -> zh_tw -> key."""
    text = _strings.get(msg) or _fallback.get(msg) or msg
    if kwargs:
        text = text.format(**kwargs)
    return text
