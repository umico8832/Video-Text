#!/usr/bin/env python3
from __future__ import annotations

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from settings_manager import DEFAULT_MODEL_DIR
from ui_components import NoWheelComboBox, form_row, status_line


def build_model_run_tab(dialog) -> QWidget:
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

    dialog.advanced_model_combo = NoWheelComboBox()
    dialog.populate_advanced_model_combo(dialog.main_window.model_combo.currentData())
    dialog.advanced_model_combo.currentIndexChanged.connect(dialog.advanced_model_changed)
    left_layout.addWidget(form_row("Whisper 模型", dialog.advanced_model_combo))

    dialog.advanced_device_combo = NoWheelComboBox()
    dialog.advanced_device_combo.addItem("自动选择", "auto")
    dialog.advanced_device_combo.addItem("GPU 加速", "cuda")
    dialog.advanced_device_combo.addItem("CPU 模式", "cpu")
    dialog.advanced_device_combo.currentIndexChanged.connect(dialog.advanced_device_changed)
    left_layout.addWidget(form_row("运行方式", dialog.advanced_device_combo))

    model_dir_layout = QHBoxLayout()
    model_dir_layout.setContentsMargins(0, 0, 0, 0)
    model_dir_layout.setSpacing(8)
    dialog.model_dir_input = QLineEdit()
    dialog.model_dir_input.setPlaceholderText(DEFAULT_MODEL_DIR.name)
    dialog.model_dir_input.setText(dialog.main_window.model_dir)
    dialog.model_dir_input.textChanged.connect(dialog.model_dir_changed)
    dialog.model_dir_button = QPushButton("浏览")
    dialog.model_dir_button.setObjectName("smallSecondaryButton")
    dialog.model_dir_button.clicked.connect(dialog.pick_model_dir)
    model_dir_layout.addWidget(dialog.model_dir_input, 1)
    model_dir_layout.addWidget(dialog.model_dir_button)
    model_dir_widget = QWidget()
    model_dir_widget.setStyleSheet("background: transparent;")
    model_dir_widget.setLayout(model_dir_layout)
    left_layout.addWidget(form_row("模型存放位置", model_dir_widget))

    dialog.advanced_local_model_label = QLabel("本地模型目录")
    dialog.advanced_local_model_label.setStyleSheet("color: #475569; font-weight: 700;")
    local_layout = QHBoxLayout()
    local_layout.setContentsMargins(0, 0, 0, 0)
    local_layout.setSpacing(8)
    dialog.advanced_local_model_input = QLineEdit()
    dialog.advanced_local_model_input.setPlaceholderText("例如 D:/models/faster-whisper-large-v3")
    dialog.advanced_local_model_input.textChanged.connect(dialog.advanced_local_model_changed)
    dialog.advanced_local_model_button = QPushButton("浏览")
    dialog.advanced_local_model_button.setObjectName("smallSecondaryButton")
    dialog.advanced_local_model_button.clicked.connect(dialog.pick_advanced_local_model_dir)
    local_layout.addWidget(dialog.advanced_local_model_input, 1)
    local_layout.addWidget(dialog.advanced_local_model_button)
    local_widget = QWidget()
    local_widget.setStyleSheet("background: transparent;")
    local_widget.setLayout(local_layout)
    dialog.advanced_local_model_row = form_row("本地模型目录", local_widget)
    left_layout.addWidget(dialog.advanced_local_model_row)

    dialog.advanced_model_info = QPlainTextEdit()
    dialog.advanced_model_info.setReadOnly(True)
    dialog.advanced_model_info.setMinimumHeight(132)
    dialog.advanced_model_info.setMaximumHeight(150)
    dialog.advanced_model_info.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
    dialog.advanced_model_info.setStyleSheet("""
        QPlainTextEdit {
            color: #475569;
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 7px;
            padding: 8px 10px;
            font-weight: 400;
        }
    """)
    left_layout.addWidget(dialog.advanced_model_info)

    actions = QHBoxLayout()
    actions.setContentsMargins(0, 2, 0, 0)
    actions.setSpacing(10)
    dialog.advanced_deploy_button = QPushButton("下载/部署所选模型")
    dialog.advanced_deploy_button.clicked.connect(dialog.deploy_selected_model)
    dialog.advanced_gpu_button = QPushButton("安装 GPU 加速组件")
    dialog.advanced_gpu_button.clicked.connect(dialog.install_gpu_components)
    actions.addWidget(dialog.advanced_deploy_button)
    actions.addWidget(dialog.advanced_gpu_button)
    left_layout.addLayout(actions)

    dialog.advanced_action_status = QLabel("设置会自动保存；部署和安装会在后台执行。")
    dialog.advanced_action_status.setWordWrap(True)
    dialog.advanced_action_status.setStyleSheet("color: #64748b; font-weight: 400;")
    left_layout.addWidget(dialog.advanced_action_status)
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
    dialog.whisper_status_label = status_line("语音识别：未检测")
    dialog.cuda_status_label = status_line("GPU 加速：未检测")
    dialog.whisper_version_label = status_line("faster-whisper 版本：未知")
    for label in (
        dialog.whisper_status_label,
        dialog.cuda_status_label,
        dialog.whisper_version_label,
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
    dialog.sync_model_run_from_main()
    dialog.update_model_run_controls()
    return page
