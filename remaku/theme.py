from qfluentwidgets import Theme, setTheme

THEME_MAP = {
    "light": Theme.LIGHT,
    "dark": Theme.DARK,
    "system": Theme.AUTO,
}


def apply_theme(theme_name):
    setTheme(THEME_MAP.get(theme_name, Theme.AUTO))
