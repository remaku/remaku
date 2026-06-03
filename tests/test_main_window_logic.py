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


# ---------------------------------------------------------------------------
# get_descendants
# ---------------------------------------------------------------------------


class TestGetDescendants:
    def test_repeat(self):
        mw = FakeMainWindow()
        mw.bind_method("get_descendants")
        child_a = {"type": "key", "key": "a"}
        child_b = {"type": "delay", "ms": 100}
        step = {"type": "repeat", "count": 1, "steps": [child_a, child_b]}
        desc = mw.get_descendants(step)
        assert id(child_a) in desc
        assert id(child_b) in desc

    def test_if_image(self):
        mw = FakeMainWindow()
        mw.bind_method("get_descendants")
        then_step = {"type": "key", "key": "t"}
        else_step = {"type": "key", "key": "e"}
        step = {"type": "if_image", "then": [then_step], "else": [else_step]}
        desc = mw.get_descendants(step)
        assert id(then_step) in desc
        assert id(else_step) in desc

    def test_grid_nav(self):
        mw = FakeMainWindow()
        mw.bind_method("get_descendants")
        row_step = {"type": "key", "key": "r"}
        col_step = {"type": "key", "key": "c"}
        step = {"type": "grid_nav", "on_next_row": [row_step], "on_next_col": [col_step]}
        desc = mw.get_descendants(step)
        assert id(row_step) in desc
        assert id(col_step) in desc

    def test_if_any_image_branches(self):
        mw = FakeMainWindow()
        mw.bind_method("get_descendants")
        branch_a = [{"type": "key", "key": "a"}]
        branch_b = [{"type": "key", "key": "b"}]
        step = {"type": "if_any_image", "branches": {"a": branch_a, "b": branch_b}}
        desc = mw.get_descendants(step)
        assert id(branch_a[0]) in desc
        assert id(branch_b[0]) in desc

    def test_deep_nesting(self):
        mw = FakeMainWindow()
        mw.bind_method("get_descendants")
        leaf = {"type": "key", "key": "x"}
        inner = {"type": "repeat", "count": 1, "steps": [leaf]}
        outer = {"type": "repeat", "count": 1, "steps": [inner]}
        desc = mw.get_descendants(outer)
        assert id(inner) in desc
        assert id(leaf) in desc

    def test_leaf(self):
        mw = FakeMainWindow()
        mw.bind_method("get_descendants")
        step = {"type": "key", "key": "a"}
        assert mw.get_descendants(step) == set()


# ---------------------------------------------------------------------------
# get_block_child_list
# ---------------------------------------------------------------------------


class TestGetBlockChildList:
    def test_repeat(self):
        mw = FakeMainWindow()
        steps = [{"type": "key", "key": "a"}]
        step = {"type": "repeat", "steps": steps}
        assert MainWindow.get_block_child_list(mw, step, 1) is steps
        assert MainWindow.get_block_child_list(mw, step, -1) is steps

    def test_if_image_direction_down(self):
        mw = FakeMainWindow()
        then = [{"type": "key", "key": "t"}]
        else_ = [{"type": "key", "key": "e"}]
        step = {"type": "if_image", "then": then, "else": else_}
        assert MainWindow.get_block_child_list(mw, step, 1) is then

    def test_if_image_direction_up(self):
        mw = FakeMainWindow()
        then = [{"type": "key", "key": "t"}]
        else_ = [{"type": "key", "key": "e"}]
        step = {"type": "if_image", "then": then, "else": else_}
        assert MainWindow.get_block_child_list(mw, step, -1) is else_

    def test_if_image_no_else_fallback(self):
        mw = FakeMainWindow()
        then = [{"type": "key", "key": "t"}]
        step = {"type": "if_image", "then": then}
        assert MainWindow.get_block_child_list(mw, step, -1) is then

    def test_if_any_image_direction_down(self):
        mw = FakeMainWindow()
        a = [{"type": "key", "key": "a"}]
        b = [{"type": "key", "key": "b"}]
        step = {"type": "if_any_image", "branches": {"a": a, "b": b}}
        assert MainWindow.get_block_child_list(mw, step, 1) is a

    def test_if_any_image_direction_up(self):
        mw = FakeMainWindow()
        a = [{"type": "key", "key": "a"}]
        b = [{"type": "key", "key": "b"}]
        step = {"type": "if_any_image", "branches": {"a": a, "b": b}}
        assert MainWindow.get_block_child_list(mw, step, -1) is b

    def test_if_any_image_no_branches_creates_from_templates(self):
        mw = FakeMainWindow()
        step = {"type": "if_any_image", "templates": ["x", "y"]}
        result = MainWindow.get_block_child_list(mw, step, 1)
        assert result is not None
        assert "branches" in step
        assert "x" in step["branches"]

    def test_if_any_image_no_templates_returns_none(self):
        mw = FakeMainWindow()
        step = {"type": "if_any_image"}
        assert MainWindow.get_block_child_list(mw, step, 1) is None

    def test_grid_nav_direction_down(self):
        mw = FakeMainWindow()
        row = [{"type": "key", "key": "r"}]
        col = [{"type": "key", "key": "c"}]
        step = {"type": "grid_nav", "on_next_row": row, "on_next_col": col}
        assert MainWindow.get_block_child_list(mw, step, 1) is row

    def test_grid_nav_direction_up(self):
        mw = FakeMainWindow()
        row = [{"type": "key", "key": "r"}]
        col = [{"type": "key", "key": "c"}]
        step = {"type": "grid_nav", "on_next_row": row, "on_next_col": col}
        assert MainWindow.get_block_child_list(mw, step, -1) is col

    def test_grid_nav_no_col_fallback(self):
        mw = FakeMainWindow()
        row = [{"type": "key", "key": "r"}]
        step = {"type": "grid_nav", "on_next_row": row}
        assert MainWindow.get_block_child_list(mw, step, -1) is row

    def test_leaf_returns_none(self):
        mw = FakeMainWindow()
        step = {"type": "key", "key": "a"}
        assert MainWindow.get_block_child_list(mw, step, 1) is None


# ---------------------------------------------------------------------------
# get_sibling_branch
# ---------------------------------------------------------------------------


class TestGetSiblingBranch:
    def test_if_image_then_to_else(self):
        then = [{"type": "key", "key": "t"}]
        else_ = [{"type": "key", "key": "e"}]
        parent_if = {"type": "if_image", "then": then, "else": else_}
        mw = FakeMainWindow(flat_steps=[parent_if])
        assert MainWindow.get_sibling_branch(mw, then, 1) is else_

    def test_if_image_else_to_then(self):
        then = [{"type": "key", "key": "t"}]
        else_ = [{"type": "key", "key": "e"}]
        parent_if = {"type": "if_image", "then": then, "else": else_}
        mw = FakeMainWindow(flat_steps=[parent_if])
        assert MainWindow.get_sibling_branch(mw, else_, -1) is then

    def test_if_any_image_next(self):
        a = [{"type": "key", "key": "a"}]
        b = [{"type": "key", "key": "b"}]
        c = [{"type": "key", "key": "c"}]
        parent = {"type": "if_any_image", "branches": {"a": a, "b": b, "c": c}}
        mw = FakeMainWindow(flat_steps=[parent])
        assert MainWindow.get_sibling_branch(mw, a, 1) is b
        assert MainWindow.get_sibling_branch(mw, b, 1) is c

    def test_if_any_image_prev(self):
        a = [{"type": "key", "key": "a"}]
        b = [{"type": "key", "key": "b"}]
        parent = {"type": "if_any_image", "branches": {"a": a, "b": b}}
        mw = FakeMainWindow(flat_steps=[parent])
        assert MainWindow.get_sibling_branch(mw, b, -1) is a

    def test_if_any_image_boundary(self):
        a = [{"type": "key", "key": "a"}]
        b = [{"type": "key", "key": "b"}]
        parent = {"type": "if_any_image", "branches": {"a": a, "b": b}}
        mw = FakeMainWindow(flat_steps=[parent])
        assert MainWindow.get_sibling_branch(mw, a, -1) is None
        assert MainWindow.get_sibling_branch(mw, b, 1) is None

    def test_grid_nav_row_to_col(self):
        row = [{"type": "key", "key": "r"}]
        col = [{"type": "key", "key": "c"}]
        parent = {"type": "grid_nav", "on_next_row": row, "on_next_col": col}
        mw = FakeMainWindow(flat_steps=[parent])
        assert MainWindow.get_sibling_branch(mw, row, 1) is col

    def test_grid_nav_col_to_row(self):
        row = [{"type": "key", "key": "r"}]
        col = [{"type": "key", "key": "c"}]
        parent = {"type": "grid_nav", "on_next_row": row, "on_next_col": col}
        mw = FakeMainWindow(flat_steps=[parent])
        assert MainWindow.get_sibling_branch(mw, col, -1) is row

    def test_no_match(self):
        mw = FakeMainWindow(flat_steps=[{"type": "key", "key": "a"}])
        orphan = [{"type": "key", "key": "x"}]
        assert MainWindow.get_sibling_branch(mw, orphan, 1) is None


# ---------------------------------------------------------------------------
# find_repeat_owner
# ---------------------------------------------------------------------------


class TestFindRepeatOwner:
    def test_finds_repeat(self):
        child_list = [{"type": "key", "key": "a"}]
        parent_list = [{"type": "delay", "ms": 100}]
        repeat = {"type": "repeat", "steps": child_list}
        mw = FakeMainWindow(flat_steps=[repeat], flat_parents=[parent_list])
        result = MainWindow.find_repeat_owner(mw, child_list)
        assert result is not None
        assert result[0] is repeat
        assert result[1] is parent_list

    def test_finds_if_image(self):
        then = [{"type": "key", "key": "t"}]
        parent_list = []
        if_step = {"type": "if_image", "then": then, "else": []}
        mw = FakeMainWindow(flat_steps=[if_step], flat_parents=[parent_list])
        result = MainWindow.find_repeat_owner(mw, then)
        assert result is not None
        assert result[0] is if_step

    def test_finds_if_any_image(self):
        branch = [{"type": "key", "key": "b"}]
        parent_list = []
        if_step = {"type": "if_any_image", "branches": {"a": branch}}
        mw = FakeMainWindow(flat_steps=[if_step], flat_parents=[parent_list])
        result = MainWindow.find_repeat_owner(mw, branch)
        assert result is not None
        assert result[0] is if_step

    def test_finds_grid_nav(self):
        row = [{"type": "key", "key": "r"}]
        parent_list = []
        grid = {"type": "grid_nav", "on_next_row": row, "on_next_col": []}
        mw = FakeMainWindow(flat_steps=[grid], flat_parents=[parent_list])
        result = MainWindow.find_repeat_owner(mw, row)
        assert result is not None
        assert result[0] is grid

    def test_not_found(self):
        mw = FakeMainWindow(flat_steps=[], flat_parents=[])
        assert MainWindow.find_repeat_owner(mw, []) is None


# ---------------------------------------------------------------------------
# template_label
# ---------------------------------------------------------------------------


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

    def test_fallback_flat_steps(self):
        child = {"type": "key", "key": "a"}
        repeat = {"type": "repeat", "skip": True, "steps": [child]}
        mw = FakeMainWindow(step_tree=None, flat_steps=[repeat])
        assert MainWindow.is_child_of_skipped_repeat(mw, child) is True

    def test_root_step(self):
        from step_tree import StepTree

        step = {"type": "key", "key": "a"}
        tree = StepTree([step])
        mw = FakeMainWindow(step_tree=tree, flat_steps=[])
        assert MainWindow.is_child_of_skipped_repeat(mw, step) is False
