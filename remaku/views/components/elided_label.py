from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QFontMetrics, QPainter
from PySide6.QtWidgets import QSizePolicy
from qfluentwidgets import BodyLabel, CaptionLabel, StrongBodyLabel, SubtitleLabel, TitleLabel


def create_elided_label(LabelClass):
    class ElidedFluentLabel(LabelClass):
        def __init__(self, text: str = "", parent=None):
            super().__init__(text, parent) if parent else super().__init__(text)

            self.text_content = text
            self._elide_mode = Qt.TextElideMode.ElideRight

            self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)

        def setElideMode(self, mode):
            self._elide_mode = mode
            self.update()

        def elideMode(self):
            return self._elide_mode

        def setText(self, text: str):
            self.text_content = text
            super().setText(text)
            self.updateGeometry()
            self.update()

        def sizeHint(self):
            metrics = QFontMetrics(self.font())
            return metrics.size(Qt.TextFlag.TextSingleLine, self.text_content)

        def minimumSizeHint(self) -> QSize:
            metrics = QFontMetrics(self.font())
            return QSize(0, metrics.height())

        def paintEvent(self, event):
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            text_color = self.palette().color(self.foregroundRole())
            painter.setPen(text_color)

            metrics = QFontMetrics(self.font())
            draw_rect = self.contentsRect()
            elided_text = metrics.elidedText(self.text_content, self.elideMode(), draw_rect.width())

            painter.drawText(draw_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, elided_text)

    return ElidedFluentLabel


ElidedBodyLabel = create_elided_label(BodyLabel)
ElidedSubtitleLabel = create_elided_label(SubtitleLabel)
ElidedTitleLabel = create_elided_label(TitleLabel)
ElidedCaptionLabel = create_elided_label(CaptionLabel)
ElidedStrongBodyLabel = create_elided_label(StrongBodyLabel)
