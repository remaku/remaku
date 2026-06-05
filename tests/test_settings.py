"""Tests for the settings page."""

from unittest.mock import MagicMock, patch

import pytest

import config as cfg
from settings import SettingsPage


@pytest.fixture
def default_config():
    return cfg.get_defaults()


@pytest.fixture
def settings_page(qtbot, default_config):
    page = SettingsPage(None, default_config)
    qtbot.addWidget(page)
    return page


class TestSettingsPageCreation:
    def test_has_object_name(self, settings_page):
        assert settings_page.objectName() == "settingsPage"

    def test_has_conf(self, settings_page, default_config):
        assert settings_page.conf is default_config

    def test_has_form_layout(self, settings_page):
        assert settings_page.form_layout is not None

    def test_on_save_none_by_default(self, settings_page):
        assert settings_page.on_save is None

    def test_on_save_set_when_passed(self, qtbot, default_config):
        cb = MagicMock()
        with patch("settings.MessageBox"):
            page = SettingsPage(None, default_config, on_save=cb)
            qtbot.addWidget(page)
        assert page.on_save is cb


class TestUIElements:
    def test_has_always_on_top_checkbox(self, settings_page):
        assert settings_page.var_always_on_top is not None
        assert settings_page.var_always_on_top.isChecked() == settings_page.conf.general.always_on_top

    def test_has_overlay_checkbox(self, settings_page):
        assert settings_page.var_overlay is not None
        assert settings_page.var_overlay.isChecked() == settings_page.conf.general.overlay_enabled

    def test_has_auto_update_checkbox(self, settings_page):
        assert settings_page.var_auto_update is not None
        assert settings_page.var_auto_update.isChecked() == settings_page.conf.general.check_update_on_startup

    def test_has_update_channel_dropdown(self, settings_page):
        assert settings_page.var_update_channel is not None
        assert settings_page.var_update_channel.currentData() == settings_page.conf.general.update_channel

    def test_has_theme_dropdown(self, settings_page):
        assert settings_page.var_theme is not None
        assert settings_page.var_theme.currentData() == settings_page.conf.general.theme

    def test_has_language_dropdown(self, settings_page):
        assert settings_page.var_language is not None
        assert settings_page.var_language.currentData() == settings_page.conf.general.language

    def test_has_fps_entry(self, settings_page):
        assert settings_page.var_fps is not None
        assert settings_page.var_fps.text() == str(settings_page.conf.capture.fps)

    def test_has_jitter_entry(self, settings_page):
        assert settings_page.var_jitter is not None
        assert settings_page.var_jitter.text() == str(settings_page.conf.input.jitter_ms)


class TestSection:
    def test_adds_label(self, settings_page):
        count_before = settings_page.form_layout.count()
        settings_page.section("My Section")
        assert settings_page.form_layout.count() == count_before + 1


class TestCheckbox:
    def test_returns_checkbox(self, settings_page):
        cb = settings_page.checkbox("Test")
        assert cb is not None

    def test_checkbox_has_label(self, settings_page):
        cb = settings_page.checkbox("Test Label")
        assert cb.text() == "Test Label"


class TestEntry:
    def test_returns_line_edit(self, settings_page):
        edit = settings_page.entry("Test", 42)
        assert edit is not None
        assert edit.text() == "42"

    def test_entry_string_value(self, settings_page):
        edit = settings_page.entry("Test", "hello")
        assert edit.text() == "hello"


class TestDropdown:
    def test_returns_combo_box(self, settings_page):
        combo = settings_page.dropdown("Test", "b", ["a", "b", "c"], "prefix")
        assert combo is not None
        assert combo.currentData() == "b"

    def test_dropdown_unknown_value_selects_first(self, settings_page):
        combo = settings_page.dropdown("Test", "z", ["a", "b", "c"], "prefix")
        assert combo.currentIndex() == 0
        assert combo.currentData() == "a"

    def test_dropdown_adds_items_with_translated_labels(self, settings_page):
        combo = settings_page.dropdown("Test", "stable", ["stable", "beta"], "settings.channel")
        assert combo.count() == 2
        assert combo.itemData(0) == "stable"
        assert combo.itemData(1) == "beta"


class TestLanguageDropdown:
    def test_returns_combo_box(self, settings_page):
        combo = settings_page.language_dropdown("en")
        assert combo is not None
        assert combo.currentData() == "en"

    def test_language_unknown_selects_first(self, settings_page):
        combo = settings_page.language_dropdown("zz")
        assert combo.currentIndex() == 0
        assert combo.currentData() == "auto"

    def test_language_has_correct_options(self, settings_page):
        combo = settings_page.language_dropdown("auto")
        assert combo.count() == 4
        assert combo.itemData(0) == "auto"
        assert combo.itemData(1) == "zh_tw"
        assert combo.itemData(2) == "zh_cn"
        assert combo.itemData(3) == "en"


class TestOnLanguageChanged:
    def test_shows_message_box(self, settings_page):
        with patch("settings.MessageBox") as mock_msg:
            settings_page.on_language_changed()
            mock_msg.assert_called_once()


class TestSave:
    def test_saves_config(self, settings_page):
        with patch("settings.cfg.save") as mock_save:
            settings_page.save()
            mock_save.assert_called_once()

    def test_calls_on_save(self, qtbot, default_config):
        cb = MagicMock()
        with patch("settings.MessageBox"):
            page = SettingsPage(None, default_config, on_save=cb)
            qtbot.addWidget(page)
        with patch("settings.cfg.save"):
            page.save()
        cb.assert_called_once()

    def test_save_values_read_from_widgets(self, settings_page):
        settings_page.var_always_on_top.setChecked(True)
        settings_page.var_overlay.setChecked(False)
        settings_page.var_fps.setText("30")
        settings_page.var_jitter.setText("100")

        with patch("settings.cfg.save") as mock_save:
            settings_page.save()
            saved = mock_save.call_args[0][0]
            assert saved.general.always_on_top is True
            assert saved.general.overlay_enabled is False
            assert saved.capture.fps == 30
            assert saved.input.jitter_ms == 100

    def test_save_preserves_target_window(self, settings_page):
        settings_page.conf.general.target_window = "MyWindow"
        with patch("settings.cfg.save") as mock_save:
            settings_page.save()
            saved = mock_save.call_args[0][0]
            assert saved.general.target_window == "MyWindow"

    def test_save_preserves_skipped_version(self, settings_page):
        settings_page.conf.general.skipped_version = "1.2.3"
        with patch("settings.cfg.save") as mock_save:
            settings_page.save()
            saved = mock_save.call_args[0][0]
            assert saved.general.skipped_version == "1.2.3"

    def test_save_preserves_overlay_position(self, settings_page):
        settings_page.conf.general.overlay_position = [200, 300]
        with patch("settings.cfg.save") as mock_save:
            settings_page.save()
            saved = mock_save.call_args[0][0]
            assert saved.general.overlay_position == [200, 300]

    def test_save_uses_defaults_for_missing_data(self, settings_page):
        settings_page.var_update_channel.setCurrentIndex(-1)
        settings_page.var_theme.setCurrentIndex(-1)
        settings_page.var_language.setCurrentIndex(-1)

        with patch("settings.cfg.save") as mock_save:
            settings_page.save()
            saved = mock_save.call_args[0][0]
            assert saved.general.update_channel == "stable"
            assert saved.general.theme == "auto"
            assert saved.general.language == "auto"

    def test_save_handles_value_error(self, settings_page):
        settings_page.var_fps.setText("not_a_number")
        with patch("settings.cfg.save") as mock_save, patch("settings.MessageBox") as mock_msg:
            settings_page.save()
            mock_save.assert_not_called()
            mock_msg.assert_called_once()

    def test_save_handles_os_error(self, settings_page):
        with patch("settings.cfg.save", side_effect=OSError("disk full")), patch("settings.MessageBox") as mock_msg:
            settings_page.save()
            mock_msg.assert_called_once()
