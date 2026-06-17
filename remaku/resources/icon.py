from enum import Enum

from qfluentwidgets import FluentIconBase, Theme, getIconColor


class RemakuIcon(FluentIconBase, Enum):
    ARROW_DOWN = "arrow-down"
    ARROW_LEFT = "arrow-left"
    ARROW_UP = "arrow-up"
    CHEVRON_DOWN = "chevron-down"
    CHEVRON_RIGHT = "chevron-right"
    CHEVRONS_UP_DOWN = "chevrons-up-down"
    CLOCK = "clock"
    CORNER_DOWN_RIGHT = "corner-down-right"
    GIT_BRANCH = "git-branch"
    GRID_3X3 = "grid-3x3"
    HAND = "hand"
    IMAGE = "image"
    IMAGES = "images"
    INFO = "info"
    KEYBOARD = "keyboard"
    MOUSE_POINTER = "mouse-pointer"
    MOUSE_POINTER_CLICK = "mouse-pointer-click"
    PAUSE = "pause"
    PLAY = "play"
    PLUS = "plus"
    REDO = "redo-2"
    REPEAT = "repeat"
    SCAN_SEARCH = "scan-search"
    STOP = "stop"
    TRASH = "trash-2"
    UNDO = "undo-2"

    def path(self, theme=Theme.AUTO):
        return f":/remaku/icons/{self.value}-{getIconColor(theme)}.svg"
