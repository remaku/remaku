"""Icon helper module.

Provides a simple interface to load Lucide SVG icons as QIcon instances,
with automatic color adjustment based on the current theme.
"""

from pathlib import Path

from PySide6.QtCore import QByteArray, QRect, Qt
from PySide6.QtGui import QIcon, QIconEngine, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from qfluentwidgets import isDarkTheme

ICONS_DIR = Path(__file__).parent / "icons"


class SvgIconEngine(QIconEngine):
    """Icon engine that renders SVG at any requested size, resolving color at paint time."""

    def __init__(self, raw_svg: bytes) -> None:
        super().__init__()
        self.raw_svg = raw_svg

    def resolved_svg(self) -> bytes:
        color = "#ffffff" if isDarkTheme() else "#000000"
        return self.raw_svg.replace(b"currentColor", color.encode())

    def paint(self, painter: QPainter, rect: QRect, mode, state) -> None:
        renderer = QSvgRenderer(QByteArray(self.resolved_svg()))
        renderer.render(painter, rect.toRectF())

    def pixmap(self, size, mode, state) -> QPixmap:
        pixmap = QPixmap(size)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        self.paint(painter, QRect(0, 0, size.width(), size.height()), mode, state)
        painter.end()

        return pixmap

    def clone(self) -> "SvgIconEngine":
        return SvgIconEngine(self.raw_svg)


def icon(name: str) -> QIcon:
    """Load a Lucide SVG icon that auto-adapts color to the current theme."""
    path = ICONS_DIR / f"{name}.svg"
    raw_svg = path.read_bytes()

    return QIcon(SvgIconEngine(raw_svg))
