from remaku.views.home_view import HomeView


def test_home_view_creates_main_panels(qtbot) -> None:
    view = HomeView()
    qtbot.addWidget(view)

    assert view.objectName() == "home"
    assert view.toolbar is not None
    assert view.left_panel is not None
    assert view.center_panel is not None
    assert view.right_panel is not None
    assert view.status_label.text() == "Ready"


def test_home_view_updates_status_text(qtbot) -> None:
    view = HomeView()
    qtbot.addWidget(view)

    view.set_status_text("Running")

    assert view.status_label.text() == "Running"
