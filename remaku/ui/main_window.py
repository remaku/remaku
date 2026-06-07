from qfluentwidgets import FluentWindow
from remaku.ui.pages.home import HomePage


class MainWindow(FluentWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Remaku")
        self.setMinimumSize(900, 600)
        self.resize(900, 600)
        self.reset_navigation_interface()

        self.addSubInterface(HomePage(), "", "")

    def reset_navigation_interface(self):
        # self.navigationInterface.setVisible(False)
        pass
