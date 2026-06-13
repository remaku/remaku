from qfluentwidgets import BodyLabel, LineEdit, MessageBoxBase, SubtitleLabel


class RenameMacroDialog(MessageBoxBase):
    def __init__(self, parent=None, current_label: str = "") -> None:
        super().__init__(parent)

        self.current_label = current_label
        self.label_edit: LineEdit | None = None
        self.init_ui()

    def init_ui(self) -> None:
        self.widget.setMinimumWidth(350)

        self.yesButton.setText(self.tr("Save"))
        self.cancelButton.setText(self.tr("Cancel"))

        self.viewLayout.addWidget(SubtitleLabel(self.tr("Rename Macro"), self))
        self.viewLayout.addSpacing(4)

        label = BodyLabel(self.tr("New Name"), self)
        self.viewLayout.addWidget(label)

        self.label_edit = LineEdit(self)
        self.label_edit.setText(self.current_label)
        self.label_edit.setClearButtonEnabled(True)
        self.viewLayout.addWidget(self.label_edit)
        self.label_edit.setFocus()
        self.label_edit.selectAll()

    def value(self) -> str:
        if self.label_edit is None:
            return ""

        return self.label_edit.text().strip()
