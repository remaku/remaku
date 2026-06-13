from remaku.core import i18n


def test_normalize_language_preserves_supported_region_case() -> None:
    assert i18n.normalize_language("zh-TW") == "zh_TW"
    assert i18n.normalize_language_key("ZH-tw") == "zh_tw"


def test_localized_text_uses_requested_language_then_english() -> None:
    value = {"en_US": "English", "zh_TW": "繁中"}

    assert i18n.localized_text(value, "zh-TW") == "繁中"
    assert i18n.localized_text(value, "fr_FR") == "English"


def test_localized_text_uses_first_non_empty_then_empty_string() -> None:
    assert i18n.localized_text({"zh_TW": "繁中"}, "fr_FR") == "繁中"
    assert i18n.localized_text({"zh_TW": ""}, "fr_FR") == ""


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


class MockLocale:
    def __init__(self, language, script, territory, ui_languages):
        self.language_val = language
        self.script_val = script
        self.territory_val = territory
        self.ui_languages_val = ui_languages

    def language(self):
        return self.language_val

    def script(self):
        return self.script_val

    def territory(self):
        return self.territory_val

    def uiLanguages(self):
        return self.ui_languages_val


def test_resolve_system_chinese_traditional_script(monkeypatch) -> None:
    monkeypatch.setattr(
        i18n.QLocale,
        "system",
        lambda: MockLocale(
            i18n.QLocale.Language.Chinese,
            i18n.QLocale.Script.TraditionalHanScript,
            i18n.QLocale.Country.Taiwan,
            ["zh-TW"],
        ),
    )
    assert i18n.resolve_language("system") == "zh_TW"


def test_resolve_system_chinese_simplified_script(monkeypatch) -> None:
    monkeypatch.setattr(
        i18n.QLocale,
        "system",
        lambda: MockLocale(
            i18n.QLocale.Language.Chinese,
            i18n.QLocale.Script.SimplifiedHanScript,
            i18n.QLocale.Country.China,
            ["zh-CN"],
        ),
    )
    assert i18n.resolve_language("system") == "zh_CN"


def test_resolve_system_chinese_territory_taiwan(monkeypatch) -> None:
    monkeypatch.setattr(
        i18n.QLocale,
        "system",
        lambda: MockLocale(
            i18n.QLocale.Language.Chinese,
            i18n.QLocale.Script.LatinScript,
            i18n.QLocale.Country.Taiwan,
            ["zh-TW"],
        ),
    )
    assert i18n.resolve_language("system") == "zh_TW"


def test_resolve_system_chinese_territory_hongkong(monkeypatch) -> None:
    monkeypatch.setattr(
        i18n.QLocale,
        "system",
        lambda: MockLocale(
            i18n.QLocale.Language.Chinese,
            i18n.QLocale.Script.LatinScript,
            i18n.QLocale.Country.HongKong,
            ["zh-HK"],
        ),
    )
    assert i18n.resolve_language("system") == "zh_TW"


def test_resolve_system_chinese_territory_china(monkeypatch) -> None:
    monkeypatch.setattr(
        i18n.QLocale,
        "system",
        lambda: MockLocale(
            i18n.QLocale.Language.Chinese,
            i18n.QLocale.Script.LatinScript,
            i18n.QLocale.Country.China,
            ["zh-CN"],
        ),
    )
    assert i18n.resolve_language("system") == "zh_CN"


def test_resolve_system_chinese_territory_singapore(monkeypatch) -> None:
    monkeypatch.setattr(
        i18n.QLocale,
        "system",
        lambda: MockLocale(
            i18n.QLocale.Language.Chinese,
            i18n.QLocale.Script.LatinScript,
            i18n.QLocale.Country.Singapore,
            ["zh-SG"],
        ),
    )
    assert i18n.resolve_language("system") == "zh_CN"


def test_resolve_system_chinese_fallback(monkeypatch) -> None:
    monkeypatch.setattr(
        i18n.QLocale,
        "system",
        lambda: MockLocale(
            i18n.QLocale.Language.Chinese,
            i18n.QLocale.Script.LatinScript,
            i18n.QLocale.Country.Malaysia,
            ["zh-MY"],
        ),
    )
    assert i18n.resolve_language("system") == "zh_TW"


def test_resolve_system_english_uilanguage(monkeypatch) -> None:
    monkeypatch.setattr(
        i18n.QLocale,
        "system",
        lambda: MockLocale(
            i18n.QLocale.Language.French,
            i18n.QLocale.Script.LatinScript,
            i18n.QLocale.Country.France,
            ["en-US"],
        ),
    )
    assert i18n.resolve_language("system") == "en_US"


def test_resolve_system_zh_hant_tw_uilanguage(monkeypatch) -> None:
    monkeypatch.setattr(
        i18n.QLocale,
        "system",
        lambda: MockLocale(
            i18n.QLocale.Language.French,
            i18n.QLocale.Script.LatinScript,
            i18n.QLocale.Country.France,
            ["zh-Hant-TW"],
        ),
    )
    assert i18n.resolve_language("system") == "zh_TW"


def test_resolve_system_zh_hans_cn_uilanguage(monkeypatch) -> None:
    monkeypatch.setattr(
        i18n.QLocale,
        "system",
        lambda: MockLocale(
            i18n.QLocale.Language.French,
            i18n.QLocale.Script.LatinScript,
            i18n.QLocale.Country.France,
            ["zh-Hans-CN"],
        ),
    )
    assert i18n.resolve_language("system") == "zh_CN"


def test_resolve_system_zh_tw_territory_uilanguage(monkeypatch) -> None:
    monkeypatch.setattr(
        i18n.QLocale,
        "system",
        lambda: MockLocale(
            i18n.QLocale.Language.French,
            i18n.QLocale.Script.LatinScript,
            i18n.QLocale.Country.France,
            ["zh-TW"],
        ),
    )
    assert i18n.resolve_language("system") == "zh_TW"


def test_resolve_system_zh_cn_territory_uilanguage(monkeypatch) -> None:
    monkeypatch.setattr(
        i18n.QLocale,
        "system",
        lambda: MockLocale(
            i18n.QLocale.Language.French,
            i18n.QLocale.Script.LatinScript,
            i18n.QLocale.Country.France,
            ["zh-CN"],
        ),
    )
    assert i18n.resolve_language("system") == "zh_CN"
