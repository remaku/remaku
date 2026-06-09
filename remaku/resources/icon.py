from enum import Enum

from qfluentwidgets import FluentIconBase, Theme, getIconColor


class RemakuIcon(FluentIconBase, Enum):
    ARROW_DOWN = "arrow-down"
    ARROW_LEFT = "arrow-left"
    ARROW_UP = "arrow-up"
    CHEVRON_DOWN = "chevron-down"
    CHEVRON_RIGHT = "chevron-right"
    PAUSE = "pause"
    PLAY = "play"
    PLUS = "plus"
    REDO = "redo-2"
    TRASH = "trash-2"
    UNDO = "undo-2"

    def path(self, theme=Theme.AUTO):
        return f":/remaku/icons/{self.value}-{getIconColor(theme)}.svg"
