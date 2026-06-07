#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
import time
from pathlib import Path

from PySide6.QtCore import QEvent, QObject, QThread, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QDesktopServices, QFont, QFontDatabase
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QProgressBar,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QStyle,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import QUrl

from env_checker import (
    build_env_summary,
    format_env_report,
)
from model_config import (
    MISSING_WHISPER_MODEL_MESSAGE,
    MODELS_DIR,
    get_model_choices,
    get_model_description,
    is_local_model_choice,
    is_preset_model,
    is_valid_model_dir,
    resolve_model_from_settings,
    resolve_preset_model_for_extract,
    resolve_selected_model,
    scan_deployed_models,
)
from settings_manager import (
    DEFAULT_OUTPUT_DIR,
    build_settings_payload,
    load_settings as read_settings,
    save_settings as write_settings,
    selected_output_dir as get_selected_output_dir,
)
from workers import EnvWorker, ExtractWorker, ModelDeployWorker


ROOT = Path(__file__).resolve().parent

COOKIE_MODES = [
    {"name": "none", "label": "不使用 Cookies"},
    {"name": "browser", "label": "从浏览器读取"},
    {"name": "file", "label": "使用 cookies.txt 文件"},
]
COOKIE_BROWSERS = ["chrome", "edge", "firefox"]


def timestamp() -> str:
    return time.strftime("%H:%M:%S")


ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def clean_log_text(message: str) -> str:
    return ANSI_RE.sub("", message)


def configure_app_font(app: QApplication) -> None:
    families = set(QFontDatabase.families())
    preferred = [
        "Noto Sans CJK SC",
        "Noto Sans CJK",
        "Microsoft YaHei UI",
        "Microsoft YaHei",
        "SimHei",
        "WenQuanYi Micro Hei",
        "Source Han Sans SC",
    ]
    for family in preferred:
        if family in families:
            app.setFont(QFont(family, 10))
            return


class NoWheelComboBox(QComboBox):
    """Ignore wheel changes while the popup is closed so page scrolling keeps working."""

    def __init__(self):
        super().__init__()
        self.setView(QListView())
        self.view().setStyleSheet("""
            QListView {
                background: #ffffff;
                color: #172033;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 4px;
                outline: none;
                selection-background-color: #eaf2ff;
                selection-color: #172033;
            }
            QListView::item {
                min-height: 28px;
                padding: 6px 10px;
                color: #172033;
                background: #ffffff;
            }
            QListView::item:hover {
                background: #f3f6fa;
                color: #172033;
            }
            QListView::item:selected {
                background: #eaf2ff;
                color: #172033;
            }
        """)

    def wheelEvent(self, event) -> None:
        if self.view().isVisible():
            super().wheelEvent(event)
            return
        event.ignore()


class ClickablePathBox(QFrame):
    clicked = Signal()

    def __init__(self):
        super().__init__()
        self.full_path = ""
        self.setObjectName("pathBox")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(38)
        self.setStyleSheet("""
            QFrame#pathBox {
                background: #f9fbfd;
                border: 1px solid #e1e7ef;
                border-radius: 7px;
            }
            QFrame#pathBox:hover {
                background: #f1f7ff;
                border-color: #b7d4f6;
            }
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 7, 10, 7)
        layout.setSpacing(8)
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(20, 20)
        self.path_label = QLabel("点击修改路径")
        self.path_label.setWordWrap(False)
        self.path_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.path_label.setStyleSheet("color: #253244; font-weight: 400;")
        self.edit_label = QLabel("修改")
        self.edit_label.setStyleSheet("color: #2563eb; font-weight: 500;")
        for label in (self.icon_label, self.path_label, self.edit_label):
            label.setCursor(Qt.CursorShape.PointingHandCursor)
            label.installEventFilter(self)
        layout.addWidget(self.icon_label, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.path_label, 1, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.edit_label, 0, Qt.AlignmentFlag.AlignVCenter)

    def eventFilter(self, watched, event) -> bool:
        if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            return True
        return super().eventFilter(watched, event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def set_icon(self, icon) -> None:
        self.icon_label.setPixmap(icon.pixmap(16, 16))

    def set_path(self, path: str) -> None:
        self.full_path = path or "未检测到路径，点击手动指定"
        self.setToolTip(self.full_path)
        self.update_elided_path()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.update_elided_path()

    def update_elided_path(self) -> None:
        if not self.full_path:
            return
        metrics = self.path_label.fontMetrics()
        self.path_label.setText(metrics.elidedText(
            self.full_path,
            Qt.TextElideMode.ElideMiddle,
            max(80, self.path_label.width()),
        ))


class QuickConfigCard(QFrame):
    clicked = Signal()

    def __init__(self, clickable: bool = False):
        super().__init__()
        self.clickable = clickable
        self.setObjectName("statusCard")
        self.setMinimumHeight(74)
        if clickable:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.apply_style()

    def apply_style(self) -> None:
        hover = """
            QFrame#statusCard:hover {
                background: #f8fbff;
                border-color: #bfdbfe;
            }
        """ if self.clickable else ""
        self.setStyleSheet(f"""
            QFrame#statusCard {{
                background: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
            }}
            {hover}
        """)

    def mousePressEvent(self, event) -> None:
        if self.clickable and event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def keyPressEvent(self, event) -> None:
        if self.clickable and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.clicked.emit()
            return
        super().keyPressEvent(event)

    def eventFilter(self, watched, event) -> bool:
        if (
            self.clickable
            and event.type() == QEvent.Type.MouseButtonPress
            and event.button() == Qt.MouseButton.LeftButton
        ):
            self.clicked.emit()
            return True
        return super().eventFilter(watched, event)

    def add_click_target(self, widget: QWidget) -> None:
        if self.clickable:
            widget.setCursor(Qt.CursorShape.PointingHandCursor)
            widget.installEventFilter(self)


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


class ToolStatusCard(QFrame):
    def __init__(self, tool_name: str, path_icon, show_version: bool = True):
        super().__init__()
        self.show_version = show_version
        self.setObjectName("toolStatusCard")
        self.setStyleSheet("""
            QFrame#toolStatusCard {
                background: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
            }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(8)
        self.status_dot = QLabel()
        self.status_dot.setFixedSize(10, 10)
        self.name_label = QLabel(tool_name)
        self.name_label.setStyleSheet("font-size: 14px; font-weight: 600; color: #172033;")
        self.status_label = QLabel("未检查")
        self.status_label.setStyleSheet("""
            color: #475569;
            background: #f1f5f9;
            border-radius: 7px;
            padding: 2px 8px;
            font-weight: 500;
        """)
        header.addWidget(self.status_dot)
        header.addWidget(self.name_label, 1)
        header.addWidget(self.status_label)
        layout.addLayout(header)

        meta = QHBoxLayout()
        meta.setSpacing(8)
        self.source_label = QLabel("来源：未知")
        self.version_label = QLabel("版本：未知")
        for label in (self.source_label, self.version_label):
            label.setStyleSheet("color: #64748b; font-weight: 400;")
            label.setWordWrap(True)
        meta.addWidget(self.source_label, 1)
        if self.show_version:
            meta.addWidget(self.version_label, 1)
        else:
            self.version_label.hide()
        layout.addLayout(meta)

        self.path_box = ClickablePathBox()
        self.path_box.set_icon(path_icon)
        layout.addWidget(self.path_box)

    def update_status(self, data: dict | None) -> None:
        if not data:
            status = "检测失败"
            color = "#dc2626"
            source = "未知"
            version = "未知"
            path = ""
        else:
            ok = bool(data.get("ok"))
            status = "已可用" if ok else "未找到"
            color = "#16a34a" if ok else "#dc2626"
            source = data.get("source") or "未知"
            version = data.get("version") or "未知"
            path = data.get("path") or ""
        self.status_dot.setStyleSheet(f"background: {color}; border-radius: 6px;")
        self.status_label.setText(status)
        self.status_label.setStyleSheet(f"""
            color: {color};
            background: {'#dcfce7' if color == '#16a34a' else '#fee2e2'};
            border-radius: 7px;
            padding: 2px 8px;
            font-weight: 500;
        """)
        self.source_label.setText(f"来源：{source}")
        if self.show_version:
            self.version_label.setText(f"版本：{version}")
        self.path_box.set_path(path)

    def set_pending(self, status: str) -> None:
        self.status_dot.setStyleSheet("background: #94a3b8; border-radius: 5px;")
        self.status_label.setText(status)
        self.status_label.setStyleSheet("""
            color: #475569;
            background: #f1f5f9;
            border-radius: 7px;
            padding: 2px 8px;
            font-weight: 500;
        """)
        self.source_label.setText("来源：检测中")
        if self.show_version:
            self.version_label.setText("版本：检测中")
        self.path_box.set_path("")


class AdvancedSettingsDialog(QDialog):
    def __init__(self, main_window: "MainWindow"):
        super().__init__(main_window)
        self.main_window = main_window
        self.thread: QThread | None = None
        self.worker: QObject | None = None
        self.syncing_model_run = False
        self.syncing_cookies = False
        self.env_report: dict = {}
        self.setWindowTitle("高级设置")
        self.resize(840, 540)
        self.setModal(False)
        self.build_ui()
        self.connect_model_run_sync()
        self.connect_cookie_access_sync()
        QTimer.singleShot(0, self.run_detection)

    def build_ui(self) -> None:
        self.setStyleSheet("""
            QDialog {
                background: #f6f8fb;
                color: #17202c;
            }
            QLabel {
                color: #17202c;
                background: transparent;
            }
            QPushButton {
                min-height: 22px;
                background: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 12px;
                font-weight: 500;
                color: #172033;
            }
            QPushButton:hover {
                background: #f3f6fa;
                border-color: #a9b6c7;
                color: #172033;
            }
            QPushButton:pressed {
                background: #e8eef6;
                color: #172033;
            }
            QPushButton:disabled {
                color: #97a3b3;
                background: #edf1f5;
                border-color: #dbe2ea;
            }
            QTabWidget::pane {
                border: 1px solid #e2e8f0;
                border-radius: 7px;
                background: #ffffff;
                top: -1px;
            }
            QTabBar::tab {
                background: #f1f5f9;
                color: #475569;
                border: 1px solid #d8dee8;
                border-bottom: none;
                padding: 8px 14px;
                margin-right: 4px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                font-weight: 500;
            }
            QTabBar::tab:selected {
                background: #ffffff;
                color: #172033;
            }
            QPushButton#smallSecondaryButton {
                min-height: 20px;
                padding: 5px 10px;
                font-weight: 500;
            }
            QPushButton#linkButton {
                min-height: 20px;
                padding: 4px 2px;
                color: #2563eb;
                background: transparent;
                border: none;
                font-weight: 400;
                text-align: left;
            }
            QPushButton#linkButton:hover {
                color: #1d4ed8;
                background: transparent;
                text-decoration: underline;
            }
            QComboBox, QLineEdit {
                min-height: 24px;
                background: #ffffff;
                color: #172033;
                border: 1px solid #d8dee8;
                border-radius: 7px;
                padding: 7px 10px;
                selection-background-color: #2563eb;
            }
            QComboBox:focus, QLineEdit:focus {
                border-color: #2563eb;
            }
            QComboBox QAbstractItemView {
                background: #ffffff;
                color: #172033;
                selection-background-color: #eaf2ff;
                selection-color: #172033;
            }
        """)
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 16)
        root.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("高级设置")
        title_font = title.font()
        title_font.setPointSize(17)
        title_font.setWeight(QFont.Weight.DemiBold)
        title.setFont(title_font)
        title.setStyleSheet("color: #172033; font-weight: 600;")
        header.addWidget(title, 1)
        root.addLayout(header)

        self.tabs = QTabWidget()
        self.tabs.addTab(self.build_environment_tab(), "环境与工具")
        self.tabs.addTab(self.build_model_run_tab(), "模型与运行")
        self.tabs.addTab(self.build_cookie_access_tab(), "Cookies 与访问")
        root.addWidget(self.tabs, 1)

        footer = QHBoxLayout()
        hint = QLabel("设置会自动保存")
        hint.setStyleSheet("color: #64748b; font-weight: 400;")
        footer.addWidget(hint, 1)
        root.addLayout(footer)

    def build_environment_tab(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("QWidget { background: #ffffff; }")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(16)

        left = QVBoxLayout()
        left.setSpacing(10)
        tools_header = QHBoxLayout()
        tools_header.setContentsMargins(0, 0, 0, 0)
        tools_header.setSpacing(10)
        tools_title = QLabel("工具状态")
        tools_title.setStyleSheet("font-size: 14px; font-weight: 600; color: #172033;")
        self.update_tools_button = QPushButton("更新 yt-dlp")
        self.redetect_button = QPushButton("重新检测")
        self.restore_button = QPushButton("恢复使用内置工具")
        self.update_tools_button.setObjectName("smallSecondaryButton")
        self.redetect_button.setObjectName("smallSecondaryButton")
        self.restore_button.setObjectName("linkButton")
        self.restore_button.setFlat(True)
        self.restore_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update_tools_button.clicked.connect(self.update_tools)
        self.redetect_button.clicked.connect(self.run_detection)
        self.restore_button.clicked.connect(self.restore_builtin_tools)
        tools_header.addWidget(tools_title, 1)
        tools_header.addWidget(self.redetect_button)
        left.addLayout(tools_header)

        self.ffmpeg_card = ToolStatusCard("FFmpeg", self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon), show_version=False)
        self.ytdlp_card = ToolStatusCard("yt-dlp", self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon))
        self.ffmpeg_card.path_box.clicked.connect(lambda: self.choose_tool_path("ffmpeg"))
        self.ytdlp_card.path_box.clicked.connect(lambda: self.choose_tool_path("yt_dlp"))
        left.addWidget(self.ffmpeg_card)
        left.addWidget(self.ytdlp_card)

        light_actions = QHBoxLayout()
        light_actions.setContentsMargins(2, 2, 0, 0)
        light_actions.setSpacing(12)
        light_actions.addWidget(self.restore_button, 0, Qt.AlignmentFlag.AlignLeft)
        light_actions.addStretch(1)
        light_actions.addWidget(self.update_tools_button, 0, Qt.AlignmentFlag.AlignRight)
        left.addLayout(light_actions)
        left.addStretch(1)
        content_layout.addLayout(left, 3)

        notes = QFrame()
        notes.setObjectName("notesPanel")
        notes.setStyleSheet("""
            QFrame#notesPanel {
                background: #f9fbfd;
                border: 1px solid #e2e8f0;
                border-radius: 7px;
            }
        """)
        notes_layout = QVBoxLayout(notes)
        notes_layout.setContentsMargins(15, 14, 15, 14)
        notes_layout.setSpacing(9)
        notes_title = QLabel("说明")
        notes_title.setStyleSheet("font-size: 14px; font-weight: 600; color: #172033;")
        notes_body = QLabel(
            "软件会优先使用内置工具，无需手动配置即可正常使用。\n\n"
            "如需使用本机已有工具，可点击路径自定义位置。\n\n"
            "遇到下载解析失败时，可尝试更新 yt-dlp。"
        )
        notes_body.setWordWrap(True)
        notes_body.setStyleSheet("color: #475569; line-height: 150%; font-weight: 400;")
        notes_layout.addWidget(notes_title)
        notes_layout.addWidget(notes_body)
        notes_layout.addStretch(1)
        content_layout.addWidget(notes, 2)
        layout.addLayout(content_layout, 1)
        return page

    def build_model_run_tab(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("QWidget { background: #ffffff; }")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(16)

        left = QFrame()
        left.setObjectName("modelRunPanel")
        left.setStyleSheet("""
            QFrame#modelRunPanel {
                background: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
            }
        """)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(16, 15, 16, 16)
        left_layout.setSpacing(12)

        config_title = QLabel("模型与运行配置")
        config_title.setStyleSheet("font-size: 14px; font-weight: 600; color: #172033;")
        left_layout.addWidget(config_title)

        self.advanced_model_combo = NoWheelComboBox()
        self.populate_advanced_model_combo(self.main_window.model_combo.currentData())
        self.advanced_model_combo.currentIndexChanged.connect(self.advanced_model_changed)
        left_layout.addWidget(self.form_row("Whisper 模型", self.advanced_model_combo))

        self.advanced_device_combo = NoWheelComboBox()
        self.advanced_device_combo.addItem("自动选择", "auto")
        self.advanced_device_combo.addItem("GPU 加速", "cuda")
        self.advanced_device_combo.addItem("CPU 模式", "cpu")
        self.advanced_device_combo.currentIndexChanged.connect(self.advanced_device_changed)
        left_layout.addWidget(self.form_row("运行方式", self.advanced_device_combo))

        self.model_dir_value = QLabel()
        self.model_dir_value.setWordWrap(True)
        self.model_dir_value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.model_dir_value.setStyleSheet("""
            color: #334155;
            background: #f9fbfd;
            border: 1px solid #e1e7ef;
            border-radius: 7px;
            padding: 9px 10px;
            font-weight: 400;
        """)
        left_layout.addWidget(self.form_row("模型存放位置", self.model_dir_value))

        self.advanced_local_model_label = QLabel("本地模型目录")
        self.advanced_local_model_label.setStyleSheet("color: #475569; font-weight: 700;")
        local_layout = QHBoxLayout()
        local_layout.setContentsMargins(0, 0, 0, 0)
        local_layout.setSpacing(8)
        self.advanced_local_model_input = QLineEdit()
        self.advanced_local_model_input.setPlaceholderText("例如 D:/models/faster-whisper-large-v3")
        self.advanced_local_model_input.textChanged.connect(self.advanced_local_model_changed)
        self.advanced_local_model_button = QPushButton("浏览")
        self.advanced_local_model_button.setObjectName("smallSecondaryButton")
        self.advanced_local_model_button.clicked.connect(self.pick_advanced_local_model_dir)
        local_layout.addWidget(self.advanced_local_model_input, 1)
        local_layout.addWidget(self.advanced_local_model_button)
        local_widget = QWidget()
        local_widget.setStyleSheet("background: transparent;")
        local_widget.setLayout(local_layout)
        self.advanced_local_model_row = self.form_row("本地模型目录", local_widget)
        left_layout.addWidget(self.advanced_local_model_row)

        self.advanced_model_info = QPlainTextEdit()
        self.advanced_model_info.setReadOnly(True)
        self.advanced_model_info.setMinimumHeight(132)
        self.advanced_model_info.setMaximumHeight(150)
        self.advanced_model_info.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.advanced_model_info.setStyleSheet("""
            QPlainTextEdit {
                color: #475569;
                background: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 7px;
                padding: 8px 10px;
                font-weight: 400;
            }
        """)
        left_layout.addWidget(self.advanced_model_info)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 2, 0, 0)
        actions.setSpacing(10)
        self.advanced_deploy_button = QPushButton("下载/部署所选模型")
        self.advanced_deploy_button.clicked.connect(self.deploy_selected_model)
        self.advanced_gpu_button = QPushButton("安装 GPU 加速组件")
        self.advanced_gpu_button.clicked.connect(self.install_gpu_components)
        actions.addWidget(self.advanced_deploy_button)
        actions.addWidget(self.advanced_gpu_button)
        left_layout.addLayout(actions)

        self.advanced_action_status = QLabel("设置会自动保存；部署和安装会在后台执行。")
        self.advanced_action_status.setWordWrap(True)
        self.advanced_action_status.setStyleSheet("color: #64748b; font-weight: 400;")
        left_layout.addWidget(self.advanced_action_status)
        left_layout.addStretch(1)
        content_layout.addWidget(left, 3)

        right = QFrame()
        right.setObjectName("runInfoPanel")
        right.setStyleSheet("""
            QFrame#runInfoPanel {
                background: #f9fbfd;
                border: 1px solid #e2e8f0;
                border-radius: 7px;
            }
        """)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(15, 14, 15, 14)
        right_layout.setSpacing(10)
        info_title = QLabel("运行信息")
        info_title.setStyleSheet("font-size: 14px; font-weight: 600; color: #172033;")
        right_layout.addWidget(info_title)
        self.whisper_status_label = self.status_line("语音识别：未检测")
        self.cuda_status_label = self.status_line("GPU 加速：未检测")
        self.whisper_version_label = self.status_line("faster-whisper 版本：未知")
        self.cuda_detail_label = self.status_line("支持精度：未检测")
        for label in (
            self.whisper_status_label,
            self.cuda_status_label,
            self.whisper_version_label,
            self.cuda_detail_label,
        ):
            right_layout.addWidget(label)

        tips_title = QLabel("提示")
        tips_title.setStyleSheet("font-size: 14px; font-weight: 600; color: #172033; margin-top: 6px;")
        tips_body = QLabel(
            "建议首次使用选择 medium 模型，在速度与识别准确度之间较平衡。\n\n"
            "GPU 加速仅 NVIDIA 显卡支持；不可用时会使用 CPU 模式。\n\n"
            "模型部署到本地后，可减少重复下载并支持离线使用。"
        )
        tips_body.setWordWrap(True)
        tips_body.setStyleSheet("color: #475569; line-height: 150%; font-weight: 400;")
        right_layout.addWidget(tips_title)
        right_layout.addWidget(tips_body)
        right_layout.addStretch(1)
        content_layout.addWidget(right, 2)

        layout.addLayout(content_layout, 1)
        self.sync_model_run_from_main()
        self.update_model_run_controls()
        return page

    def build_cookie_access_tab(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("QWidget { background: #ffffff; }")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(16)

        left = QFrame()
        left.setObjectName("cookieModePanel")
        left.setStyleSheet("""
            QFrame#cookieModePanel {
                background: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
            }
            QFrame#cookieOption {
                background: #f9fbfd;
                border: 1px solid #e1e7ef;
                border-radius: 7px;
            }
            QRadioButton {
                color: #172033;
                font-weight: 600;
                spacing: 8px;
            }
        """)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(16, 15, 16, 16)
        left_layout.setSpacing(12)

        title = QLabel("Cookies 使用方式")
        title.setStyleSheet("font-size: 14px; font-weight: 600; color: #172033;")
        left_layout.addWidget(title)

        self.cookie_radio_group = QButtonGroup(self)
        self.cookie_radio_group.setExclusive(True)
        self.advanced_cookie_radios: dict[str, QRadioButton] = {}
        self.advanced_cookie_option_frames: dict[str, QFrame] = {}
        self.advanced_cookie_option_modes: dict[QObject, str] = {}
        cookie_options = [
            ("none", "不使用 Cookies（推荐）", "适用于大多数公开视频"),
            ("browser", "从浏览器读取", "自动读取浏览器中的登录状态"),
            ("file", "使用 cookies.txt 文件", "使用本地 cookies.txt 文件"),
        ]
        for mode, label, description in cookie_options:
            radio = QRadioButton(label)
            self.cookie_radio_group.addButton(radio)
            self.advanced_cookie_radios[mode] = radio
            option = self.cookie_option_widget(mode, radio, description)
            self.advanced_cookie_option_frames[mode] = option
            left_layout.addWidget(option)
            radio.toggled.connect(lambda checked, selected=mode: self.advanced_cookie_mode_changed(selected) if checked else None)

        self.advanced_cookie_browser_combo = NoWheelComboBox()
        for browser in COOKIE_BROWSERS:
            self.advanced_cookie_browser_combo.addItem(browser.title(), browser)
        self.advanced_cookie_browser_combo.currentIndexChanged.connect(self.advanced_cookie_browser_changed)
        self.advanced_cookie_browser_row = self.form_row("浏览器", self.advanced_cookie_browser_combo)
        left_layout.addWidget(self.advanced_cookie_browser_row)

        file_row = QWidget()
        file_row.setStyleSheet("background: transparent;")
        file_layout = QHBoxLayout(file_row)
        file_layout.setContentsMargins(0, 0, 0, 0)
        file_layout.setSpacing(8)
        self.advanced_cookies_input = QLineEdit()
        self.advanced_cookies_input.setPlaceholderText("选择本地 cookies.txt 文件")
        self.advanced_cookies_input.textChanged.connect(self.advanced_cookies_file_changed)
        self.advanced_cookies_pick_btn = QPushButton("选择")
        self.advanced_cookies_pick_btn.setObjectName("smallSecondaryButton")
        self.advanced_cookies_pick_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton))
        self.advanced_cookies_pick_btn.clicked.connect(self.pick_advanced_cookies_file)
        file_layout.addWidget(self.advanced_cookies_input, 1)
        file_layout.addWidget(self.advanced_cookies_pick_btn)
        self.advanced_cookies_file_row = self.form_row("cookies.txt", file_row)
        left_layout.addWidget(self.advanced_cookies_file_row)

        self.advanced_cookies_status = QLabel("")
        self.advanced_cookies_status.setWordWrap(True)
        self.advanced_cookies_status.setStyleSheet("color: #64748b; font-weight: 400;")
        left_layout.addWidget(self.advanced_cookies_status)
        left_layout.addStretch(1)
        content_layout.addWidget(left, 3)

        right = QFrame()
        right.setObjectName("cookieInfoPanel")
        right.setStyleSheet("""
            QFrame#cookieInfoPanel {
                background: #f9fbfd;
                border: 1px solid #e2e8f0;
                border-radius: 7px;
            }
        """)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(15, 14, 15, 14)
        right_layout.setSpacing(10)
        info_title = QLabel("说明")
        info_title.setStyleSheet("font-size: 14px; font-weight: 600; color: #172033;")
        info_body = QLabel(
            "大多数公开视频不需要 Cookies。\n\n"
            "只有登录资源、会员资源或部分受限视频，才可能需要 Cookies 才能正常下载字幕或音频。\n\n"
        )
        info_body.setWordWrap(True)
        info_body.setStyleSheet("color: #475569; line-height: 150%; font-weight: 400;")
        right_layout.addWidget(info_title)
        right_layout.addWidget(info_body)
        right_layout.addStretch(1)
        content_layout.addWidget(right, 2)

        layout.addLayout(content_layout, 1)
        self.sync_cookie_access_from_main()
        return page

    def cookie_option_widget(self, mode: str, radio: QRadioButton, description: str) -> QFrame:
        frame = QFrame()
        frame.setObjectName("cookieOption")
        frame.setCursor(Qt.CursorShape.PointingHandCursor)
        frame.installEventFilter(self)
        self.advanced_cookie_option_modes[frame] = mode
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)
        desc_label = QLabel(description)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #64748b; font-weight: 400;")
        desc_label.setCursor(Qt.CursorShape.PointingHandCursor)
        desc_label.installEventFilter(self)
        self.advanced_cookie_option_modes[desc_label] = mode
        radio.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(radio)
        layout.addWidget(desc_label)
        return frame

    def eventFilter(self, watched, event) -> bool:
        if (
            hasattr(self, "advanced_cookie_option_modes")
            and watched in self.advanced_cookie_option_modes
            and event.type() == QEvent.Type.MouseButtonPress
            and event.button() == Qt.MouseButton.LeftButton
        ):
            mode = self.advanced_cookie_option_modes[watched]
            radio = self.advanced_cookie_radios.get(mode)
            if radio is not None:
                radio.setChecked(True)
            return True
        return super().eventFilter(watched, event)

    def form_row(self, label_text: str, field: QWidget) -> QWidget:
        row = QWidget()
        row.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        label = QLabel(label_text)
        label.setStyleSheet("color: #475569; font-weight: 700;")
        layout.addWidget(label)
        layout.addWidget(field)
        return row

    def status_line(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        label.setStyleSheet("""
            color: #334155;
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 7px;
            padding: 8px 10px;
            font-weight: 500;
        """)
        return label

    def placeholder_tab(self, text: str) -> QWidget:
        page = QWidget()
        page.setStyleSheet("QWidget { background: #ffffff; }")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        label = QLabel(text)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("color: #64748b; font-size: 14px; font-weight: 700;")
        layout.addWidget(label, 1)
        return page

    def connect_model_run_sync(self) -> None:
        self.main_window.model_combo.currentIndexChanged.connect(self.sync_model_run_from_main)
        self.main_window.local_model_input.textChanged.connect(self.sync_model_run_from_main)
        self.main_window.device_combo.currentTextChanged.connect(self.sync_model_run_from_main)

    def connect_cookie_access_sync(self) -> None:
        self.main_window.cookie_mode_combo.currentIndexChanged.connect(self.sync_cookie_access_from_main)
        self.main_window.cookie_browser_combo.currentIndexChanged.connect(self.sync_cookie_access_from_main)
        self.main_window.cookies_input.textChanged.connect(self.sync_cookie_access_from_main)

    def sync_cookie_access_from_main(self) -> None:
        if not hasattr(self, "advanced_cookie_radios") or self.syncing_cookies:
            return
        self.syncing_cookies = True
        try:
            mode = self.main_window.cookie_mode_combo.currentData() or "none"
            radio = self.advanced_cookie_radios.get(mode) or self.advanced_cookie_radios["none"]
            radio.setChecked(True)
            browser = self.main_window.cookie_browser_combo.currentData()
            if not browser:
                browser_index = self.main_window.cookie_browser_combo.currentIndex()
                browser = COOKIE_BROWSERS[browser_index] if 0 <= browser_index < len(COOKIE_BROWSERS) else "chrome"
            index = self.advanced_cookie_browser_combo.findData(str(browser).lower())
            self.advanced_cookie_browser_combo.setCurrentIndex(index if index >= 0 else 0)
            self.advanced_cookies_input.setText(self.main_window.cookies_input.text())
        finally:
            self.syncing_cookies = False
        self.update_cookie_access_controls()

    def advanced_cookie_mode_changed(self, mode: str) -> None:
        if self.syncing_cookies:
            return
        index = self.main_window.cookie_mode_combo.findData(mode)
        if index >= 0:
            self.main_window.cookie_mode_combo.setCurrentIndex(index)
        self.main_window.update_cookie_mode_ui()
        self.main_window.save_settings_now()
        self.update_cookie_access_controls()

    def advanced_cookie_browser_changed(self) -> None:
        if self.syncing_cookies:
            return
        browser = self.advanced_cookie_browser_combo.currentData() or "chrome"
        index = self.main_window.cookie_browser_combo.findText(str(browser).title())
        self.syncing_cookies = True
        try:
            self.main_window.cookie_browser_combo.setCurrentIndex(index if index >= 0 else 0)
        finally:
            self.syncing_cookies = False
        self.main_window.save_settings_now()
        self.update_cookie_file_status()

    def advanced_cookies_file_changed(self) -> None:
        if self.syncing_cookies:
            return
        self.syncing_cookies = True
        try:
            self.main_window.cookies_input.setText(self.advanced_cookies_input.text())
        finally:
            self.syncing_cookies = False
        self.main_window.save_settings_now()
        self.update_cookie_file_status()

    def pick_advanced_cookies_file(self) -> None:
        current = self.advanced_cookies_input.text().strip() or str(ROOT)
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择 cookies.txt 文件",
            current,
            "文本文件 (*.txt);;所有文件 (*)",
        )
        if path:
            self.advanced_cookies_input.setText(path)

    def update_cookie_access_controls(self) -> None:
        if not hasattr(self, "advanced_cookie_browser_combo"):
            return
        mode = self.current_advanced_cookie_mode()
        is_browser = mode == "browser"
        is_file = mode == "file"
        self.advanced_cookie_browser_row.setVisible(is_browser)
        self.advanced_cookie_browser_combo.setEnabled(is_browser)
        self.advanced_cookies_file_row.setVisible(is_file)
        self.advanced_cookies_input.setEnabled(is_file)
        self.advanced_cookies_pick_btn.setEnabled(is_file)
        self.update_cookie_option_styles(mode)
        self.update_cookie_file_status()

    def update_cookie_option_styles(self, selected_mode: str) -> None:
        if not hasattr(self, "advanced_cookie_option_frames"):
            return
        for mode, frame in self.advanced_cookie_option_frames.items():
            selected = mode == selected_mode
            frame.setStyleSheet(f"""
                QFrame#cookieOption {{
                    background: {'#eef6ff' if selected else '#f9fbfd'};
                    border: 1px solid {'#60a5fa' if selected else '#e1e7ef'};
                    border-radius: 7px;
                }}
            """)
            radio = self.advanced_cookie_radios.get(mode)
            if radio is not None:
                radio.setStyleSheet(f"""
                    QRadioButton {{
                        color: {'#1d4ed8' if selected else '#172033'};
                        font-weight: 600;
                        spacing: 8px;
                    }}
                """)

    def update_cookie_file_status(self) -> None:
        if not hasattr(self, "advanced_cookies_status"):
            return
        mode = self.current_advanced_cookie_mode()
        path = self.advanced_cookies_input.text().strip()
        if mode == "none":
            message = "当前不会向下载流程传递 Cookies。"
        elif mode == "browser":
            message = "将尝试从所选浏览器读取登录状态，使用前建议关闭对应浏览器。"
        elif not path:
            message = "请选择 cookies.txt 文件；取消选择不会改变原路径。"
        elif Path(path).exists():
            message = "将使用所选 cookies.txt 文件；请不要上传、分享或提交该文件。"
        else:
            message = "当前路径不存在，请确认 cookies.txt 文件位置。"
        self.advanced_cookies_status.setText(message)

    def current_advanced_cookie_mode(self) -> str:
        if not hasattr(self, "advanced_cookie_radios"):
            return "none"
        for mode, radio in self.advanced_cookie_radios.items():
            if radio.isChecked():
                return mode
        return "none"

    def populate_advanced_model_combo(self, selected_value: str | None = None) -> None:
        if not hasattr(self, "advanced_model_combo"):
            return
        was_syncing = self.syncing_model_run
        self.syncing_model_run = True
        try:
            self.advanced_model_combo.clear()
            for label, value in get_model_choices(self.main_window.deployed_models):
                self.advanced_model_combo.addItem(label, value)
            index = self.advanced_model_combo.findData(selected_value)
            self.advanced_model_combo.setCurrentIndex(index if index >= 0 else 0)
        finally:
            self.syncing_model_run = was_syncing

    def sync_model_run_from_main(self) -> None:
        if not hasattr(self, "advanced_model_combo") or self.syncing_model_run:
            return
        self.syncing_model_run = True
        try:
            selected_value = self.main_window.model_combo.currentData()
            self.populate_advanced_model_combo(selected_value)
            self.advanced_local_model_input.setText(self.main_window.local_model_input.text())
            device = self.main_window.device_combo.currentText()
            index = self.advanced_device_combo.findData(device)
            self.advanced_device_combo.setCurrentIndex(index if index >= 0 else 0)
        finally:
            self.syncing_model_run = False
        self.update_model_run_controls()

    def advanced_model_changed(self) -> None:
        if self.syncing_model_run:
            return
        value = self.advanced_model_combo.currentData()
        self.syncing_model_run = True
        try:
            index = self.main_window.model_combo.findData(value)
            self.main_window.model_combo.setCurrentIndex(index if index >= 0 else 0)
        finally:
            self.syncing_model_run = False
        self.main_window.update_model_info()
        self.main_window.save_settings_now()
        self.update_model_run_controls()

    def advanced_device_changed(self) -> None:
        if self.syncing_model_run:
            return
        value = self.advanced_device_combo.currentData() or "auto"
        self.syncing_model_run = True
        try:
            self.main_window.device_combo.setCurrentText(value)
        finally:
            self.syncing_model_run = False
        self.main_window.update_model_summary()
        self.main_window.save_settings_now()
        self.update_model_run_controls()

    def advanced_local_model_changed(self) -> None:
        if self.syncing_model_run:
            return
        self.syncing_model_run = True
        try:
            self.main_window.local_model_input.setText(self.advanced_local_model_input.text())
        finally:
            self.syncing_model_run = False
        self.main_window.update_model_info()
        self.main_window.save_settings_now()
        self.update_model_run_controls()

    def pick_advanced_local_model_dir(self) -> None:
        current = self.advanced_local_model_input.text().strip() or str(ROOT)
        path = QFileDialog.getExistingDirectory(self, "选择模型目录", current)
        if path:
            self.advanced_local_model_input.setText(path)

    def update_model_run_controls(self) -> None:
        if not hasattr(self, "advanced_model_combo"):
            return
        selected_value = self.advanced_model_combo.currentData()
        is_local = is_local_model_choice(selected_value)
        self.advanced_local_model_row.setVisible(is_local)
        self.model_dir_value.setText(str(MODELS_DIR))
        self.model_dir_value.setToolTip(str(MODELS_DIR))
        self.advanced_model_info.setPlainText(
            get_model_description(selected_value, cuda_ok=self.main_window.cuda_ok)
        )
        if is_local:
            local_dir = self.advanced_local_model_input.text().strip()
            if not local_dir:
                status = "请选择本地模型目录。"
            elif is_valid_model_dir(local_dir):
                status = "本地模型目录可用。"
            elif Path(local_dir).is_dir():
                status = "本地模型目录缺少基本模型文件。"
            else:
                status = "本地模型目录不存在。"
            self.advanced_action_status.setText(status)
        elif selected_value:
            status = "已部署，可离线使用。" if selected_value in self.main_window.deployed_models else "未部署，可点击下载/部署。"
            self.advanced_action_status.setText(status)
        else:
            self.advanced_action_status.setText("请选择 Whisper 模型。")

    def set_status_label(self, label: QLabel, text: str, state: str = "unknown") -> None:
        colors = {
            "ok": ("#166534", "#dcfce7", "#bbf7d0"),
            "bad": ("#b91c1c", "#fee2e2", "#fecaca"),
            "pending": ("#475569", "#f1f5f9", "#e2e8f0"),
            "unknown": ("#334155", "#ffffff", "#e2e8f0"),
        }
        color, bg, border = colors.get(state, colors["unknown"])
        label.setText(text)
        label.setStyleSheet(f"""
            color: {color};
            background: {bg};
            border: 1px solid {border};
            border-radius: 7px;
            padding: 8px 10px;
            font-weight: 500;
        """)

    def set_run_info_pending(self, action: str = "检测中") -> None:
        if not hasattr(self, "whisper_status_label"):
            return
        self.set_status_label(self.whisper_status_label, f"语音识别：{action}", "pending")
        self.set_status_label(self.cuda_status_label, f"GPU 加速：{action}", "pending")
        self.set_status_label(self.whisper_version_label, "faster-whisper 版本：检测中", "pending")
        self.set_status_label(self.cuda_detail_label, "支持精度：检测中", "pending")

    def update_run_info(self, report: dict | None) -> None:
        if not hasattr(self, "whisper_status_label"):
            return
        whisper = (report or {}).get("whisper") or {}
        cuda = (report or {}).get("cuda") or {}
        whisper_ok = whisper.get("ok")
        cuda_ok = cuda.get("ok")
        self.set_status_label(
            self.whisper_status_label,
            f"语音识别：{'可用' if whisper_ok else '不可用' if whisper else '未检测'}",
            "ok" if whisper_ok else "bad" if whisper else "unknown",
        )
        self.set_status_label(
            self.cuda_status_label,
            f"GPU 加速：{'可用' if cuda_ok else '不可用' if cuda else '未检测'}",
            "ok" if cuda_ok else "bad" if cuda else "unknown",
        )
        self.set_status_label(
            self.whisper_version_label,
            f"faster-whisper 版本：{whisper.get('version') or '未知'}",
            "unknown",
        )
        compute_types = cuda.get("compute_types") or []
        if compute_types:
            cuda_detail = "支持精度：" + ", ".join(compute_types)
        elif cuda:
            cuda_detail = cuda.get("detail") or "未检测到支持精度"
        else:
            cuda_detail = "支持精度：未检测"
        if not str(cuda_detail).startswith("支持精度："):
            cuda_detail = f"GPU 检测详情：{cuda_detail}"
        self.set_status_label(self.cuda_detail_label, cuda_detail, "unknown")

    def deploy_selected_model(self) -> None:
        if self.thread is not None:
            return
        selected_value = self.advanced_model_combo.currentData()
        model = resolve_selected_model(selected_value, self.advanced_local_model_input.text())
        if not selected_value or not model:
            QMessageBox.warning(self, "缺少模型", "请先选择识别模型。")
            return
        model_source = "local" if is_local_model_choice(selected_value) else "preset"
        self.main_window.save_settings_now()
        self.main_window.append_log_separator()
        self.main_window.append_log(
            f"开始部署官方模型：{model}"
            if model_source == "preset"
            else f"开始检查本地模型目录：{model}"
        )
        self.main_window.set_status("正在部署模型" if model_source == "preset" else "正在检查本地模型目录")
        self.advanced_action_status.setText("正在部署模型，请稍候。" if model_source == "preset" else "正在检查本地模型目录。")
        self.set_busy(True)
        self.thread = QThread()
        self.worker = ModelDeployWorker(model_source, model)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.done.connect(self.model_deploy_done)
        self.worker.done.connect(self.thread.quit)
        self.worker.done.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(self.clear_worker)
        self.thread.start()

    def model_deploy_done(self, ok: bool, message: str) -> None:
        if ok:
            self.main_window.refresh_model_choices()
            self.populate_advanced_model_combo(self.main_window.model_combo.currentData())
        self.main_window.set_status(message)
        self.main_window.append_log(message)
        self.advanced_action_status.setText(message)
        self.update_model_run_controls()
        if not ok and message.startswith("模型部署失败"):
            QMessageBox.critical(self, "模型部署失败", message)
        self.set_busy(False)

    def install_gpu_components(self) -> None:
        self.main_window.save_settings_now()
        self.main_window.append_log_separator()
        self.main_window.append_log("开始安装 GPU 加速组件")
        self.main_window.set_status("正在安装 GPU 加速组件")
        self.start_env_action("install_gpu", "安装中")

    def set_busy(self, busy: bool) -> None:
        self.update_tools_button.setEnabled(not busy)
        self.redetect_button.setEnabled(not busy)
        self.restore_button.setEnabled(not busy)
        if hasattr(self, "advanced_deploy_button"):
            self.advanced_deploy_button.setEnabled(not busy)
            self.advanced_gpu_button.setEnabled(not busy)
            self.advanced_model_combo.setEnabled(not busy)
            self.advanced_device_combo.setEnabled(not busy)
            self.advanced_local_model_input.setEnabled(not busy)
            self.advanced_local_model_button.setEnabled(not busy)

    def choose_tool_path(self, key: str) -> None:
        title = "选择 FFmpeg 可执行文件" if key == "ffmpeg" else "选择 yt-dlp 可执行文件"
        target = self.main_window.ffmpeg_input if key == "ffmpeg" else self.main_window.ytdlp_input
        current = target.text().strip() or str(ROOT)
        path, _ = QFileDialog.getOpenFileName(self, title, current, "可执行文件 (*.exe);;所有文件 (*)")
        if not path:
            return
        target.setText(path)
        self.main_window.save_settings_now()
        self.run_detection()

    def restore_builtin_tools(self) -> None:
        self.main_window.ffmpeg_input.setText("")
        self.main_window.ytdlp_input.setText("")
        self.main_window.save_settings_now()
        self.run_detection()

    def update_tools(self) -> None:
        self.main_window.save_settings_now()
        self.main_window.append_log_separator()
        self.main_window.append_log("开始更新 yt-dlp")
        self.main_window.set_status("正在更新 yt-dlp")
        self.start_env_action("update_ytdlp", "更新中")

    def run_detection(self) -> None:
        self.start_env_action("check", "检测中")

    def start_env_action(self, action: str, label: str) -> None:
        if self.thread is not None:
            return
        self.ffmpeg_card.set_pending("检测中")
        self.ytdlp_card.set_pending(label)
        self.set_run_info_pending(label)
        self.set_busy(True)
        self.thread = QThread()
        self.worker = EnvWorker(
            self.main_window.ffmpeg_input.text(),
            self.main_window.ytdlp_input.text(),
            action,
        )
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.log.connect(self.main_window.append_log)
        self.worker.done.connect(self.detection_done)
        self.worker.done.connect(self.thread.quit)
        self.worker.done.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(self.clear_worker)
        self.thread.start()

    def detection_done(self, ok: bool, report: dict) -> None:
        self.ffmpeg_card.update_status(report.get("ffmpeg") if report else None)
        self.ytdlp_card.update_status(report.get("yt-dlp") if report else None)
        self.env_report = report or {}
        self.update_run_info(self.env_report)
        if report:
            summary = build_env_summary(report, ok)
            self.main_window.env_ready = ok
            self.main_window.set_env_summary(summary)
            details_text = format_env_report(report)
            self.main_window.env_status.setToolTip(details_text)
            self.main_window.env_detail_label.setText(details_text)
            self.main_window.cuda_ok = report.get("cuda", {}).get("ok", False)
            self.main_window.update_model_info()
            self.main_window.refresh_buttons(False)
        self.set_busy(False)

    def clear_worker(self) -> None:
        self.worker = None
        self.thread = None

    def closeEvent(self, event) -> None:
        if self.thread is not None:
            self.thread.quit()
            self.thread.wait(1500)
        super().closeEvent(event)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("视频字幕提取")
        self.resize(1180, 820)
        self.settings = read_settings()
        self.env_ready = False
        self.cuda_ok = False
        self.env_advanced_visible = False
        self.model_panel_visible = False
        self.log_panel_visible = False
        self.thread: QThread | None = None
        self.worker: QObject | None = None
        self.advanced_settings_dialog: AdvancedSettingsDialog | None = None
        self.output_path = ""
        self.loading_settings = False
        self.env_task_autosave = True
        self.deployed_models = scan_deployed_models()
        self.settings_save_timer = QTimer(self)
        self.settings_save_timer.setSingleShot(True)
        self.settings_save_timer.setInterval(1000)
        self.settings_save_timer.timeout.connect(self.save_settings_now)
        self.build_ui()
        self.load_settings()
        self.refresh_buttons()
        QTimer.singleShot(200, lambda: self.run_env_task("check", autosave=False))

    def build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root.setStyleSheet("""
            QWidget {
                background: #f6f8fb;
                color: #17202c;
            }
            QLabel {
                background: transparent;
            }
            QLineEdit, QComboBox, QPlainTextEdit {
                min-height: 24px;
                background: #ffffff;
                border: 1px solid #d8dee8;
                border-radius: 7px;
                padding: 8px 11px;
                selection-background-color: #2563eb;
            }
            QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus {
                border-color: #2563eb;
            }
            QPushButton {
                min-height: 24px;
                background: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 7px;
                padding: 8px 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #f3f6fa;
                border-color: #a9b6c7;
            }
            QPushButton:pressed {
                background: #e8eef6;
            }
            QPushButton:disabled {
                color: #97a3b3;
                background: #edf1f5;
                border-color: #dbe2ea;
            }
            QProgressBar {
                min-height: 8px;
                max-height: 8px;
                border: 1px solid #d8dee8;
                border-radius: 4px;
                background: #eef2f7;
                text-align: center;
            }
            QProgressBar::chunk {
                background: #2563eb;
                border-radius: 4px;
            }
        """)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        scroll_area.setStyleSheet("QScrollArea { background: #f6f8fb; border: none; }")

        scroll_body = QWidget()
        scroll_body.setStyleSheet("QWidget { background: #f6f8fb; }")
        scroll_layout = QHBoxLayout(scroll_body)
        scroll_layout.setContentsMargins(28, 22, 28, 24)
        scroll_layout.setSpacing(0)

        content = QWidget()
        content.setObjectName("content")
        content.setMinimumWidth(900)
        content.setMaximumWidth(1180)
        content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        content.setStyleSheet("QWidget#content { background: transparent; }")
        scroll_layout.addStretch(1)
        scroll_layout.addWidget(content, 16)
        scroll_layout.addStretch(1)
        scroll_area.setWidget(scroll_body)
        root_layout.addWidget(scroll_area)

        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("请输入或粘贴视频链接，例如：https://www.bilibili.com/video/BV1GedwbPE1j/")
        self.output_dir_input = QLineEdit()
        self.output_dir_input.setPlaceholderText(DEFAULT_OUTPUT_DIR.name)
        self.output_dir_pick_btn = QPushButton("选择目录")
        self.decorate_button(self.output_dir_pick_btn, QStyle.StandardPixmap.SP_DirOpenIcon)
        self.output_dir_pick_btn.clicked.connect(self.pick_output_dir)
        self.open_button = QPushButton("打开目录")
        self.decorate_button(self.open_button, QStyle.StandardPixmap.SP_DialogOpenButton)
        self.open_button.setEnabled(False)

        self.model_combo = NoWheelComboBox()
        for label, value in get_model_choices(self.deployed_models):
            self.model_combo.addItem(label, value)
        self.model_combo.setCurrentIndex(0)
        self.local_model_input = QLineEdit()
        self.local_model_input.setPlaceholderText("例如 D:/models/faster-whisper-large-v3")
        self.local_model_pick_btn = QPushButton("选择目录")
        self.decorate_button(self.local_model_pick_btn, QStyle.StandardPixmap.SP_DirOpenIcon)
        self.local_model_pick_btn.clicked.connect(self.pick_local_model_dir)
        self.device_combo = NoWheelComboBox()
        self.device_combo.addItems(["auto", "cuda", "cpu"])

        header_layout = QHBoxLayout()
        header_layout.setSpacing(18)
        logo = QLabel("cc")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setFixedSize(48, 48)
        logo_font = logo.font()
        logo_font.setPointSize(18)
        logo_font.setWeight(QFont.Weight.Black)
        logo.setFont(logo_font)
        logo.setStyleSheet("""
            color: #2563eb;
            background: #eaf2ff;
            border-radius: 8px;
            font-weight: 900;
        """)
        title_stack = QVBoxLayout()
        title_stack.setSpacing(5)
        title_label = QLabel("视频字幕提取")
        title_font = title_label.font()
        title_font.setPointSize(22)
        title_font.setWeight(QFont.Weight.Bold)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #172033;")
        subtitle_label = QLabel("粘贴链接，提取字幕")
        subtitle_label.setStyleSheet("color: #64748b; font-size: 13px; font-weight: 600;")
        title_stack.addWidget(title_label)
        title_stack.addWidget(subtitle_label)
        header_layout.addWidget(logo, 0, Qt.AlignmentFlag.AlignTop)
        header_layout.addLayout(title_stack, 1)
        self.advanced_button = QPushButton("高级设置")
        self.decorate_button(self.advanced_button, QStyle.StandardPixmap.SP_FileDialogDetailedView)
        self.advanced_button.setMinimumHeight(40)
        header_layout.addWidget(self.advanced_button, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(header_layout)

        self.advanced_card = self.create_card()
        advanced_layout = QVBoxLayout(self.advanced_card)
        advanced_layout.setContentsMargins(24, 22, 24, 22)
        advanced_placeholder = QLabel("")
        advanced_placeholder.setMinimumHeight(120)
        advanced_layout.addWidget(advanced_placeholder)
        self.advanced_card.setVisible(False)
        layout.addWidget(self.advanced_card)

        main_card = self.create_card()
        main_layout = QGridLayout(main_card)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setHorizontalSpacing(16)
        main_layout.setVerticalSpacing(18)
        main_layout.setColumnStretch(1, 1)
        main_layout.setColumnMinimumWidth(0, 150)
        main_layout.addWidget(
            self.create_icon_label("视频链接", QStyle.StandardPixmap.SP_FileLinkIcon),
            0,
            0,
        )
        main_layout.addWidget(self.url_input, 0, 1, 1, 3)
        main_layout.addWidget(
            self.create_icon_label("输出目录", QStyle.StandardPixmap.SP_DirIcon),
            1,
            0,
        )
        main_layout.addWidget(self.output_dir_input, 1, 1)
        main_layout.addWidget(self.output_dir_pick_btn, 1, 2)
        main_layout.addWidget(self.open_button, 1, 3)

        self.model_value_label = QLabel("等待加载配置")
        self.device_value_label = QLabel("等待加载配置")
        self.env_value_label = QLabel("未检查")
        self.model_summary_label = QLabel("")
        self.model_summary_label.hide()
        config_layout = QHBoxLayout()
        config_layout.setSpacing(12)
        self.model_config_card = self.create_status_card(
            "模型",
            self.model_value_label,
            QStyle.StandardPixmap.SP_DriveNetIcon,
            action_text="选择",
            on_click=self.open_model_picker,
        )
        self.device_config_card = self.create_status_card(
            "运行方式",
            self.device_value_label,
            QStyle.StandardPixmap.SP_ComputerIcon,
            action_text="选择",
            on_click=self.open_device_menu,
        )
        config_layout.addWidget(self.model_config_card, 1)
        config_layout.addWidget(self.device_config_card, 1)
        config_layout.addWidget(self.create_status_card("环境状态", self.env_value_label, QStyle.StandardPixmap.SP_DialogApplyButton), 1)
        main_layout.addWidget(
            self.create_icon_label("当前配置", QStyle.StandardPixmap.SP_FileDialogInfoView),
            2,
            0,
        )
        main_layout.addLayout(config_layout, 2, 1, 1, 3)
        config_hint = QLabel("中文内容请选择通用模型；英文内容可选择 .en 英文专用模型。")
        config_hint.setWordWrap(True)
        config_hint.setStyleSheet("color: #64748b; font-size: 12px; font-weight: 400;")
        main_layout.addWidget(config_hint, 3, 1, 1, 3)

        self.env_status = QLabel("环境状态：未检查")
        self.env_status.hide()
        self.env_status.setWordWrap(True)
        self.result_label = QLabel("当前状态：等待环境检查")
        self.result_label.hide()
        self.result_label.setWordWrap(True)
        self.result_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.start_button = QPushButton("开始提取字幕")
        self.start_button.setMinimumHeight(58)
        self.start_button.setDefault(True)
        self.decorate_button(self.start_button, QStyle.StandardPixmap.SP_MediaPlay)
        self.start_button.setStyleSheet("""
            QPushButton {
                color: #ffffff;
                background: #2563eb;
                border: 1px solid #2563eb;
                border-radius: 10px;
                font-size: 17px;
                font-weight: 700;
                padding: 13px 18px;
            }
            QPushButton:hover {
                background: #1d4ed8;
                border-color: #1d4ed8;
            }
            QPushButton:pressed {
                background: #1e40af;
                border-color: #1e40af;
            }
            QPushButton:disabled {
                color: #d8e2f1;
                background: #8da6cf;
                border-color: #8da6cf;
            }
        """)
        main_layout.addWidget(self.start_button, 4, 0, 1, 4)
        layout.addWidget(main_card)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.hide()
        layout.addWidget(self.progress)

        self.hidden_settings_widget = QWidget()
        self.hidden_settings_widget.setVisible(False)
        hidden_layout = QVBoxLayout(self.hidden_settings_widget)
        hidden_layout.setContentsMargins(0, 0, 0, 0)
        self.ffmpeg_input = QLineEdit()
        self.ytdlp_input = QLineEdit()
        self.cookie_mode_combo = NoWheelComboBox()
        for mode in COOKIE_MODES:
            self.cookie_mode_combo.addItem(mode["label"], mode["name"])
        self.cookie_browser_combo = NoWheelComboBox()
        self.cookie_browser_combo.addItems(["Chrome", "Edge", "Firefox"])
        self.browser_combo = self.cookie_browser_combo
        self.cookie_browser_label = self.form_label("浏览器")
        self.cookies_input = QLineEdit()
        self.cookies_input.setPlaceholderText("cookies.txt 文件路径")
        self.cookies_pick_btn = self.pick_button(self.cookies_input)
        self.cookies_label = self.form_label("cookies.txt")
        self.check_button = QPushButton("检查环境")
        self.prepare_button = QPushButton("准备环境")
        self.update_ytdlp_button = QPushButton("更新 yt-dlp")
        self.gpu_button = QPushButton("安装 GPU 加速组件")
        self.env_detail_label = QLabel("")
        self.env_detail_label.setWordWrap(True)
        self.env_detail_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.cookie_mode_combo.currentIndexChanged.connect(self.update_cookie_mode_ui)
        self.local_model_label = self.form_label("本地模型目录")
        self.model_info_label = QLabel("")
        self.model_info_label.setWordWrap(True)
        self.deploy_model_button = QPushButton("部署模型")
        self.deploy_model_button.clicked.connect(self.deploy_model)
        for widget in [
            self.ffmpeg_input,
            self.ytdlp_input,
            self.cookie_mode_combo,
            self.cookie_browser_label,
            self.cookie_browser_combo,
            self.cookies_label,
            self.cookies_input,
            self.cookies_pick_btn,
            self.local_model_label,
            self.local_model_input,
            self.local_model_pick_btn,
            self.model_combo,
            self.device_combo,
            self.model_info_label,
            self.deploy_model_button,
            self.env_detail_label,
            self.check_button,
            self.prepare_button,
            self.update_ytdlp_button,
            self.gpu_button,
        ]:
            hidden_layout.addWidget(widget)
        layout.addWidget(self.hidden_settings_widget)

        log_card = self.create_card()
        log_layout = QVBoxLayout(log_card)
        log_layout.setContentsMargins(20, 20, 20, 20)
        log_layout.setSpacing(12)
        log_header = QHBoxLayout()
        log_header.setSpacing(12)
        log_icon = QLabel()
        log_icon.setFixedSize(34, 34)
        log_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        log_icon.setPixmap(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogInfoView).pixmap(20, 20))
        log_icon.setStyleSheet("""
            background: #eef6ff;
            border: 1px solid #dbeafe;
            border-radius: 7px;
        """)
        log_title = QLabel("运行日志")
        log_title.setStyleSheet("font-size: 15px; font-weight: 700; color: #172033;")
        self.log_toggle_button = QPushButton("清空日志")
        self.decorate_button(self.log_toggle_button, QStyle.StandardPixmap.SP_TrashIcon)
        log_header.addWidget(log_icon)
        log_header.addWidget(log_title, 1)
        log_header.addWidget(self.log_toggle_button, 0, Qt.AlignmentFlag.AlignTop)
        log_layout.addLayout(log_header)
        self.log_panel_widget = QFrame()
        self.log_panel_widget.setObjectName("logPanel")
        self.log_panel_widget.setStyleSheet("""
            QFrame#logPanel {
                background: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 7px;
            }
            QPlainTextEdit {
                border: none;
                background: #ffffff;
                font-family: Consolas, "Microsoft YaHei UI";
                color: #334155;
            }
        """)
        log_panel_layout = QVBoxLayout(self.log_panel_widget)
        log_panel_layout.setContentsMargins(8, 8, 8, 8)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMinimumHeight(150)
        self.log_view.setMaximumHeight(220)
        self.log_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        log_panel_layout.addWidget(self.log_view)
        self.log_panel_widget.setVisible(True)
        self.log_panel_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        log_layout.addWidget(self.log_panel_widget)
        layout.addWidget(log_card)

        footer_layout = QHBoxLayout()
        footer_layout.setContentsMargins(0, 6, 8, 0)
        footer_layout.setSpacing(10)
        footer_icon = QLabel()
        footer_icon.setPixmap(self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation).pixmap(16, 16))
        help_label = QLabel("帮助文档")
        help_label.setStyleSheet("color: #64748b; font-weight: 600;")
        self.footer_summary_label = QLabel("")
        self.footer_summary_label.hide()
        self.footer_summary_label.setStyleSheet("color: #64748b; font-weight: 600;")
        footer_version_label = QLabel("版本：1.0.0")
        footer_version_label.setStyleSheet("color: #64748b; font-weight: 600;")
        footer_layout.addWidget(footer_icon)
        footer_layout.addWidget(help_label)
        footer_layout.addWidget(self.footer_summary_label, 1)
        footer_layout.addWidget(footer_version_label, 0, Qt.AlignmentFlag.AlignRight)
        layout.addLayout(footer_layout)
        layout.addStretch(1)
        self.env_advanced_visible = False
        self.model_panel_visible = False
        self.log_panel_visible = True
        self.env_advanced_button = QPushButton("环境与诊断")
        self.model_panel_button = QPushButton("模型管理")

        self.check_button.clicked.connect(lambda: self.run_env_task("check"))
        self.prepare_button.clicked.connect(lambda: self.run_env_task("prepare"))
        self.update_ytdlp_button.clicked.connect(lambda: self.run_env_task("update_ytdlp"))
        self.gpu_button.clicked.connect(lambda: self.run_env_task("install_gpu"))
        self.advanced_button.clicked.connect(self.open_advanced_settings)
        self.log_toggle_button.clicked.connect(self.clear_log)
        self.start_button.clicked.connect(self.start_extract)
        self.open_button.clicked.connect(self.open_output_dir)
        self.model_combo.currentIndexChanged.connect(self.update_model_info)
        self.local_model_input.textChanged.connect(self.update_model_info)
        self.device_combo.currentTextChanged.connect(self.update_model_summary)
        for widget in [
            self.ffmpeg_input,
            self.ytdlp_input,
            self.cookies_input,
            self.url_input,
            self.output_dir_input,
            self.local_model_input,
        ]:
            widget.textChanged.connect(self.schedule_save_settings)
        self.model_combo.currentIndexChanged.connect(self.schedule_save_settings)
        self.device_combo.currentTextChanged.connect(self.schedule_save_settings)
        self.cookie_mode_combo.currentIndexChanged.connect(self.schedule_save_settings)
        self.cookie_browser_combo.currentIndexChanged.connect(self.schedule_save_settings)

    def create_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        card.setFrameShape(QFrame.Shape.StyledPanel)
        card.setStyleSheet("""
            QFrame#card {
                background: #ffffff;
                border: 1px solid #e1e6ec;
                border-radius: 12px;
            }
        """)
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(18)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(31, 41, 55, 28))
        card.setGraphicsEffect(shadow)
        return card

    def create_icon_label(self, text: str, icon: QStyle.StandardPixmap) -> QWidget:
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        icon_label = QLabel()
        icon_label.setFixedSize(42, 42)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setPixmap(self.style().standardIcon(icon).pixmap(24, 24))
        icon_label.setStyleSheet("""
            background: #eef6ff;
            border: 1px solid #dbeafe;
            border-radius: 7px;
        """)
        text_label = QLabel(text)
        text_label.setStyleSheet("color: #1f2937; font-size: 14px; font-weight: 700;")
        layout.addWidget(icon_label)
        layout.addWidget(text_label, 1, Qt.AlignmentFlag.AlignVCenter)
        return container

    def create_status_card(
        self,
        title: str,
        value_label: QLabel,
        icon: QStyle.StandardPixmap,
        action_text: str = "",
        on_click=None,
    ) -> QFrame:
        card = QuickConfigCard(clickable=on_click is not None)
        if on_click is not None:
            card.clicked.connect(on_click)
        layout = QHBoxLayout(card)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(14)
        icon_label = QLabel()
        icon_label.setFixedSize(44, 44)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setPixmap(self.style().standardIcon(icon).pixmap(24, 24))
        icon_label.setStyleSheet("""
            background: #eef6ff;
            border-radius: 22px;
        """)
        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(3)
        title_label = QLabel(title)
        title_label.setStyleSheet("color: #64748b; font-weight: 700;")
        value_label.setWordWrap(True)
        value_label.setStyleSheet("color: #172033; font-size: 14px; font-weight: 700;")
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(6)
        header_layout.addWidget(title_label, 1)
        if action_text:
            action_label = QLabel(action_text)
            action_label.setStyleSheet("color: #2563eb; font-size: 12px; font-weight: 700;")
            header_layout.addWidget(action_label, 0, Qt.AlignmentFlag.AlignRight)
            card.add_click_target(action_label)
        text_layout.addLayout(header_layout)
        text_layout.addWidget(value_label)
        layout.addWidget(icon_label)
        layout.addLayout(text_layout, 1)
        for target in (icon_label, title_label, value_label):
            card.add_click_target(target)
        return card

    def decorate_button(self, button: QPushButton, icon: QStyle.StandardPixmap) -> None:
        button.setIcon(self.style().standardIcon(icon))
        button.setIconSize(button.iconSize())

    def pick_button(self, target: QLineEdit) -> QPushButton:
        button = QPushButton("选择")
        self.decorate_button(button, QStyle.StandardPixmap.SP_DialogOpenButton)
        button.clicked.connect(lambda: self.pick_file(target))
        return button

    def form_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet("color: #334155; font-weight: 600;")
        return label

    def field_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet("color: #475569; font-weight: 700;")
        label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        return label

    def open_model_picker(self) -> None:
        dialog = ModelPickerDialog(
            self,
            get_model_choices(self.deployed_models),
            self.model_combo.currentData(),
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        index = self.model_combo.findData(dialog.selected_value)
        if index < 0:
            return
        if self.model_combo.currentIndex() != index:
            self.model_combo.setCurrentIndex(index)
        self.update_model_info()
        self.save_settings_now()
        if self.advanced_settings_dialog is not None:
            self.advanced_settings_dialog.sync_model_run_from_main()

    def open_device_menu(self) -> None:
        options = [
            ("自动选择", "auto"),
            ("GPU 加速", "cuda"),
            ("CPU 模式", "cpu"),
        ]
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background: #ffffff;
                color: #172033;
                border: 1px solid #cbd5e1;
                border-radius: 7px;
                padding: 4px;
            }
            QMenu::item {
                padding: 7px 26px 7px 10px;
                border-radius: 5px;
            }
            QMenu::item:selected {
                background: #eaf2ff;
                color: #172033;
            }
        """)
        current = self.device_combo.currentText()
        for label, value in options:
            action = menu.addAction(label)
            action.setData(value)
            action.setCheckable(True)
            action.setChecked(value == current)
        action = menu.exec(self.device_config_card.mapToGlobal(self.device_config_card.rect().bottomLeft()))
        if action is None:
            return
        value = action.data() or "auto"
        if self.device_combo.currentText() != value:
            self.device_combo.setCurrentText(value)
        self.update_model_summary()
        self.save_settings_now()
        if self.advanced_settings_dialog is not None:
            self.advanced_settings_dialog.sync_model_run_from_main()

    def pick_file(self, target: QLineEdit) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择文件")
        if path:
            target.setText(path)

    def pick_output_dir(self) -> None:
        current = self.output_dir_input.text().strip() or str(DEFAULT_OUTPUT_DIR)
        path = QFileDialog.getExistingDirectory(self, "选择输出目录", current)
        if path:
            self.output_dir_input.setText(path)

    def pick_local_model_dir(self) -> None:
        current = self.local_model_input.text().strip() or str(ROOT)
        path = QFileDialog.getExistingDirectory(self, "选择模型目录", current)
        if path:
            self.local_model_input.setText(path)

    def selected_output_dir(self) -> str:
        return get_selected_output_dir(self.output_dir_input.text())

    def toggle_advanced_card(self) -> None:
        self.env_advanced_visible = not self.env_advanced_visible
        self.advanced_card.setVisible(self.env_advanced_visible)
        self.update_collapsible_geometry(self.advanced_card)

    def open_advanced_settings(self) -> None:
        if self.advanced_settings_dialog is None:
            self.advanced_settings_dialog = AdvancedSettingsDialog(self)
        self.advanced_settings_dialog.sync_model_run_from_main()
        self.advanced_settings_dialog.sync_cookie_access_from_main()
        self.advanced_settings_dialog.show()
        self.advanced_settings_dialog.raise_()
        self.advanced_settings_dialog.activateWindow()
        self.advanced_settings_dialog.run_detection()

    def clear_log(self) -> None:
        self.log_view.clear()

    def update_collapsible_geometry(self, widget: QWidget) -> None:
        layout = widget.layout()
        if layout is not None:
            layout.invalidate()
        widget.updateGeometry()
        central = self.centralWidget()
        if central is not None:
            central.updateGeometry()

    def set_env_summary(self, message: str) -> None:
        self.env_status.setText(f"环境状态：{message}")
        self.update_status_badge()

    def update_status_badge(self) -> None:
        if not hasattr(self, "env_value_label"):
            return
        env_text = self.env_status.text().replace("环境状态：", "").strip()
        state_text = self.result_label.text().replace("当前状态：", "").strip()
        ready = "就绪" in env_text or "准备就绪" in state_text
        failed = "未就绪" in env_text or "失败" in state_text or "缺少" in state_text
        color = "#16a34a" if ready and not failed else "#dc2626" if failed else "#172033"
        summary = env_text if env_text and env_text != "未检查" else state_text
        self.env_value_label.setText(summary or "未检查")
        self.env_value_label.setStyleSheet(f"color: {color}; font-size: 14px; font-weight: 700;")

    def update_model_summary(self) -> None:
        if not hasattr(self, "model_summary_label"):
            return
        model_name = self.model_combo.currentData()
        device = self.device_combo.currentText()
        if is_local_model_choice(model_name):
            local_dir = self.local_model_input.text().strip()
            model_text = "本地模型" if local_dir else "本地模型未选择"
        elif model_name:
            status = "已部署" if model_name in self.deployed_models else "未部署"
            model_text = f"{model_name}（{status}）"
        else:
            model_text = "未选择识别模型"
        self.model_summary_label.setText(f"模型：{model_text}\n设备：{device}")
        if hasattr(self, "model_value_label"):
            self.model_value_label.setText(model_text)
        if hasattr(self, "device_value_label"):
            device_text = "CPU 模式" if device == "cpu" else "GPU 模式" if device == "cuda" else "自动选择"
            self.device_value_label.setText(device_text)
        self.update_footer_summary(model_text, device)

    def update_footer_summary(self, model_text: str | None = None, device: str | None = None) -> None:
        if not hasattr(self, "footer_summary_label"):
            return
        if model_text is None or device is None:
            model_name = self.model_combo.currentData()
            device = self.device_combo.currentText()
            if is_local_model_choice(model_name):
                local_dir = self.local_model_input.text().strip()
                model_text = "本地模型" if local_dir else "本地模型未选择"
            elif model_name:
                status = "已部署" if model_name in self.deployed_models else "未部署"
                model_text = f"{model_name}（{status}）"
            else:
                model_text = "未选择识别模型"
        self.footer_summary_label.setText(f"Whisper 模型：{model_text}  |  设备：{device}")

    def update_model_info(self) -> None:
        model_name = self.model_combo.currentData()
        is_local = is_local_model_choice(model_name)
        self.local_model_label.setVisible(is_local)
        self.local_model_input.setVisible(is_local)
        self.local_model_pick_btn.setVisible(is_local)
        self.model_info_label.setText(get_model_description(model_name, cuda_ok=self.cuda_ok))
        self.update_model_summary()
        if is_local:
            local_dir = self.local_model_input.text().strip()
            if not local_dir:
                self.set_status("未检查")
            elif is_valid_model_dir(local_dir):
                self.set_status("本地模型目录可用")
            elif Path(local_dir).is_dir():
                self.set_status("本地模型目录缺少基本模型文件")
            else:
                self.set_status("本地模型目录不存在")
        elif is_preset_model(model_name):
            self.set_status("已部署" if model_name in self.deployed_models else "未部署")

    def refresh_model_choices(self) -> None:
        selected_value = self.model_combo.currentData()
        local_value = self.local_model_input.text()
        self.deployed_models = scan_deployed_models()
        self.loading_settings = True
        try:
            self.model_combo.clear()
            for label, value in get_model_choices(self.deployed_models):
                self.model_combo.addItem(label, value)
            index = self.model_combo.findData(selected_value)
            self.model_combo.setCurrentIndex(index if index >= 0 else 0)
            self.local_model_input.setText(local_value)
        finally:
            self.loading_settings = False
        self.update_model_info()

    def update_cookie_mode_ui(self) -> None:
        mode = self.cookie_mode_combo.currentData()
        is_browser = mode == "browser"
        is_file = mode == "file"
        self.cookie_browser_label.setVisible(is_browser)
        self.cookie_browser_combo.setVisible(is_browser)
        self.cookies_label.setVisible(is_file)
        self.cookies_input.setVisible(is_file)
        self.cookies_pick_btn.setVisible(is_file)

    def load_settings(self) -> None:
        self.loading_settings = True
        try:
            self.url_input.setText(self.settings.get("url", ""))
            self.ffmpeg_input.setText(self.settings.get("ffmpeg", ""))
            self.ytdlp_input.setText(self.settings.get("yt_dlp", ""))
            self.cookies_input.setText(self.settings.get("cookies", ""))
            self.output_dir_input.setText(self.settings.get("output_dir", DEFAULT_OUTPUT_DIR.name))
            model_selection = resolve_model_from_settings(self.settings)
            index = self.model_combo.findData(model_selection.selected_value)
            self.model_combo.setCurrentIndex(index if index >= 0 else 0)
            self.local_model_input.setText(model_selection.local_value)
            self.device_combo.setCurrentText(self.settings.get("device", "auto"))
            cookie_mode = self.settings.get("cookie_mode", "none")
            cookie_mode_names = [m["name"] for m in COOKIE_MODES]
            if cookie_mode in cookie_mode_names:
                self.cookie_mode_combo.setCurrentIndex(cookie_mode_names.index(cookie_mode))
            browser = self.settings.get("cookies_browser", "chrome")
            browser_lower = browser.lower()
            if browser_lower in COOKIE_BROWSERS:
                self.cookie_browser_combo.setCurrentIndex(COOKIE_BROWSERS.index(browser_lower))
        finally:
            self.loading_settings = False
        self.update_cookie_mode_ui()
        self.update_model_info()

    def selected_model_value(self) -> str:
        return resolve_selected_model(self.model_combo.currentData(), self.local_model_input.text())

    def schedule_save_settings(self) -> None:
        if self.loading_settings:
            return
        self.settings_save_timer.start()

    def save_settings_now(self) -> None:
        if self.loading_settings:
            return
        self.settings_save_timer.stop()
        settings = build_settings_payload({
            "url": self.url_input.text().strip(),
            "ffmpeg": self.ffmpeg_input.text().strip(),
            "yt_dlp": self.ytdlp_input.text().strip(),
            "cookies": self.cookies_input.text().strip(),
            "output_dir": self.output_dir_input.text().strip(),
            "device": self.device_combo.currentText(),
            "cookie_mode": self.cookie_mode_combo.currentData(),
            "cookies_browser": COOKIE_BROWSERS[self.cookie_browser_combo.currentIndex()],
            "selected_model": self.model_combo.currentData(),
            "local_model": self.local_model_input.text(),
        })
        write_settings(settings)

    def set_status(self, message: str) -> None:
        self.result_label.setText(f"当前状态：{message}")
        self.update_status_badge()

    def status_from_log(self, message: str) -> str | None:
        if "开始环境检查" in message or "环境检查线程已启动" in message:
            return "环境检查中"
        if "环境已就绪" in message:
            return "准备就绪"
        if "环境未就绪" in message:
            return "环境未就绪，请检查配置"
        if "获取视频信息" in message:
            return "正在获取视频信息"
        if "查找中文字幕" in message:
            return "正在查找已有中文字幕"
        if "找到" in message and "字幕" in message:
            return "正在下载字幕"
        if "没有可直接下载的中文字幕" in message:
            return "正在准备语音识别"
        if "下载音频" in message or "音频下载完成" in message:
            return "正在下载音频"
        if "正在下载/加载 Whisper 模型" in message:
            return "正在加载识别模型"
        if "开始中文语音识别" in message or "识别进度" in message:
            return "正在语音识别"
        if "已写入文本" in message:
            return "正在保存结果"
        return None

    def append_log(self, message: str) -> None:
        message = clean_log_text(message)
        status = self.status_from_log(message)
        if status:
            self.set_status(status)
        self.log_view.appendPlainText(f"[{timestamp()}] {message}")
        scrollbar = self.log_view.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def append_log_separator(self) -> None:
        self.log_view.appendPlainText("------------------------------")
        scrollbar = self.log_view.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def refresh_buttons(self, busy: bool = False) -> None:
        self.check_button.setEnabled(not busy)
        self.prepare_button.setEnabled(not busy)
        self.update_ytdlp_button.setEnabled(not busy)
        self.gpu_button.setEnabled(not busy)
        self.deploy_model_button.setEnabled(not busy)
        self.start_button.setEnabled(not busy and self.env_ready)
        self.progress.setVisible(busy)

    def run_env_task(self, action: str, autosave: bool = True) -> None:
        self.env_task_autosave = autosave
        if autosave:
            self.save_settings_now()
        action_labels = {
            "check": "开始环境检查",
            "prepare": "开始准备环境",
            "update_ytdlp": "开始更新 yt-dlp",
            "install_gpu": "开始安装 GPU 加速组件",
        }
        self.append_log_separator()
        self.append_log(action_labels.get(action, "开始环境任务"))
        if action == "check":
            self.set_env_summary("检查中")
            self.set_status("环境检查中")
        elif action == "prepare":
            self.set_env_summary("正在准备环境")
            self.set_status("正在自动修复环境")
        elif action == "update_ytdlp":
            self.set_env_summary("正在更新 yt-dlp")
            self.set_status("正在更新 yt-dlp")
        elif action == "install_gpu":
            self.set_env_summary("正在安装 GPU 加速组件")
            self.set_status("正在安装 GPU 加速组件")
        self.env_ready = False
        self.refresh_buttons(True)
        self.thread = QThread()
        self.worker = EnvWorker(
            self.ffmpeg_input.text(),
            self.ytdlp_input.text(),
            action,
        )
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.log.connect(self.append_log)
        self.worker.done.connect(self.env_done)
        self.worker.done.connect(self.thread.quit)
        self.worker.done.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(self.clear_worker)
        self.thread.start()

    def env_done(self, ok: bool, report: dict) -> None:
        self.env_ready = ok
        if report:
            summary = build_env_summary(report, ok)
            self.set_env_summary(summary)
            details_text = format_env_report(report)
            self.env_status.setToolTip(details_text)
            self.env_detail_label.setText(details_text)
            self.cuda_ok = report.get("cuda", {}).get("ok", False)
            self.update_model_info()
        self.append_log("环境已就绪" if ok else "环境未就绪，请配置路径或下载缺失依赖")
        self.set_status("准备就绪" if ok else "环境未就绪，请检查配置")
        self.refresh_buttons(False)

    def clear_worker(self) -> None:
        self.worker = None
        self.thread = None

    def start_extract(self) -> None:
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "缺少链接", "请先输入视频链接。")
            return
        model = self.selected_model_value()
        if is_local_model_choice(self.model_combo.currentData()) and not model:
            QMessageBox.warning(self, "缺少模型", "请选择本地模型目录。")
            return
        if is_preset_model(model):
            model = resolve_preset_model_for_extract(model)
        self.save_settings_now()
        self.set_status("正在启动字幕提取")
        self.output_path = ""
        self.open_button.setEnabled(False)
        self.append_log_separator()
        self.append_log("启动字幕获取工作流")
        self.set_status("正在启动字幕提取")
        self.refresh_buttons(True)

        cookie_mode = self.cookie_mode_combo.currentData()
        cookies_from_browser = None
        cookies = self.cookies_input.text()
        if cookie_mode == "browser":
            cookies_from_browser = COOKIE_BROWSERS[self.cookie_browser_combo.currentIndex()]
            cookies = ""
            self.append_log(f"将从浏览器 {cookies_from_browser.title()} 读取 Cookies")
        elif cookie_mode == "file":
            cookies = self.cookies_input.text()
        else:
            cookies = ""

        self.thread = QThread()
        self.worker = ExtractWorker(
            url=url,
            model=model,
            device=self.device_combo.currentText(),
            cookies=cookies,
            ffmpeg=self.ffmpeg_input.text(),
            yt_dlp=self.ytdlp_input.text(),
            cookies_from_browser=cookies_from_browser,
            output_dir=self.selected_output_dir(),
        )
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.log.connect(self.append_log)
        self.worker.done.connect(self.extract_done)
        self.worker.done.connect(self.thread.quit)
        self.worker.done.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(self.clear_worker)
        self.thread.start()

    def deploy_model(self) -> None:
        selected_value = self.model_combo.currentData()
        model = self.selected_model_value()
        if not selected_value or not model:
            QMessageBox.warning(self, "缺少模型", "请先选择识别模型。")
            return

        model_source = "local" if is_local_model_choice(selected_value) else "preset"
        self.save_settings_now()
        self.append_log_separator()
        self.append_log(
            f"开始部署官方模型：{model}"
            if model_source == "preset"
            else f"开始检查本地模型目录：{model}"
        )
        self.set_status("正在部署模型" if model_source == "preset" else "正在检查本地模型目录")
        self.refresh_buttons(True)
        self.thread = QThread()
        self.worker = ModelDeployWorker(model_source, model)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.done.connect(self.model_deploy_done)
        self.worker.done.connect(self.thread.quit)
        self.worker.done.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(self.clear_worker)
        self.thread.start()

    def model_deploy_done(self, ok: bool, message: str) -> None:
        if ok and is_preset_model(self.model_combo.currentData()):
            self.refresh_model_choices()
        self.set_status(message)
        self.append_log(message)
        if not ok and message.startswith("模型部署失败"):
            QMessageBox.critical(self, "模型部署失败", message)
        self.refresh_buttons(False)

    def extract_done(self, ok: bool, message: str) -> None:
        if ok:
            self.output_path = message
            self.set_status(f"提取完成：{message}")
            self.open_button.setEnabled(True)
            self.append_log("字幕文件获取完成")
        else:
            if "未找到可用字幕" in message and "识别模型" in message:
                self.set_status(f"{MISSING_WHISPER_MODEL_MESSAGE}可展开运行日志查看详情")
            else:
                self.set_status(f"提取失败：{message}。可展开运行日志查看详情")
            self.append_log("字幕文件获取失败")
        self.refresh_buttons(False)

    def open_output_dir(self) -> None:
        path = Path(self.output_path)
        if path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent)))

    def closeEvent(self, event) -> None:
        if self.settings_save_timer.isActive():
            self.save_settings_now()
        super().closeEvent(event)


def main() -> int:
    app = QApplication(sys.argv)
    configure_app_font(app)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
