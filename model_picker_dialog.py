from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class ModelPickerDialog(QDialog):
    def __init__(self, parent: QWidget, choices: list[tuple[str, str]], selected_value: str | None):
        super().__init__(parent)
        self.choices = [(label, value) for label, value in choices if value]
        self.selected_value = selected_value or ""
        self.setWindowTitle("选择 Whisper 模型")
        self.resize(460, 520)
        self.build_ui()
        self.populate_list()

    def build_ui(self) -> None:
        self.setStyleSheet("""
            QDialog {
                background: #ffffff;
                color: #172033;
            }
            QLabel {
                color: #172033;
                background: transparent;
            }
            QLineEdit {
                min-height: 26px;
                background: #ffffff;
                color: #172033;
                border: 1px solid #d8dee8;
                border-radius: 7px;
                padding: 8px 11px;
                selection-background-color: #2563eb;
            }
            QLineEdit:focus {
                border-color: #2563eb;
            }
            QListWidget {
                background: #ffffff;
                color: #172033;
                border: 1px solid #e2e8f0;
                border-radius: 7px;
                outline: none;
            }
            QListWidget::item {
                min-height: 30px;
                padding: 8px 10px;
                border-bottom: 1px solid #f1f5f9;
            }
            QListWidget::item:hover {
                background: #f3f6fa;
            }
            QListWidget::item:selected {
                background: #eaf2ff;
                color: #172033;
            }
            QPushButton {
                min-height: 24px;
                background: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 7px;
                padding: 8px 14px;
                font-weight: 600;
                color: #172033;
            }
            QPushButton:hover {
                background: #f3f6fa;
                border-color: #a9b6c7;
            }
            QPushButton#primaryButton {
                color: #ffffff;
                background: #2563eb;
                border-color: #2563eb;
            }
            QPushButton#primaryButton:hover {
                background: #1d4ed8;
                border-color: #1d4ed8;
            }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 16)
        layout.setSpacing(12)

        title = QLabel("选择模型")
        title.setStyleSheet("font-size: 16px; font-weight: 700; color: #172033;")
        layout.addWidget(title)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索模型名，例如 small、large、.en")
        self.search_input.textChanged.connect(self.populate_list)
        layout.addWidget(self.search_input)

        self.list_widget = QListWidget()
        self.list_widget.itemActivated.connect(self.accept_current_item)
        self.list_widget.currentItemChanged.connect(self.update_accept_button)
        layout.addWidget(self.list_widget, 1)

        hint = QLabel("中文内容请选择通用模型；英文内容可选择 .en 英文专用模型。")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #64748b; font-weight: 400;")
        layout.addWidget(hint)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel_button = QPushButton("取消")
        cancel_button.clicked.connect(self.reject)
        self.accept_button = QPushButton("选择")
        self.accept_button.setObjectName("primaryButton")
        self.accept_button.clicked.connect(self.accept_current_item)
        buttons.addWidget(cancel_button)
        buttons.addWidget(self.accept_button)
        layout.addLayout(buttons)

    def populate_list(self) -> None:
        keyword = self.search_input.text().strip().lower()
        current_value = self.current_value() or self.selected_value
        self.list_widget.clear()
        for label, value in self.choices:
            haystack = f"{label} {value}".lower()
            if keyword and keyword not in haystack:
                continue
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, value)
            item.setToolTip(value)
            self.list_widget.addItem(item)
            if value == current_value:
                self.list_widget.setCurrentItem(item)
        if self.list_widget.count() and self.list_widget.currentRow() < 0:
            self.list_widget.setCurrentRow(0)
        self.update_accept_button()

    def current_value(self) -> str:
        item = self.list_widget.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else ""

    def accept_current_item(self) -> None:
        if self.current_value():
            self.selected_value = self.current_value()
            self.accept()

    def update_accept_button(self) -> None:
        self.accept_button.setEnabled(bool(self.current_value()))
