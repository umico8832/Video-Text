#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, QObject, QThread, QTimer, Qt
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
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
    get_model_choices,
    get_model_description,
    is_local_model_choice,
    is_valid_model_dir,
    resolve_selected_model,
)
from settings_manager import DEFAULT_MODEL_DIR
from ui_components import (
    NoWheelComboBox,
    ToolStatusCard,
    create_card,
    create_icon_label,
    decorate_button,
    form_row,
    status_line,
)
from workers import EnvWorker, ModelDeployWorker


ROOT = Path(__file__).resolve().parent

COOKIE_MODES = [
    {"name": "none", "label": "不使用 Cookies"},
    {"name": "browser", "label": "从浏览器读取"},
    {"name": "file", "label": "使用 cookies.txt 文件"},
]
COOKIE_BROWSERS = ["chrome", "edge", "firefox"]


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
        left_layout.addWidget(form_row("Whisper 模型", self.advanced_model_combo))

        self.advanced_device_combo = NoWheelComboBox()
        self.advanced_device_combo.addItem("自动选择", "auto")
        self.advanced_device_combo.addItem("GPU 加速", "cuda")
        self.advanced_device_combo.addItem("CPU 模式", "cpu")
        self.advanced_device_combo.currentIndexChanged.connect(self.advanced_device_changed)
        left_layout.addWidget(form_row("运行方式", self.advanced_device_combo))

        model_dir_layout = QHBoxLayout()
        model_dir_layout.setContentsMargins(0, 0, 0, 0)
        model_dir_layout.setSpacing(8)
        self.model_dir_input = QLineEdit()
        self.model_dir_input.setPlaceholderText(DEFAULT_MODEL_DIR.name)
        self.model_dir_input.setText(self.main_window.model_dir)
        self.model_dir_input.textChanged.connect(self.model_dir_changed)
        self.model_dir_button = QPushButton("浏览")
        self.model_dir_button.setObjectName("smallSecondaryButton")
        self.model_dir_button.clicked.connect(self.pick_model_dir)
        model_dir_layout.addWidget(self.model_dir_input, 1)
        model_dir_layout.addWidget(self.model_dir_button)
        model_dir_widget = QWidget()
        model_dir_widget.setStyleSheet("background: transparent;")
        model_dir_widget.setLayout(model_dir_layout)
        left_layout.addWidget(form_row("模型存放位置", model_dir_widget))

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
        self.advanced_local_model_row = form_row("本地模型目录", local_widget)
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
        self.whisper_status_label = status_line("语音识别：未检测")
        self.cuda_status_label = status_line("GPU 加速：未检测")
        self.whisper_version_label = status_line("faster-whisper 版本：未知")
        for label in (
            self.whisper_status_label,
            self.cuda_status_label,
            self.whisper_version_label,
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
            ("file", "使用 cookies.txt 文件", "使用本地 cookies.txt 文件；软件只保存文件路径，不读取或展示 Cookies 内容。"),
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
        self.advanced_cookie_browser_row = form_row("浏览器", self.advanced_cookie_browser_combo)
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
        self.advanced_cookies_file_row = form_row("cookies.txt", file_row)
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
            message = "请选择 cookies.txt 文件；软件只保存文件路径，不读取或展示 Cookies 内容。"
        elif Path(path).exists():
            message = "将使用所选 cookies.txt 文件路径；软件不会读取或展示 Cookies 内容，请不要上传、分享或提交该文件。"
        else:
            message = "当前路径不存在，请确认 cookies.txt 文件位置；软件只保存路径，不读取或展示内容。"
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
            self.model_dir_input.setText(self.main_window.model_dir)
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

    def model_dir_changed(self) -> None:
        if self.syncing_model_run:
            return
        self.main_window.set_model_dir(self.model_dir_input.text(), save=True)
        self.populate_advanced_model_combo(self.main_window.model_combo.currentData())
        self.update_model_run_controls()

    def pick_model_dir(self) -> None:
        current = self.model_dir_input.text().strip() or str(DEFAULT_MODEL_DIR)
        path = QFileDialog.getExistingDirectory(self, "选择模型下载目录", current)
        if path:
            self.model_dir_input.setText(path)

    def update_model_run_controls(self) -> None:
        if not hasattr(self, "advanced_model_combo"):
            return
        selected_value = self.advanced_model_combo.currentData()
        is_local = is_local_model_choice(selected_value)
        self.advanced_local_model_row.setVisible(is_local)
        model_dir = self.main_window.selected_models_dir()
        self.model_dir_input.setToolTip(model_dir)
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

    def deploy_selected_model(self) -> None:
        if self.thread is not None:
            return
        selected_value = self.advanced_model_combo.currentData()
        model = resolve_selected_model(selected_value, self.advanced_local_model_input.text())
        if not selected_value or not model:
            QMessageBox.warning(self, "缺少模型", "请先选择识别模型。")
            return
        model_source = "local" if is_local_model_choice(selected_value) else "preset"
        if not self.main_window.confirm_model_deploy(model, model_source):
            self.main_window.append_log_separator()
            self.main_window.append_log(f"已取消模型部署：{model}")
            self.advanced_action_status.setText(f"已取消模型部署：{model}")
            return
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
        self.worker = ModelDeployWorker(model_source, model, self.main_window.selected_models_dir())
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
        if not self.main_window.confirm_gpu_install():
            self.main_window.append_log_separator()
            self.main_window.append_log("已取消 GPU 加速组件安装")
            self.advanced_action_status.setText("已取消 GPU 加速组件安装。")
            return
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
        if not self.main_window.confirm_ytdlp_update():
            self.main_window.append_log_separator()
            self.main_window.append_log("已取消更新 yt-dlp")
            return
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

