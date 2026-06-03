"""Tests for i18n module."""

from unittest.mock import patch

import pytest

import i18n


@pytest.fixture(autouse=True)
def restore_i18n():
    """Save and restore i18n global state after each test."""
    saved_strings = i18n._strings.copy()
    saved_fallback = i18n._fallback.copy()
    saved_locale = i18n.current_locale
    yield
    i18n._strings = saved_strings
    i18n._fallback = saved_fallback
    i18n.current_locale = saved_locale


class TestDetectSystemLocale:
    def test_zh_tw(self):
        with patch("i18n.locale.getdefaultlocale", return_value=("zh_TW", "UTF-8")):
            assert i18n.detect_system_locale() == "zh_tw"

    def test_zh_cn(self):
        with patch("i18n.locale.getdefaultlocale", return_value=("zh_CN", "UTF-8")):
            assert i18n.detect_system_locale() == "zh_cn"

    def test_zh_hans(self):
        with patch("i18n.locale.getdefaultlocale", return_value=("zh_Hans", "UTF-8")):
            assert i18n.detect_system_locale() == "zh_cn"

    def test_zh_sg(self):
        with patch("i18n.locale.getdefaultlocale", return_value=("zh_SG", "UTF-8")):
            assert i18n.detect_system_locale() == "zh_cn"

    def test_en(self):
        with patch("i18n.locale.getdefaultlocale", return_value=("en_US", "UTF-8")):
            assert i18n.detect_system_locale() == "en"

    def test_other_defaults_to_en(self):
        with patch("i18n.locale.getdefaultlocale", return_value=("ja_JP", "UTF-8")):
            assert i18n.detect_system_locale() == "en"

    def test_none_defaults_to_en(self):
        with patch("i18n.locale.getdefaultlocale", return_value=(None, None)):
            assert i18n.detect_system_locale() == "en"

    def test_case_insensitive(self):
        with patch("i18n.locale.getdefaultlocale", return_value=("ZH-tw", "UTF-8")):
            assert i18n.detect_system_locale() == "zh_tw"


class TestLoad:
    def test_load_en(self, tmp_path, monkeypatch):
        en = tmp_path / "en.json"
        en.write_text('{"hello": "Hello"}', encoding="utf-8")
        zh_tw = tmp_path / "zh_tw.json"
        zh_tw.write_text('{"hello": "你好"}', encoding="utf-8")
        monkeypatch.setattr(i18n, "DIR", tmp_path)

        i18n.load("en")
        assert i18n.current_locale == "en"
        assert i18n.t("hello") == "Hello"

    def test_load_zh_tw_uses_fallback(self, tmp_path, monkeypatch):
        zh_tw = tmp_path / "zh_tw.json"
        zh_tw.write_text('{"hello": "你好"}', encoding="utf-8")
        monkeypatch.setattr(i18n, "DIR", tmp_path)

        i18n.load("zh_tw")
        assert i18n.current_locale == "zh_tw"
        assert i18n.t("hello") == "你好"

    def test_load_auto(self, tmp_path, monkeypatch):
        en = tmp_path / "en.json"
        en.write_text('{"hello": "Hello"}', encoding="utf-8")
        zh_tw = tmp_path / "zh_tw.json"
        zh_tw.write_text('{"hello": "你好"}', encoding="utf-8")
        monkeypatch.setattr(i18n, "DIR", tmp_path)

        with patch("i18n.detect_system_locale", return_value="en"):
            i18n.load("auto")
        assert i18n.current_locale == "en"

    def test_missing_locale_file(self, tmp_path, monkeypatch):
        zh_tw = tmp_path / "zh_tw.json"
        zh_tw.write_text('{"hello": "你好"}', encoding="utf-8")
        monkeypatch.setattr(i18n, "DIR", tmp_path)

        i18n.load("fr")
        assert i18n.current_locale == "fr"
        assert i18n.t("hello") == "你好"  # falls back to zh_tw

    def test_missing_fallback(self, tmp_path, monkeypatch):
        monkeypatch.setattr(i18n, "DIR", tmp_path)

        i18n.load("en")
        assert i18n.t("hello") == "hello"  # returns key itself


class TestT:
    def test_with_kwargs(self, tmp_path, monkeypatch):
        zh_tw = tmp_path / "zh_tw.json"
        zh_tw.write_text('{"greeting": "Hello, {name}!"}', encoding="utf-8")
        monkeypatch.setattr(i18n, "DIR", tmp_path)
        i18n.load("zh_tw")

        assert i18n.t("greeting", name="World") == "Hello, World!"

    def test_missing_key_returns_key(self, tmp_path, monkeypatch):
        zh_tw = tmp_path / "zh_tw.json"
        zh_tw.write_text("{}", encoding="utf-8")
        monkeypatch.setattr(i18n, "DIR", tmp_path)
        i18n.load("zh_tw")

        assert i18n.t("nonexistent") == "nonexistent"

    def test_fallback_chain(self, tmp_path, monkeypatch):
        en = tmp_path / "en.json"
        en.write_text('{"only_en": "EN"}', encoding="utf-8")
        zh_tw = tmp_path / "zh_tw.json"
        zh_tw.write_text('{"only_tw": "TW"}', encoding="utf-8")
        monkeypatch.setattr(i18n, "DIR", tmp_path)
        i18n.load("en")

        assert i18n.t("only_en") == "EN"
        assert i18n.t("only_tw") == "TW"
        assert i18n.t("missing") == "missing"

    def test_no_kwargs_no_format(self, tmp_path, monkeypatch):
        zh_tw = tmp_path / "zh_tw.json"
        zh_tw.write_text('{"plain": "no args"}', encoding="utf-8")
        monkeypatch.setattr(i18n, "DIR", tmp_path)
        i18n.load("zh_tw")

        assert i18n.t("plain") == "no args"
