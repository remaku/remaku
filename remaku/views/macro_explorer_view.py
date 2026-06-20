from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFormLayout, QHBoxLayout, QListWidgetItem, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    CardWidget,
    ComboBox,
    LineEdit,
    ListWidget,
    PushButton,
    SubtitleLabel,
    TitleLabel,
)

from remaku.models.config_model import config_model
from remaku.models.pack_model import PackCatalogEntry, PackListItem, PackStatus
from remaku.services import pack_service


class MacroExplorerView(QWidget):
    pack_selected = Signal(str)
    import_requested = Signal(str, str)
    search_changed = Signal(str)
    game_filter_changed = Signal(str)
    compatibility_filter_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setObjectName("macro_explorer")
        self.items: list[PackListItem] = []
        self.current_pack_id = ""
        self.current_pack_status: PackStatus = "available"
        self.current_pack_language = ""
        self.preferred_pack_language = ""
        self.importing = False

        self.init_ui()

    def init_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        title = TitleLabel(self.tr("Macro Explorer"), self)
        root.addWidget(title)

        filter_card = CardWidget(self)
        filter_layout = QHBoxLayout(filter_card)
        filter_layout.setContentsMargins(12, 12, 12, 12)
        filter_layout.setSpacing(8)

        self.search_edit = LineEdit(filter_card)
        self.search_edit.setPlaceholderText(self.tr("Search packs"))
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self.search_changed.emit)
        filter_layout.addWidget(self.search_edit, 1)

        self.game_filter = ComboBox(filter_card)
        self.game_filter.currentIndexChanged.connect(self.handle_game_filter_changed)
        filter_layout.addWidget(self.game_filter)

        self.compatibility_filter = ComboBox(filter_card)
        self.compatibility_filter.addItem(self.tr("All compatibility"), userData="all")
        self.compatibility_filter.addItem(self.tr("Compatible"), userData="compatible")
        self.compatibility_filter.addItem(self.tr("Incompatible"), userData="incompatible")
        self.compatibility_filter.currentIndexChanged.connect(self.handle_compatibility_filter_changed)
        filter_layout.addWidget(self.compatibility_filter)

        root.addWidget(filter_card)

        content = QHBoxLayout()
        content.setSpacing(12)
        root.addLayout(content, 1)

        self.list_card = CardWidget(self)
        self.list_card.setMinimumWidth(260)
        self.list_card.setMaximumWidth(360)
        list_layout = QVBoxLayout(self.list_card)
        list_layout.setContentsMargins(12, 12, 12, 12)
        list_layout.setSpacing(8)

        list_title = SubtitleLabel(self.tr("Packs"), self.list_card)
        list_layout.addWidget(list_title)

        self.pack_list = ListWidget(self.list_card)
        self.pack_list.itemSelectionChanged.connect(self.handle_selection_changed)
        list_layout.addWidget(self.pack_list, 1)

        self.empty_label = BodyLabel(self.tr("No packs found"), self.list_card)
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setWordWrap(True)
        list_layout.addWidget(self.empty_label, 1)

        content.addWidget(self.list_card)

        self.detail_card = CardWidget(self)
        detail_layout = QVBoxLayout(self.detail_card)
        detail_layout.setContentsMargins(12, 12, 12, 12)
        detail_layout.setSpacing(10)

        self.name_label = SubtitleLabel(self.tr("Select a pack"), self.detail_card)
        detail_layout.addWidget(self.name_label)

        detail_content = QVBoxLayout()
        detail_content.setSpacing(24)
        detail_layout.addLayout(detail_content)

        self.description_label = BodyLabel(self.tr("Choose a pack from the list to view details."), self.detail_card)
        self.description_label.setWordWrap(True)
        detail_content.addWidget(self.description_label)

        self.status_label = BodyLabel("", self.detail_card)
        self.status_label.setWordWrap(True)
        self.status_label.hide()
        detail_content.addWidget(self.status_label)

        self.detail_form = QFormLayout()
        self.detail_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        self.detail_form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.detail_form.setHorizontalSpacing(24)
        self.detail_form.setVerticalSpacing(8)
        detail_content.addLayout(self.detail_form)

        self.info_labels: dict[str, BodyLabel] = {}
        for key, label in self.info_fields():
            key_label = BodyLabel(label, self.detail_card)
            value_label = BodyLabel("", self.detail_card)
            value_label.setWordWrap(True)
            self.detail_form.addRow(key_label, value_label)
            self.info_labels[key] = value_label

        self.language_label = BodyLabel(self.tr("Language"), self.detail_card)
        self.language_combo = ComboBox(self.detail_card)
        self.language_combo.currentIndexChanged.connect(self.handle_language_changed)
        self.detail_form.addRow(self.language_label, self.language_combo)

        button_row = QHBoxLayout()
        button_row.setSpacing(8)

        self.import_button = PushButton(self.tr("Import Macro"), self.detail_card)
        self.import_button.clicked.connect(
            lambda: self.import_requested.emit(self.current_pack_id, self.current_pack_language)
        )
        button_row.addWidget(self.import_button)

        detail_content.addLayout(button_row)
        detail_layout.addStretch()
        content.addWidget(self.detail_card, 1)

        self.set_pack_items([])
        self.clear_detail()

    def info_fields(self) -> list[tuple[str, str]]:
        return [
            ("game", self.tr("Game")),
            ("author", self.tr("Author")),
            ("compatibility", self.tr("Compatibility")),
        ]

    def set_info_values(self, values: dict[str, str]) -> None:
        for key, label in self.info_labels.items():
            label.setText(values.get(key, ""))

    def clear_info_values(self) -> None:
        self.set_info_values({})

    def set_loading(self) -> None:
        self.set_status_text(self.tr("Loading packs..."))

    def set_status_text(self, text: str) -> None:
        self.status_label.setText(text)
        self.status_label.setVisible(bool(text))

    def set_importing(self, importing: bool) -> None:
        self.importing = importing
        self.update_buttons(self.current_pack_status, has_selection=bool(self.current_pack_id))

    def set_filter_options(self, games: list[tuple[str, str]]) -> None:
        self.update_filter(self.game_filter, self.tr("All games"), games)

    def update_filter(self, combo: ComboBox, all_label: str, values: list[tuple[str, str]]) -> None:
        current_value = combo.currentData() or "all"
        combo.blockSignals(True)
        combo.clear()
        combo.addItem(all_label, userData="all")

        for value, label in values:
            combo.addItem(label, userData=value)

        index = combo.findData(current_value)
        combo.setCurrentIndex(index if index >= 0 else 0)
        combo.blockSignals(False)

    def current_filter_value(self, combo: ComboBox) -> str:
        value = combo.currentData()
        return str(value) if value else "all"

    def current_language_value(self) -> str:
        value = self.language_combo.currentData()
        return str(value) if value else ""

    def handle_game_filter_changed(self) -> None:
        self.game_filter_changed.emit(self.current_filter_value(self.game_filter))

    def handle_compatibility_filter_changed(self) -> None:
        self.compatibility_filter_changed.emit(self.current_filter_value(self.compatibility_filter))

    def handle_language_changed(self) -> None:
        self.current_pack_language = self.current_language_value()
        if self.current_pack_language:
            self.preferred_pack_language = self.current_pack_language

    def set_pack_items(self, items: list[PackListItem], selected_pack_id: str = "") -> None:
        self.items = items
        self.pack_list.clear()
        selected_item: QListWidgetItem | None = None

        for item in items:
            list_item = QListWidgetItem(self.item_label(item))
            list_item.setData(Qt.ItemDataRole.UserRole, item.entry.pack_id)
            self.pack_list.addItem(list_item)

            if item.entry.pack_id == selected_pack_id:
                selected_item = list_item

        if selected_item is not None:
            self.pack_list.setCurrentItem(selected_item)
        elif self.pack_list.count() > 0:
            self.pack_list.setCurrentRow(0)
        else:
            self.clear_detail()

        self.update_empty_state()

    def item_label(self, item: PackListItem) -> str:
        if item.status == "incompatible":
            return f"{self.localized_label(item.entry)} ({self.status_text(item.status)})"

        return self.localized_label(item.entry)

    def current_language(self) -> str:
        return config_model.config.general.language

    def localized_label(self, entry: PackCatalogEntry) -> str:
        return entry.display_label(self.current_language())

    def localized_description(self, entry: PackCatalogEntry) -> str:
        return entry.display_description(self.current_language())

    def status_text(self, status: PackStatus) -> str:
        labels = {
            "available": self.tr("Available"),
            "incompatible": self.tr("Incompatible"),
        }
        return labels[status]

    def update_empty_state(self) -> None:
        has_items = self.pack_list.count() > 0
        self.pack_list.setVisible(has_items)
        self.empty_label.setVisible(not has_items)

    def handle_selection_changed(self) -> None:
        item = self.pack_list.currentItem()
        if item is None:
            return

        pack_id = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(pack_id, str):
            self.pack_selected.emit(pack_id)

    def set_selected_pack(self, item: PackListItem | None) -> None:
        if item is None:
            self.clear_detail()
            return

        self.current_pack_id = item.entry.pack_id
        self.current_pack_status = item.status
        self.update_language_options(item.entry, self.preferred_pack_language)
        self.name_label.setText(self.localized_label(item.entry))
        self.set_info_values(self.info_values(item))
        self.description_label.setText(self.localized_description(item.entry))
        self.set_status_text("")
        self.update_buttons(item.status)

    def clear_detail(self) -> None:
        self.current_pack_id = ""
        self.current_pack_status = "available"
        self.current_pack_language = ""
        self.name_label.setText(self.tr("Select a pack"))
        self.clear_language_options()
        self.clear_info_values()
        self.description_label.setText(self.tr("Choose a pack from the list to view details."))
        self.set_status_text("")
        self.update_buttons("available", has_selection=False)

    def update_language_options(self, entry: PackCatalogEntry, preferred_language: str = "") -> None:
        options = pack_service.pack_language_options(entry)
        selected_language = pack_service.resolve_pack_language(entry, preferred_language, self.current_language())
        has_options = bool(options)

        self.language_combo.blockSignals(True)
        self.language_combo.clear()

        for language, label in options:
            self.language_combo.addItem(label, userData=language)

        index = self.language_combo.findData(selected_language)
        self.language_combo.setCurrentIndex(index if index >= 0 else 0)
        self.language_combo.blockSignals(False)
        self.current_pack_language = self.current_language_value()
        self.language_label.setVisible(has_options)
        self.language_combo.setVisible(has_options)

    def clear_language_options(self) -> None:
        self.language_combo.blockSignals(True)
        self.language_combo.clear()
        self.language_combo.blockSignals(False)
        self.language_label.hide()
        self.language_combo.hide()

    def info_values(self, item: PackListItem) -> dict[str, str]:
        return {
            "game": item.game_label,
            "author": item.entry.author,
            "compatibility": self.compatibility_text(item.entry),
        }

    def compatibility_text(self, entry: PackCatalogEntry) -> str:
        minimum = entry.compatibility.remaku_min
        maximum = entry.compatibility.remaku_max

        if minimum and maximum:
            return self.tr("Requires Remaku {minimum} to {maximum}").format(minimum=minimum, maximum=maximum)

        if minimum:
            return self.tr("Requires Remaku {minimum} or newer").format(minimum=minimum)

        if maximum:
            return self.tr("Requires Remaku {maximum} or older").format(maximum=maximum)

        return self.tr("Compatible")

    def update_buttons(self, status: PackStatus, has_selection: bool = True) -> None:
        self.import_button.setEnabled(has_selection and status == "available" and not self.importing)
