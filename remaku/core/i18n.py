import re
from typing import Any

from PySide6.QtCore import QLocale

DEFAULT_LANGUAGE = "en_US"
SYSTEM_LANGUAGE = "system"
SUPPORTED_LANGUAGES = (
    ("English", "en_US"),
    ("繁體中文", "zh_TW"),
    ("简体中文", "zh_CN"),
)
SUPPORTED_TRANSLATOR_LANGUAGES = {"zh_TW", "zh_CN"}
LanguageText = dict[str, str]


def normalize_language(language: str) -> str:
    return language.strip().replace("-", "_")


def normalize_language_key(language: str) -> str:
    return normalize_language(language).lower()


def resolve_language(language: str) -> str:
    if language == SYSTEM_LANGUAGE:
        return QLocale.system().name()

    return normalize_language(language)


def language_base(language: str) -> str:
    return normalize_language_key(language).split("_", 1)[0]


def settings_language_options(system_label: str) -> list[tuple[str, str]]:
    return [(system_label, SYSTEM_LANGUAGE), *SUPPORTED_LANGUAGES]


def localized_text(value: LanguageText, language: str) -> str:
    normalized = normalize_language(language)

    if value.get(normalized):
        return value[normalized]

    if value.get(DEFAULT_LANGUAGE):
        return value[DEFAULT_LANGUAGE]

    for text in value.values():
        if text:
            return text

    return ""


def parse_localized_text(value: Any) -> LanguageText:
    if isinstance(value, dict):
        return {normalize_language(str(key)): str(text) for key, text in value.items() if text is not None}

    return {DEFAULT_LANGUAGE: str(value or "")}


def localized_sections(body: str, language: str) -> str:
    sections = re.split(r"<!--\s*lang:([\w-]+)\s*-->", body)

    if len(sections) < 3:
        return body.strip()

    mapping: dict[str, str] = {}

    for index in range(1, len(sections), 2):
        mapping[normalize_language_key(sections[index])] = sections[index + 1].strip()

    resolved_language = resolve_language(language)
    normalized_language = normalize_language_key(resolved_language)
    base_language = language_base(resolved_language)

    return mapping.get(normalized_language) or mapping.get(base_language) or mapping.get("en") or body.strip()
