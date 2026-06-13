from qfluentwidgets import BodyLabel, MessageBoxBase, SubtitleLabel


class ConfirmDialog(MessageBoxBase):
    def __init__(self, title: str, content: str, parent=None):
        super().__init__(parent)

        self.title = title
        self.content = content
        self.init_ui()

    def init_ui(self) -> None:
        self.widget.setMinimumWidth(350)

        self.yesButton.setText(self.tr("OK"))
        self.cancelButton.setText(self.tr("Cancel"))

        self.viewLayout.addWidget(SubtitleLabel(self.title, self))
        self.viewLayout.addSpacing(4)
        self.viewLayout.addWidget(BodyLabel(self.content, self))
