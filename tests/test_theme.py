from math import isclose

from remaku import theme


class FakeSignal:
    def __init__(self) -> None:
        self.callbacks = []

    def connect(self, callback) -> None:
        self.callbacks.append(callback)


class FakeQConfig:
    def __init__(self) -> None:
        self.themeChangedFinished = FakeSignal()


def assert_hsl(color, hue, saturation, lightness) -> None:
    color_hue, color_saturation, color_lightness, alpha = color.getHslF()

    assert isclose(color_hue, hue / 360, rel_tol=0.001)
    assert isclose(color_saturation, saturation, rel_tol=0.001)
    assert isclose(color_lightness, lightness, rel_tol=0.001)
    assert alpha == 1


def test_apply_theme_sets_light_theme_color(monkeypatch) -> None:
    calls = []
    fake_qconfig = FakeQConfig()
    monkeypatch.setattr(theme, "theme_color_sync_connected", False)
    monkeypatch.setattr(theme, "qconfig", fake_qconfig)
    monkeypatch.setattr(theme, "isDarkTheme", lambda: False)
    monkeypatch.setattr(theme, "setTheme", lambda value: calls.append(("theme", value)))
    monkeypatch.setattr(theme, "setThemeColor", lambda color: calls.append(("color", color)))

    theme.apply_theme("light")

    assert calls[0] == ("theme", theme.Theme.LIGHT)
    assert calls[1][0] == "color"
    assert_hsl(calls[1][1], 17.41, 0.8355, 0.5471)
    assert fake_qconfig.themeChangedFinished.callbacks == [theme.apply_theme_color]


def test_apply_theme_sets_dark_theme_color(monkeypatch) -> None:
    calls = []
    fake_qconfig = FakeQConfig()
    monkeypatch.setattr(theme, "theme_color_sync_connected", False)
    monkeypatch.setattr(theme, "qconfig", fake_qconfig)
    monkeypatch.setattr(theme, "isDarkTheme", lambda: True)
    monkeypatch.setattr(theme, "setTheme", lambda value: calls.append(("theme", value)))
    monkeypatch.setattr(theme, "setThemeColor", lambda color: calls.append(("color", color)))

    theme.apply_theme("dark")

    assert calls[0] == ("theme", theme.Theme.DARK)
    assert calls[1][0] == "color"
    assert_hsl(calls[1][1], 18.9, 1, 0.502)
    assert fake_qconfig.themeChangedFinished.callbacks == [theme.apply_theme_color]


def test_apply_theme_connects_theme_color_sync_once(monkeypatch) -> None:
    fake_qconfig = FakeQConfig()
    monkeypatch.setattr(theme, "theme_color_sync_connected", False)
    monkeypatch.setattr(theme, "qconfig", fake_qconfig)
    monkeypatch.setattr(theme, "isDarkTheme", lambda: False)
    monkeypatch.setattr(theme, "setTheme", lambda value: None)
    monkeypatch.setattr(theme, "setThemeColor", lambda color: None)

    theme.apply_theme("light")
    theme.apply_theme("system")

    assert fake_qconfig.themeChangedFinished.callbacks == [theme.apply_theme_color]
