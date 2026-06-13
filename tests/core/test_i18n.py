from remaku.core import i18n


def test_normalize_language_preserves_supported_region_case() -> None:
    assert i18n.normalize_language("zh-TW") == "zh_TW"
    assert i18n.normalize_language_key("ZH-tw") == "zh_tw"


def test_localized_text_uses_requested_language_then_english() -> None:
    value = {"en_US": "English", "zh_TW": "繁中"}

    assert i18n.localized_text(value, "zh-TW") == "繁中"
    assert i18n.localized_text(value, "fr_FR") == "English"


def test_parse_localized_text_normalizes_keys_and_legacy_strings() -> None:
    assert i18n.parse_localized_text({"zh-TW": "繁中"}) == {"zh_TW": "繁中"}
    assert i18n.parse_localized_text("Legacy") == {"en_US": "Legacy"}


def test_localized_sections_uses_exact_base_and_english(monkeypatch) -> None:
    body = "<!-- lang:fr -->Français<!-- lang:zh_TW -->繁中<!-- lang:en -->English"

    assert i18n.localized_sections(body, "zh-TW") == "繁中"
    assert i18n.localized_sections(body, "fr_CA") == "Français"
    assert i18n.localized_sections(body, "de_DE") == "English"

    monkeypatch.setattr(i18n.QLocale, "system", lambda: i18n.QLocale("fr_CA"))

    assert i18n.localized_sections(body, "system") == "Français"


def test_localized_sections_returns_plain_body() -> None:
    assert i18n.localized_sections("  Plain notes  ", "zh_TW") == "Plain notes"


def test_settings_language_options_includes_system_first() -> None:
    assert i18n.settings_language_options("System") == [
        ("System", "system"),
        ("English", "en_US"),
        ("繁體中文", "zh_TW"),
        ("简体中文", "zh_CN"),
    ]
