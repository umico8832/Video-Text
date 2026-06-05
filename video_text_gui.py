#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
import time
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Qt, QTimer
from PySide6.QtGui import QDesktopServices, QFont, QFontDatabase
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QProgressBar,
    QSizePolicy,
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
        "Microsoft YaHei",
        "WenQuanYi Micro Hei",
        "Source Han Sans SC",
    ]
    for family in preferred:
        if family in families:
            app.setFont(QFont(family, 10))
            return


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("视频字幕提取")
        self.resize(980, 720)
        self.settings = read_settings()
        self.env_ready = False
        self.cuda_ok = False
        self.env_advanced_visible = False
        self.log_panel_visible = False
        self.thread: QThread | None = None
        self.worker: QObject | None = None
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
        layout = QVBoxLayout(root)
        layout.setSpacing(12)

        input_box = QGroupBox("字幕获取")
        input_layout = QGridLayout(input_box)
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("粘贴 B 站或 YouTube 视频链接")
        self.model_combo = QComboBox()
        for label, value in get_model_choices(self.deployed_models):
            self.model_combo.addItem(label, value)
        self.model_combo.setCurrentIndex(0)
        self.local_model_input = QLineEdit()
        self.local_model_input.setPlaceholderText("例如 D:/models/faster-whisper-large-v3")
        self.local_model_pick_btn = QPushButton("选择目录")
        self.local_model_pick_btn.clicked.connect(self.pick_local_model_dir)
        self.model_info_label = QLabel("")
        self.model_info_label.setWordWrap(True)
        self.model_info_label.setStyleSheet("color: #555; font-size: 12px;")
        self.output_dir_input = QLineEdit()
        self.output_dir_input.setPlaceholderText(DEFAULT_OUTPUT_DIR.name)
        self.output_dir_pick_btn = QPushButton("选择目录")
        self.output_dir_pick_btn.clicked.connect(self.pick_output_dir)
        self.device_combo = QComboBox()
        self.device_combo.addItems(["auto", "cuda", "cpu"])
        input_layout.addWidget(QLabel("视频链接"), 0, 0)
        input_layout.addWidget(self.url_input, 0, 1, 1, 5)
        input_layout.addWidget(QLabel("Whisper 模型"), 1, 0)
        input_layout.addWidget(self.model_combo, 1, 1)
        input_layout.addWidget(QLabel("设备"), 1, 2)
        input_layout.addWidget(self.device_combo, 1, 3)
        self.local_model_label = QLabel("本地模型目录")
        input_layout.addWidget(self.local_model_label, 2, 0)
        input_layout.addWidget(self.local_model_input, 2, 1, 1, 4)
        input_layout.addWidget(self.local_model_pick_btn, 2, 5)
        input_layout.addWidget(QLabel("输出目录"), 3, 0)
        input_layout.addWidget(self.output_dir_input, 3, 1, 1, 4)
        input_layout.addWidget(self.output_dir_pick_btn, 3, 5)
        strategy_label = QLabel("字幕来源：自动：优先下载视频已有中文字幕，找不到再使用语音识别生成文本。")
        strategy_label.setWordWrap(True)
        strategy_label.setStyleSheet("color: #666;")
        input_layout.addWidget(strategy_label, 4, 0, 1, 6)
        input_layout.addWidget(self.model_info_label, 5, 0, 1, 6)
        self.start_button = QPushButton("开始提取字幕")
        self.deploy_model_button = QPushButton("部署模型")
        self.deploy_model_button.clicked.connect(self.deploy_model)
        self.start_button.setMinimumHeight(42)
        self.start_button.setDefault(True)
        self.start_button.setStyleSheet("font-weight: 600;")
        self.result_label = QLabel("当前状态：等待环境检查")
        self.result_label.setWordWrap(True)
        self.result_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        main_action_layout = QHBoxLayout()
        main_action_layout.addWidget(self.start_button)
        main_action_layout.addWidget(self.deploy_model_button)
        main_action_layout.addWidget(self.result_label, 1)
        input_layout.addLayout(main_action_layout, 6, 0, 1, 6)
        layout.addWidget(input_box)

        env_box = QGroupBox("环境配置")
        env_layout = QVBoxLayout(env_box)
        env_summary_layout = QHBoxLayout()
        self.env_status = QLabel("环境状态：未检查")
        self.env_status.setWordWrap(True)
        self.check_button = QPushButton("检查环境")
        self.prepare_button = QPushButton("准备环境")
        self.env_advanced_button = QPushButton("高级设置")
        env_summary_layout.addWidget(self.env_status, 1)
        env_summary_layout.addWidget(self.check_button)
        env_summary_layout.addWidget(self.prepare_button)
        env_summary_layout.addWidget(self.env_advanced_button)
        env_layout.addLayout(env_summary_layout)

        self.env_advanced_widget = QWidget()
        env_advanced_layout = QGridLayout(self.env_advanced_widget)
        self.ffmpeg_input = QLineEdit()
        self.ytdlp_input = QLineEdit()
        env_advanced_layout.addWidget(QLabel("FFmpeg 路径"), 0, 0)
        env_advanced_layout.addWidget(self.ffmpeg_input, 0, 1)
        env_advanced_layout.addWidget(self.pick_button(self.ffmpeg_input), 0, 2)
        env_advanced_layout.addWidget(QLabel("yt-dlp 路径"), 1, 0)
        env_advanced_layout.addWidget(self.ytdlp_input, 1, 1)
        env_advanced_layout.addWidget(self.pick_button(self.ytdlp_input), 1, 2)

        # Cookie 配置区
        self.cookie_mode_combo = QComboBox()
        for mode in COOKIE_MODES:
            self.cookie_mode_combo.addItem(mode["label"], mode["name"])
        env_advanced_layout.addWidget(QLabel("Cookies"), 2, 0)
        env_advanced_layout.addWidget(self.cookie_mode_combo, 2, 1, 1, 2)

        self.cookie_browser_combo = QComboBox()
        self.cookie_browser_combo.addItems(["Chrome", "Edge", "Firefox"])
        self.cookie_browser_label = QLabel("浏览器")
        env_advanced_layout.addWidget(self.cookie_browser_label, 3, 0)
        env_advanced_layout.addWidget(self.cookie_browser_combo, 3, 1, 1, 2)

        self.cookies_input = QLineEdit()
        self.cookies_input.setPlaceholderText("cookies.txt 文件路径")
        self.cookies_pick_btn = self.pick_button(self.cookies_input)
        self.cookies_label = QLabel("cookies.txt")
        env_advanced_layout.addWidget(self.cookies_label, 4, 0)
        env_advanced_layout.addWidget(self.cookies_input, 4, 1)
        env_advanced_layout.addWidget(self.cookies_pick_btn, 4, 2)

        cookies_note = QLabel("大多数公开视频不需要 Cookies。B 站登录字幕/会员资源或部分 YouTube 资源可能需要。从浏览器读取需要先关闭对应浏览器。")
        cookies_note.setWordWrap(True)
        env_advanced_layout.addWidget(cookies_note, 5, 0, 1, 3)

        self.cookie_browser_label.setVisible(False)
        self.cookie_browser_combo.setVisible(False)
        self.cookies_label.setVisible(False)
        self.cookies_input.setVisible(False)
        self.cookies_pick_btn.setVisible(False)
        self.cookie_mode_combo.currentIndexChanged.connect(self.update_cookie_mode_ui)
        self.update_ytdlp_button = QPushButton("更新 yt-dlp")
        self.gpu_button = QPushButton("安装 GPU 加速组件")
        advanced_actions = QHBoxLayout()
        advanced_actions.addWidget(self.update_ytdlp_button)
        advanced_actions.addWidget(self.gpu_button)
        advanced_actions.addStretch(1)
        env_advanced_layout.addLayout(advanced_actions, 6, 0, 1, 3)
        self.env_detail_label = QLabel("")
        self.env_detail_label.setWordWrap(True)
        self.env_detail_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        env_advanced_layout.addWidget(self.env_detail_label, 7, 0, 1, 3)
        self.env_advanced_widget.setVisible(False)
        env_layout.addWidget(self.env_advanced_widget)
        layout.addWidget(env_box)

        actions = QHBoxLayout()
        self.open_button = QPushButton("打开输出目录")
        self.open_button.setEnabled(False)
        actions.addStretch(1)
        actions.addWidget(self.open_button)
        layout.addLayout(actions)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.hide()
        layout.addWidget(self.progress)

        log_header = QHBoxLayout()
        self.log_toggle_button = QPushButton("运行日志")
        log_header.addWidget(self.log_toggle_button)
        log_header.addStretch(1)
        layout.addLayout(log_header)

        self.log_panel_widget = QWidget()
        log_panel_layout = QVBoxLayout(self.log_panel_widget)
        log_panel_layout.setContentsMargins(0, 0, 0, 0)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        log_panel_layout.addWidget(self.log_view)
        self.log_panel_widget.setVisible(False)
        layout.addWidget(self.log_panel_widget, 1)

        self.check_button.clicked.connect(lambda: self.run_env_task("check"))
        self.prepare_button.clicked.connect(lambda: self.run_env_task("prepare"))
        self.update_ytdlp_button.clicked.connect(lambda: self.run_env_task("update_ytdlp"))
        self.gpu_button.clicked.connect(lambda: self.run_env_task("install_gpu"))
        self.env_advanced_button.clicked.connect(self.toggle_env_advanced)
        self.log_toggle_button.clicked.connect(self.toggle_log_panel)
        self.start_button.clicked.connect(self.start_extract)
        self.open_button.clicked.connect(self.open_output_dir)
        self.model_combo.currentIndexChanged.connect(self.update_model_info)
        self.local_model_input.textChanged.connect(self.update_model_info)
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

    def pick_button(self, target: QLineEdit) -> QPushButton:
        button = QPushButton("选择")
        button.clicked.connect(lambda: self.pick_file(target))
        return button

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

    def toggle_env_advanced(self) -> None:
        self.env_advanced_visible = not self.env_advanced_visible
        self.env_advanced_widget.setVisible(self.env_advanced_visible)
        self.env_advanced_button.setText("收起高级设置" if self.env_advanced_visible else "高级设置")

    def toggle_log_panel(self) -> None:
        self.log_panel_visible = not self.log_panel_visible
        self.log_panel_widget.setVisible(self.log_panel_visible)
        self.log_toggle_button.setText("收起运行日志" if self.log_panel_visible else "运行日志")

    def set_env_summary(self, message: str) -> None:
        self.env_status.setText(f"环境状态：{message}")

    def update_model_info(self) -> None:
        model_name = self.model_combo.currentData()
        is_local = is_local_model_choice(model_name)
        self.local_model_label.setVisible(is_local)
        self.local_model_input.setVisible(is_local)
        self.local_model_pick_btn.setVisible(is_local)
        self.model_info_label.setText(get_model_description(model_name, cuda_ok=self.cuda_ok))
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
            self.loading_settings = not self.env_task_autosave
            try:
                if report.get("ffmpeg", {}).get("path") and not self.ffmpeg_input.text().strip():
                    self.ffmpeg_input.setText(report["ffmpeg"]["path"])
                if report.get("yt-dlp", {}).get("path") and not self.ytdlp_input.text().strip():
                    self.ytdlp_input.setText(report["yt-dlp"]["path"])
            finally:
                self.loading_settings = False
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
