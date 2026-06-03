"""Tests for MainWindow pure logic methods (no Qt required)."""

from unittest.mock import MagicMock, patch

from main_window import MainWindow

# ---------------------------------------------------------------------------
# Helper: lightweight stand-in for MainWindow instance
# ---------------------------------------------------------------------------


class FakeMainWindow:
    """Minimal object that carries only the attributes needed by pure methods."""

    def __init__(self, **attrs):
        for k, v in attrs.items():
            setattr(self, k, v)

    def bind_method(self, name):
        """Bind a MainWindow method to this instance."""
        method = getattr(MainWindow, name).__get__(self)
        setattr(self, name, method)


# ---------------------------------------------------------------------------
# parse_hotkey / key_to_vk
# ---------------------------------------------------------------------------


class TestParseHotkey:
    def test_ctrl_f1(self):
        mw = FakeMainWindow()
        mw.key_to_vk = MainWindow.key_to_vk.__get__(mw)
        mods, vk = MainWindow.parse_hotkey(mw, "ctrl+f1")
        assert mods == 0x0002
        assert vk == 0x70

    def test_alt_shift_a(self):
        mw = FakeMainWindow()
        mw.key_to_vk = MainWindow.key_to_vk.__get__(mw)
        with patch("main_window.ctypes") as mock_ctypes:
            mock_ctypes.windll.user32.VkKeyScanW.return_value = ord("A")
            mods, vk = MainWindow.parse_hotkey(mw, "alt+shift+a")
        assert mods == 0x0001 | 0x0004
        assert vk == ord("A") & 0xFF

    def test_ctrl_alt_enter(self):
        mw = FakeMainWindow()
        mw.key_to_vk = MainWindow.key_to_vk.__get__(mw)
        mods, vk = MainWindow.parse_hotkey(mw, "ctrl+alt+enter")
        assert mods == 0x0002 | 0x0001
        assert vk == 0x0D

    def test_no_modifier(self):
        mw = FakeMainWindow()
        mw.key_to_vk = MainWindow.key_to_vk.__get__(mw)
        mods, vk = MainWindow.parse_hotkey(mw, "space")
        assert mods == 0
        assert vk == 0x20

    def test_case_insensitive(self):
        mw = FakeMainWindow()
        mw.key_to_vk = MainWindow.key_to_vk.__get__(mw)
        mods, vk = MainWindow.parse_hotkey(mw, "CTRL+F1")
        assert mods == 0x0002
        assert vk == 0x70


class TestKeyToVk:
    def test_f_keys(self):
        mw = FakeMainWindow()
        assert MainWindow.key_to_vk(mw, "f1") == 0x70
        assert MainWindow.key_to_vk(mw, "f12") == 0x7B

    def test_special_keys(self):
        mw = FakeMainWindow()
        assert MainWindow.key_to_vk(mw, "space") == 0x20
        assert MainWindow.key_to_vk(mw, "enter") == 0x0D
        assert MainWindow.key_to_vk(mw, "escape") == 0x1B
        assert MainWindow.key_to_vk(mw, "tab") == 0x09
        assert MainWindow.key_to_vk(mw, "delete") == 0x2E
        assert MainWindow.key_to_vk(mw, "up") == 0x26
        assert MainWindow.key_to_vk(mw, "down") == 0x28

    def test_single_char(self):
        mw = FakeMainWindow()
        with patch("main_window.ctypes") as mock_ctypes:
            mock_ctypes.windll.user32.VkKeyScanW.return_value = 0x41
            assert MainWindow.key_to_vk(mw, "a") == 0x41

    def test_unknown_key_returns_zero(self):
        mw = FakeMainWindow()
        assert MainWindow.key_to_vk(mw, "nonexistent") == 0


# ---------------------------------------------------------------------------
# collect_template_refs
# ---------------------------------------------------------------------------


class TestCollectTemplateRefs:
    def test_flat_steps(self):
        mw = FakeMainWindow()
        mw.bind_method("collect_template_refs")
        steps = [
            {"type": "wait_image", "template": "btn"},
            {"type": "key", "key": "a"},
        ]
        out: set[str] = set()
        mw.collect_template_refs(steps, out)
        assert out == {"btn"}

    def test_nested_repeat(self):
        mw = FakeMainWindow()
        mw.bind_method("collect_template_refs")
        steps = [
            {
                "type": "repeat",
                "count": 1,
                "steps": [{"type": "wait_image", "template": "inner"}],
            },
        ]
        out: set[str] = set()
        mw.collect_template_refs(steps, out)
        assert out == {"inner"}

    def test_if_image_then_else(self):
        mw = FakeMainWindow()
        mw.bind_method("collect_template_refs")
        steps = [
            {
                "type": "if_image",
                "template": "cond",
                "then": [{"type": "wait_image", "template": "t"}],
                "else": [{"type": "wait_image", "template": "e"}],
            },
        ]
        out: set[str] = set()
        mw.collect_template_refs(steps, out)
        assert out == {"cond", "t", "e"}

    def test_if_any_image_branches(self):
        mw = FakeMainWindow()
        mw.bind_method("collect_template_refs")
        steps = [
            {
                "type": "if_any_image",
                "templates": ["a", "b"],
                "branches": {
                    "a": [{"type": "wait_image", "template": "a"}],
                    "b": [{"type": "wait_image", "template": "b"}],
                },
            },
        ]
        out: set[str] = set()
        mw.collect_template_refs(steps, out)
        assert out == {"a", "b"}

    def test_grid_nav(self):
        mw = FakeMainWindow()
        mw.bind_method("collect_template_refs")
        steps = [
            {
                "type": "grid_nav",
                "on_next_row": [{"type": "wait_image", "template": "row"}],
                "on_next_col": [{"type": "wait_image", "template": "col"}],
            },
        ]
        out: set[str] = set()
        mw.collect_template_refs(steps, out)
        assert out == {"row", "col"}

    def test_templates_list(self):
        mw = FakeMainWindow()
        mw.bind_method("collect_template_refs")
        steps = [{"type": "if_any_image", "templates": ["x", "y"]}]
        out: set[str] = set()
        mw.collect_template_refs(steps, out)
        assert out == {"x", "y"}

    def test_empty(self):
        mw = FakeMainWindow()
        mw.bind_method("collect_template_refs")
        out: set[str] = set()
        mw.collect_template_refs([], out)
        assert out == set()


class TestTemplateLabel:
    def test_with_label(self):
        runner = MagicMock()
        runner.macro = {"templates": {"btn": {"label": "Button"}}}
        mw = FakeMainWindow(current_runner=runner)
        assert MainWindow.template_label(mw, "btn") == "Button"

    def test_without_label(self):
        runner = MagicMock()
        runner.macro = {"templates": {"btn": {}}}
        mw = FakeMainWindow(current_runner=runner)
        assert MainWindow.template_label(mw, "btn") == "btn"

    def test_no_runner(self):
        mw = FakeMainWindow(current_runner=None)
        assert MainWindow.template_label(mw, "btn") == "btn"

    def test_missing_template(self):
        runner = MagicMock()
        runner.macro = {"templates": {}}
        mw = FakeMainWindow(current_runner=runner)
        assert MainWindow.template_label(mw, "missing") == "missing"


# ---------------------------------------------------------------------------
# is_child_of_skipped_repeat
# ---------------------------------------------------------------------------


class TestIsChildOfSkippedRepeat:
    def test_with_step_tree(self):
        from step_tree import StepTree

        child = {"type": "key", "key": "a"}
        repeat = {"type": "repeat", "skip": True, "steps": [child]}
        tree = StepTree([repeat])
        mw = FakeMainWindow(step_tree=tree, flat_steps=[])
        assert MainWindow.is_child_of_skipped_repeat(mw, child) is True

    def test_not_skipped(self):
        from step_tree import StepTree

        child = {"type": "key", "key": "a"}
        repeat = {"type": "repeat", "skip": False, "steps": [child]}
        tree = StepTree([repeat])
        mw = FakeMainWindow(step_tree=tree, flat_steps=[])
        assert MainWindow.is_child_of_skipped_repeat(mw, child) is False

    def test_fallback_no_step_tree(self):
        child = {"type": "key", "key": "a"}
        repeat = {"type": "repeat", "skip": True, "steps": [child]}
        mw = FakeMainWindow(step_tree=None, flat_nodes=[])
        assert MainWindow.is_child_of_skipped_repeat(mw, child) is False

    def test_root_step(self):
        from step_tree import StepTree

        step = {"type": "key", "key": "a"}
        tree = StepTree([step])
        mw = FakeMainWindow(step_tree=tree, flat_steps=[])
        assert MainWindow.is_child_of_skipped_repeat(mw, step) is False
