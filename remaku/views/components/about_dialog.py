from qfluentwidgets import BodyLabel, MessageBoxBase, SubtitleLabel

from remaku.version import __version__


class AboutDialog(MessageBoxBase):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.init_ui()

    def init_ui(self):
        self.yesButton.setText(self.tr("Close"))
        self.cancelButton.hide()

        self.viewLayout.addWidget(SubtitleLabel(f"Remaku v{__version__}"))
        self.viewLayout.addSpacing(4)
        self.viewLayout.addWidget(
            BodyLabel(self.tr("Open-source, visual, image-recognition-driven desktop macro tool."))
        )

        links = BodyLabel(
            '<a href="https://github.com/remaku/remaku">GitHub</a> · '
            '<a href="https://discord.gg/MZfks29yTA">Discord</a> · '
            f'<a href="https://remaku.com">{self.tr("Website")}</a>'
        )
        links.setOpenExternalLinks(True)
        self.viewLayout.addWidget(links)

        email = BodyLabel('<a href="mailto:hello@remaku.com">hello@remaku.com</a>')
        email.setOpenExternalLinks(True)
        self.viewLayout.addWidget(email)

        self.viewLayout.addSpacing(8)

        self.viewLayout.addWidget(BodyLabel(self.tr("© 2026 Nelson Lai · AGPL-3.0")))

        sponsors = BodyLabel(
            '<a href="https://github.com/sponsors/nelsonlaidev">GitHub Sponsors</a> · '
            '<a href="https://buymeacoffee.com/nelsonlaidev">Buy Me A Coffee</a>'
        )
        sponsors.setOpenExternalLinks(True)
        self.viewLayout.addWidget(sponsors)
