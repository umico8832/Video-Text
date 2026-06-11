#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QEvent, QObject, QThread, Qt, QTimer
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
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
from gui_app_utils import configure_app_font
from gui_cookie_utils import selected_cookie_browser
from gui_log_utils import clean_log_text, failure_summary, timestamp
from model_picker_dialog import ModelPickerDialog
from ui_components import (
    NoWheelComboBox,
    ToolStatusCard,
    create_card,
    create_icon_label,
    create_pick_button,
    create_status_card,
    decorate_button,
    form_label,
    form_row,
    status_line,
)
from model_config import (
    MISSING_WHISPER_MODEL_MESSAGE,
    get_model_choices,
    get_model_description,
    is_english_only_model,
    is_local_model_choice,
    is_preset_model,
    is_valid_model_dir,
    resolve_model_for_runtime,
    resolve_model_from_settings,
    resolve_selected_model,
    scan_deployed_models,
)
from settings_manager import (
    DEFAULT_MODEL_DIR,
    DEFAULT_OUTPUT_DIR,
    build_settings_payload,
    load_settings as read_settings,
    normalize_model_dir,
    save_settings as write_settings,
    selected_output_dir as get_selected_output_dir,
)
from workers import EnvWorker, ExtractWorker, ModelDeployWorker


ROOT = Path(__file__).resolve().parent

from advanced_settings_dialog import AdvancedSettingsDialog, COOKIE_BROWSERS, COOKIE_MODES


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
        self.pending_extract_model_download: tuple[str, str] | None = None
        self.model_dir = normalize_model_dir(self.settings.get("model_dir"))
        self.deployed_models = scan_deployed_models(self.selected_models_dir())
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
        decorate_button(self, self.output_dir_pick_btn, QStyle.StandardPixmap.SP_DirOpenIcon)
        self.output_dir_pick_btn.clicked.connect(self.pick_output_dir)
        self.open_button = QPushButton("打开目录")
        decorate_button(self, self.open_button, QStyle.StandardPixmap.SP_DialogOpenButton)
        self.open_button.setEnabled(True)

        self.model_combo = NoWheelComboBox()
        for label, value in get_model_choices(self.deployed_models):
            self.model_combo.addItem(label, value)
        self.model_combo.setCurrentIndex(0)
        self.local_model_input = QLineEdit()
        self.local_model_input.setPlaceholderText("例如 D:/models/faster-whisper-large-v3")
        self.local_model_pick_btn = QPushButton("选择目录")
        decorate_button(self, self.local_model_pick_btn, QStyle.StandardPixmap.SP_DirOpenIcon)
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
        decorate_button(self, self.advanced_button, QStyle.StandardPixmap.SP_FileDialogDetailedView)
        self.advanced_button.setMinimumHeight(40)
        header_layout.addWidget(self.advanced_button, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(header_layout)

        self.advanced_card = create_card()
        advanced_layout = QVBoxLayout(self.advanced_card)
        advanced_layout.setContentsMargins(24, 22, 24, 22)
        advanced_placeholder = QLabel("")
        advanced_placeholder.setMinimumHeight(120)
        advanced_layout.addWidget(advanced_placeholder)
        self.advanced_card.setVisible(False)
        layout.addWidget(self.advanced_card)

        main_card = create_card()
        main_layout = QGridLayout(main_card)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setHorizontalSpacing(16)
        main_layout.setVerticalSpacing(18)
        main_layout.setColumnStretch(1, 1)
        main_layout.setColumnMinimumWidth(0, 150)
        main_layout.addWidget(
            create_icon_label(self, "视频链接", QStyle.StandardPixmap.SP_FileLinkIcon),
            0,
            0,
        )
        main_layout.addWidget(self.url_input, 0, 1, 1, 3)
        main_layout.addWidget(
            create_icon_label(self, "输出目录", QStyle.StandardPixmap.SP_DirIcon),
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
        self.model_config_card = create_status_card(
            self,
            "模型",
            self.model_value_label,
            QStyle.StandardPixmap.SP_DriveNetIcon,
            action_text="选择",
            on_click=self.open_model_picker,
        )
        self.device_config_card = create_status_card(
            self,
            "运行方式",
            self.device_value_label,
            QStyle.StandardPixmap.SP_ComputerIcon,
            action_text="选择",
            on_click=self.open_device_menu,
        )
        config_layout.addWidget(self.model_config_card, 1)
        config_layout.addWidget(self.device_config_card, 1)
        config_layout.addWidget(create_status_card(self, "环境状态", self.env_value_label, QStyle.StandardPixmap.SP_DialogApplyButton), 1)
        main_layout.addWidget(
            create_icon_label(self, "当前配置", QStyle.StandardPixmap.SP_FileDialogInfoView),
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
        decorate_button(self, self.start_button, QStyle.StandardPixmap.SP_MediaPlay)
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
        for browser in COOKIE_BROWSERS:
            self.cookie_browser_combo.addItem(browser.title(), browser)
        self.browser_combo = self.cookie_browser_combo
        self.cookie_browser_label = form_label("浏览器")
        self.cookies_input = QLineEdit()
        self.cookies_input.setPlaceholderText("cookies.txt 文件路径")
        self.cookies_pick_btn = create_pick_button(self, self.cookies_input, self.pick_file)
        self.cookies_label = form_label("cookies.txt")
        self.check_button = QPushButton("检查环境")
        self.prepare_button = QPushButton("准备环境")
        self.update_ytdlp_button = QPushButton("更新 yt-dlp")
        self.gpu_button = QPushButton("安装 GPU 加速组件")
        self.env_detail_label = QLabel("")
        self.env_detail_label.setWordWrap(True)
        self.env_detail_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.cookie_mode_combo.currentIndexChanged.connect(self.handle_cookie_mode_changed)
        self.local_model_label = form_label("本地模型目录")
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

        log_card = create_card()
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
        decorate_button(self, self.log_toggle_button, QStyle.StandardPixmap.SP_TrashIcon)
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
            QPlainTextEdit#logView QScrollBar:vertical {
                width: 9px;
                background: transparent;
                border: none;
                margin: 0;
            }
            QPlainTextEdit#logView QScrollBar::handle:vertical {
                min-height: 28px;
                background: #cbd5e1;
                border-radius: 4px;
            }
            QPlainTextEdit#logView QScrollBar::handle:vertical:hover {
                background: #94a3b8;
            }
            QPlainTextEdit#logView QScrollBar::add-line:vertical,
            QPlainTextEdit#logView QScrollBar::sub-line:vertical {
                height: 0;
                background: transparent;
                border: none;
            }
            QPlainTextEdit#logView QScrollBar::add-page:vertical,
            QPlainTextEdit#logView QScrollBar::sub-page:vertical {
                background: transparent;
            }
        """)
        log_panel_layout = QVBoxLayout(self.log_panel_widget)
        log_panel_layout.setContentsMargins(8, 8, 8, 8)
        self.log_view = QPlainTextEdit()
        self.log_view.setObjectName("logView")
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
        help_label = QLabel('<a href="help">帮助文档</a>')
        help_label.setTextFormat(Qt.TextFormat.RichText)
        help_label.setTextInteractionFlags(Qt.TextInteractionFlag.LinksAccessibleByMouse)
        help_label.setCursor(Qt.CursorShape.PointingHandCursor)
        help_label.setStyleSheet("color: #2563eb; font-weight: 600;")
        help_label.linkActivated.connect(self.open_help_document)
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
        self.update_ytdlp_button.clicked.connect(self.update_ytdlp_with_confirmation)
        self.gpu_button.clicked.connect(self.install_gpu_with_confirmation)
        self.advanced_button.clicked.connect(self.open_advanced_settings)
        self.log_toggle_button.clicked.connect(self.clear_log)
        self.start_button.clicked.connect(self.start_extract)
        self.open_button.clicked.connect(self.open_output_dir)
        self.model_combo.currentIndexChanged.connect(self.handle_model_changed)
        self.local_model_input.textChanged.connect(self.update_model_info)
        self.device_combo.currentTextChanged.connect(self.handle_device_changed)
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
            self.append_log(f"输出目录已设置为：{path}")

    def pick_local_model_dir(self) -> None:
        current = self.local_model_input.text().strip() or str(ROOT)
        path = QFileDialog.getExistingDirectory(self, "选择模型目录", current)
        if path:
            self.local_model_input.setText(path)

    def selected_output_dir(self) -> str:
        return get_selected_output_dir(self.output_dir_input.text())

    def output_dir_path(self) -> Path:
        value = self.output_dir_input.text().strip() or DEFAULT_OUTPUT_DIR.name
        path = Path(value)
        return path if path.is_absolute() else ROOT / path

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

    def open_help_document(self) -> None:
        help_url = "https://github.com/umico8832/Video-Text"
        if not QDesktopServices.openUrl(QUrl(help_url)):
            QMessageBox.warning(
                self,
                "无法打开帮助文档",
                f"无法打开帮助文档，请手动访问：\n{help_url}",
            )

    def confirm_model_deploy(self, model_name: str, model_source: str) -> bool:
        models_dir = self.selected_models_dir()
        message_box = QMessageBox(self)
        message_box.setIcon(QMessageBox.Icon.Question)
        message_box.setWindowTitle("确认下载/部署模型")
        if model_source == "preset":
            message_box.setText(f"即将下载/部署 Whisper 模型：{model_name}")
            message_box.setInformativeText(
                "该操作可能需要联网，并占用一定磁盘空间。\n"
                f"模型将保存到：{models_dir}\n\n"
                "是否继续？"
            )
        else:
            message_box.setText(f"即将检查本地 Whisper 模型目录：{model_name}")
            message_box.setInformativeText(
                "该操作不会下载模型，只会检查所选目录是否可用。\n\n"
                "是否继续？"
            )
        continue_button = message_box.addButton("继续部署", QMessageBox.ButtonRole.AcceptRole)
        message_box.addButton("取消", QMessageBox.ButtonRole.RejectRole)
        message_box.exec()
        return message_box.clickedButton() is continue_button

    def confirm_gpu_install(self) -> bool:
        message_box = QMessageBox(self)
        message_box.setIcon(QMessageBox.Icon.Question)
        message_box.setWindowTitle("确认安装 GPU 加速组件")
        message_box.setText("即将安装 GPU 加速组件。")
        message_box.setInformativeText(
            "该操作会安装 NVIDIA CUDA 相关 Python 包，适用于 NVIDIA 显卡用户。\n"
            "它不会安装显卡驱动，也不会保证所有 CUDA 环境问题都能自动修复。\n"
            "安装可能耗时，并会修改当前 Python 虚拟环境。\n\n"
            "是否继续？"
        )
        continue_button = message_box.addButton("继续安装", QMessageBox.ButtonRole.AcceptRole)
        message_box.addButton("取消", QMessageBox.ButtonRole.RejectRole)
        message_box.exec()
        return message_box.clickedButton() is continue_button

    def confirm_ytdlp_update(self) -> bool:
        message_box = QMessageBox(self)
        message_box.setIcon(QMessageBox.Icon.Question)
        message_box.setWindowTitle("确认更新 yt-dlp")
        message_box.setText("即将更新 yt-dlp 下载组件。")
        message_box.setInformativeText(
            "该操作可能需要联网，只会更新 yt-dlp，不会更新 FFmpeg。\n"
            "如果当前使用的是手动指定的外部 yt-dlp，请确认是否继续。\n\n"
            "是否继续？"
        )
        continue_button = message_box.addButton("继续更新", QMessageBox.ButtonRole.AcceptRole)
        message_box.addButton("取消", QMessageBox.ButtonRole.RejectRole)
        message_box.exec()
        return message_box.clickedButton() is continue_button

    def update_ytdlp_with_confirmation(self) -> None:
        if not self.confirm_ytdlp_update():
            self.append_log_separator()
            self.append_log("已取消更新 yt-dlp")
            return
        self.run_env_task("update_ytdlp")

    def install_gpu_with_confirmation(self) -> None:
        if not self.confirm_gpu_install():
            self.append_log_separator()
            self.append_log("已取消 GPU 加速组件安装")
            return
        self.run_env_task("install_gpu")

    def handle_model_changed(self) -> None:
        self.update_model_info()
        if self.loading_settings:
            return
        model = self.model_combo.currentData() or "未选择"
        self.append_log(f"已切换模型：{model}")

    def handle_device_changed(self) -> None:
        self.update_model_summary()
        if self.loading_settings:
            return
        mode = self.device_combo.currentText()
        mode_text = {"auto": "自动选择", "cuda": "GPU 加速", "cpu": "CPU 模式"}.get(mode, mode)
        self.append_log(f"已切换运行方式：{mode_text}")

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
        self.deployed_models = scan_deployed_models(self.selected_models_dir())
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

    def refresh_model_deployment_state(self, selected_value: str | None = None) -> None:
        current_value = selected_value if selected_value is not None else self.model_combo.currentData()
        self.refresh_model_choices()
        if current_value:
            index = self.model_combo.findData(current_value)
            if index >= 0 and self.model_combo.currentIndex() != index:
                self.model_combo.setCurrentIndex(index)
        self.update_model_summary()
        if self.advanced_settings_dialog is not None:
            self.advanced_settings_dialog.populate_advanced_model_combo(self.model_combo.currentData())
            self.advanced_settings_dialog.sync_model_run_from_main()
            self.advanced_settings_dialog.update_model_run_controls()

    def refresh_pending_extract_model_download(self, log_completion: bool = True) -> bool:
        pending_download = self.pending_extract_model_download
        if not pending_download:
            return False
        model_name, download_dir = pending_download
        if not is_preset_model(model_name) or not is_valid_model_dir(download_dir):
            return False
        self.refresh_model_deployment_state(model_name)
        if log_completion:
            self.append_log(f"Whisper 模型已下载完成：{model_name}")
        self.append_log("模型状态已刷新，可离线使用。")
        self.pending_extract_model_download = None
        return True

    def update_cookie_mode_ui(self) -> None:
        mode = self.cookie_mode_combo.currentData()
        is_browser = mode == "browser"
        is_file = mode == "file"
        self.cookie_browser_label.setVisible(is_browser)
        self.cookie_browser_combo.setVisible(is_browser)
        self.cookies_label.setVisible(is_file)
        self.cookies_input.setVisible(is_file)
        self.cookies_pick_btn.setVisible(is_file)

    def handle_cookie_mode_changed(self) -> None:
        self.update_cookie_mode_ui()
        if self.loading_settings:
            return
        mode = self.cookie_mode_combo.currentData()
        label = next((item["label"] for item in COOKIE_MODES if item["name"] == mode), mode or "未知")
        self.append_log(f"Cookies 模式已切换为：{label}")

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

    def selected_models_dir(self) -> str:
        value = normalize_model_dir(self.model_dir)
        path = Path(value)
        if path.is_absolute():
            return str(path)
        return str((ROOT / path).resolve())

    def set_model_dir(self, value: str | None, save: bool = False) -> None:
        self.model_dir = normalize_model_dir(value)
        self.deployed_models = scan_deployed_models(self.selected_models_dir())
        self.refresh_model_choices()
        self.update_model_summary()
        if save:
            self.save_settings_now()

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
            "model_dir": self.model_dir,
            "device": self.device_combo.currentText(),
            "cookie_mode": self.cookie_mode_combo.currentData(),
            "cookies_browser": selected_cookie_browser(self.cookie_browser_combo, COOKIE_BROWSERS),
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
        if "查找视频自带中文字幕" in message:
            return "正在查找已有中文字幕"
        if "查找视频自带英文字幕" in message:
            return "正在查找已有英文字幕"
        if "已找到视频自带中文字幕" in message or "已找到视频自带英文字幕" in message:
            return "正在下载字幕"
        if "未找到可用中文字幕" in message or "未找到可用英文字幕" in message:
            return "正在准备语音识别"
        if "下载音频" in message or "音频下载完成" in message:
            return "正在下载音频"
        if "正在加载本地 Whisper 模型" in message or "开始下载 Whisper 模型" in message:
            return "正在加载识别模型"
        if "已取消：未下载 Whisper 模型" in message:
            return "已取消"
        if "正在识别音频内容" in message or "识别进度" in message:
            return "正在语音识别"
        if "字幕文本已保存到" in message:
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
        if "Whisper 模型已下载完成" in message:
            self.refresh_pending_extract_model_download(log_completion=False)
        elif "Whisper 模型已下载到本地目录" in message:
            self.refresh_pending_extract_model_download()

    def append_failure_log(self, message: str) -> None:
        message = clean_log_text(message).strip()
        lines = [line.strip() for line in message.splitlines() if line.strip()]
        reason = lines[0] if lines else "未知错误"
        suggestions: list[str] = []
        details: list[str] = []
        target: list[str] | None = None
        for line in lines[1:]:
            if line == "建议：":
                target = suggestions
                continue
            if line.startswith("详情："):
                target = details
                detail = line.removeprefix("详情：").strip()
                if detail:
                    details.append(detail)
                continue
            if target is not None:
                target.append(line)
        self.append_log("提取失败。")
        self.append_log(f"原因：{reason}")
        if suggestions:
            self.append_log("建议：" + "\n" + "\n".join(suggestions))
        if details:
            self.append_log("详情：" + "\n" + "\n".join(details))

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
        self.open_button.setEnabled(not busy)
        self.progress.setVisible(busy)

    def start_worker(self, worker: QObject, done_signal, done_slot, log_signal=None) -> None:
        self.thread = QThread()
        self.worker = worker
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        if log_signal is not None:
            log_signal.connect(self.append_log)
        done_signal.connect(done_slot)
        done_signal.connect(self.thread.quit)
        done_signal.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(self.clear_worker)
        self.thread.start()

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
        worker = EnvWorker(
            self.ffmpeg_input.text(),
            self.ytdlp_input.text(),
            action,
        )
        self.start_worker(worker, worker.done, self.env_done, worker.log)

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
        selected_value = self.model_combo.currentData()
        runtime_model = resolve_model_for_runtime(
            selected_value,
            self.local_model_input.text(),
            self.selected_models_dir(),
        )
        if runtime_model.error_message:
            QMessageBox.warning(self, "模型不可用", runtime_model.error_message)
            self.append_log_separator()
            self.append_log(runtime_model.error_message)
            return
        prompt_logged = False
        if runtime_model.requires_download:
            self.append_log_separator()
            self.append_log(f"未检测到本地 Whisper 模型：{runtime_model.display_name}")
            prompt_logged = True
            message_box = QMessageBox(self)
            message_box.setIcon(QMessageBox.Icon.Question)
            message_box.setWindowTitle("需要下载 Whisper 模型")
            message_box.setText(f"当前未检测到本地 Whisper 模型：{runtime_model.display_name}。")
            message_box.setInformativeText(
                "继续识别需要下载该模型，可能占用一定时间和磁盘空间。\n是否现在下载并继续？"
            )
            download_button = message_box.addButton("下载并继续", QMessageBox.ButtonRole.AcceptRole)
            message_box.addButton("取消", QMessageBox.ButtonRole.RejectRole)
            message_box.exec()
            if message_box.clickedButton() is not download_button:
                self.append_log("已取消：未下载 Whisper 模型，识别任务未开始。")
                self.set_status("已取消")
                self.refresh_buttons(False)
                return
            self.append_log(f"用户已确认下载，开始下载 Whisper 模型：{runtime_model.display_name}")
            self.append_log(f"Whisper 模型将保存到本地目录：{runtime_model.download_dir}")
        self.save_settings_now()
        self.set_status("正在启动字幕提取")
        self.output_path = ""
        self.pending_extract_model_download = None
        if not prompt_logged:
            self.append_log_separator()
        self.append_log("启动字幕获取工作流")
        self.set_status("正在启动字幕提取")
        self.refresh_buttons(True)

        cookie_mode = self.cookie_mode_combo.currentData()
        cookies_from_browser = None
        cookies = self.cookies_input.text()
        if cookie_mode == "browser":
            cookies_from_browser = selected_cookie_browser(self.cookie_browser_combo, COOKIE_BROWSERS)
            cookies = ""
            self.append_log(f"正在尝试从浏览器 {cookies_from_browser.title()} 读取 Cookies...")
        elif cookie_mode == "file":
            cookies = self.cookies_input.text()
            if cookies.strip():
                self.append_log(f"已选择 cookies.txt 文件：{Path(cookies).name or 'cookies.txt'}，本次请求将使用该文件。")
            else:
                self.append_log("已选择 cookies.txt 文件模式，但尚未填写文件路径。")
        else:
            cookies = ""
            self.append_log("未启用 Cookies，本次请求不会使用登录态。")

        worker = ExtractWorker(
            url=url,
            model=runtime_model.model,
            device=self.device_combo.currentText(),
            cookies=cookies,
            ffmpeg=self.ffmpeg_input.text(),
            yt_dlp=self.ytdlp_input.text(),
            cookies_from_browser=cookies_from_browser,
            output_dir=self.selected_output_dir(),
            model_display_name=runtime_model.display_name,
            model_is_local=runtime_model.is_local,
            model_download_name=runtime_model.download_model,
            model_download_dir=runtime_model.download_dir,
            subtitle_language="en" if is_english_only_model(selected_value) else "zh",
        )
        if runtime_model.download_model and runtime_model.download_dir:
            self.pending_extract_model_download = (
                runtime_model.download_model,
                runtime_model.download_dir,
            )
        self.start_worker(worker, worker.done, self.extract_done, worker.log)

    def deploy_model(self) -> None:
        selected_value = self.model_combo.currentData()
        model = self.selected_model_value()
        if not selected_value or not model:
            QMessageBox.warning(self, "缺少模型", "请先选择识别模型。")
            return

        model_source = "local" if is_local_model_choice(selected_value) else "preset"
        if not self.confirm_model_deploy(model, model_source):
            self.append_log_separator()
            self.append_log(f"已取消模型部署：{model}")
            return
        self.save_settings_now()
        self.append_log_separator()
        self.append_log(
            f"开始部署官方模型：{model}"
            if model_source == "preset"
            else f"开始检查本地模型目录：{model}"
        )
        self.set_status("正在部署模型" if model_source == "preset" else "正在检查本地模型目录")
        self.refresh_buttons(True)
        worker = ModelDeployWorker(model_source, model, self.selected_models_dir())
        self.start_worker(worker, worker.done, self.model_deploy_done)

    def model_deploy_done(self, ok: bool, message: str) -> None:
        selected_value = self.model_combo.currentData()
        if ok and is_preset_model(selected_value):
            self.refresh_model_deployment_state(selected_value)
            self.append_log(f"Whisper 模型已下载完成：{selected_value}")
            self.append_log("模型状态已刷新，可离线使用。")
        self.set_status(message)
        self.append_log(message)
        if not ok and message.startswith("模型部署失败"):
            QMessageBox.critical(self, "模型部署失败", message)
        self.refresh_buttons(False)

    def extract_done(self, ok: bool, message: str) -> None:
        if ok:
            self.refresh_pending_extract_model_download()
            self.output_path = message
            self.set_status(f"提取完成：{message}")
            self.append_log("提取完成。")
        else:
            summary = failure_summary(message)
            if "未找到可用字幕" in message and "识别模型" in message:
                self.set_status(f"{MISSING_WHISPER_MODEL_MESSAGE}可展开运行日志查看详情")
            else:
                self.set_status(f"提取失败：{summary}。可展开运行日志查看详情")
            self.append_failure_log(message)
        self.pending_extract_model_download = None
        self.refresh_buttons(False)

    def open_output_dir(self) -> None:
        path = self.output_dir_path()
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            QMessageBox.warning(self, "无法打开目录", f"输出目录不可用：{exc}")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

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
