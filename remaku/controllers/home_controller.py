import webbrowser

from remaku.ui.components.about_dialog import AboutDialog
from remaku.ui.pages.home import HomePage


class HomeController:
    def __init__(self, view: HomePage):
        self.view = view
        self.view.toolbar.actionTriggered.connect(self.handle_toolbar_action)

    def handle_toolbar_action(self, action_id: str):
        print(f"Toolbar action triggered: {action_id}")

        if action_id == "about":
            about_dialog = AboutDialog(self.view)
            about_dialog.exec()

        if action_id == "support_author":
            webbrowser.open("https://github.com/sponsors/nelsonlaidev")
