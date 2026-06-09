from PySide6.QtCore import QObject, Signal


class EventBus(QObject):
    action_triggered = Signal(str)
    macro_selected = Signal(str)
    macro_rename_requested = Signal(str)
    macro_delete_requested = Signal(str)
    macro_duplicate_requested = Signal(str)
    step_selected = Signal(object)
    branch_selected = Signal(object, str)
    template_capture_requested = Signal(str)
    template_pick_requested = Signal(str)
    template_delete_requested = Signal(str)
    template_add_requested = Signal()
    step_add_requested = Signal(str)


event_bus = EventBus()
