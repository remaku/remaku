from PySide6.QtGui import QColor
from qfluentwidgets import Theme, isDarkTheme, qconfig, setTheme, setThemeColor

THEME_MAP = {
    "light": Theme.LIGHT,
    "dark": Theme.DARK,
    "system": Theme.AUTO,
}

LIGHT_THEME_COLOR = QColor.fromHslF(17.41 / 360, 0.8355, 0.5471)
DARK_THEME_COLOR = QColor.fromHslF(18.9 / 360, 1, 0.502)

theme_color_sync_connected = False


def apply_theme_color():
    setThemeColor(DARK_THEME_COLOR if isDarkTheme() else LIGHT_THEME_COLOR)


def connect_theme_color_sync():
    global theme_color_sync_connected

    if theme_color_sync_connected:
        return

    qconfig.themeChangedFinished.connect(apply_theme_color)
    theme_color_sync_connected = True


def apply_theme(theme_name):
    setTheme(THEME_MAP.get(theme_name, Theme.AUTO))
    connect_theme_color_sync()
    apply_theme_color()
