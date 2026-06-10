from PySide6.QtCore import QObject, Signal


class EventBus(QObject):
    switch_page_requested = Signal(str)
    overlay_toggled = Signal()
    overlay_position_changed = Signal(int, int)
    check_updates_requested = Signal()
    settings_changed = Signal()
    clipboard_changed = Signal(bool)
    action_triggered = Signal(str)
    new_macro_requested = Signal()
    macro_selected = Signal(str)
    macro_rename_requested = Signal(str)
    macro_delete_requested = Signal(str)
    macro_duplicate_requested = Signal(str)
    macro_running_changed = Signal(bool)
    step_selected = Signal(object)
    branch_selected = Signal(object, str)
    template_capture_requested = Signal(str)
    template_pick_requested = Signal(str)
    template_delete_requested = Signal(str)
    template_add_requested = Signal()
    step_add_requested = Signal(str)
    show_toolbar_step_menu_requested = Signal()
    macro_meta_changed = Signal(str, str)
    step_property_changed = Signal(str, str)
    template_meta_changed = Signal(str, str, str)


event_bus = EventBus()
