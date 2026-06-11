#!/usr/bin/env python3
from __future__ import annotations

from PySide6.QtCore import QObject, Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from ui_components import NoWheelComboBox, form_row


COOKIE_BROWSERS = ["chrome", "edge", "firefox"]


def build_cookie_access_tab(dialog) -> QWidget:
    page = QWidget()
    page.setObjectName("cookieAccessPage")
    page.setStyleSheet("""
        QWidget#cookieAccessPage {
            background: #ffffff;
        }
    """)
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
            background: #ffffff;
            border: 1px solid #e1e7ef;
            border-radius: 7px;
        }
        QFrame#cookieOption QLabel,
        QFrame#cookieOption QRadioButton {
            background: transparent;
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

    dialog.cookie_radio_group = QButtonGroup(dialog)
    dialog.cookie_radio_group.setExclusive(True)
    dialog.advanced_cookie_radios: dict[str, QRadioButton] = {}
    dialog.advanced_cookie_option_frames: dict[str, QFrame] = {}
    dialog.advanced_cookie_option_modes: dict[QObject, str] = {}
    cookie_options = [
        ("none", "不使用 Cookies（默认推荐）", "推荐用于 YouTube / 普通公开视频；无需登录时最稳定。"),
        ("file", "使用 cookies.txt 文件（Bilibili / 登录资源推荐）", "稳定性通常高于直读 Chrome / Edge；软件只保存文件路径，不读取或展示 Cookies 内容。"),
        ("browser", "从浏览器读取（便捷，但可能失败）", "可选择 Chrome、Edge 或 Firefox；Chrome / Edge 在部分 Windows 环境可能读取失败。"),
    ]
    for mode, label, description in cookie_options:
        radio = QRadioButton(label)
        dialog.cookie_radio_group.addButton(radio)
        dialog.advanced_cookie_radios[mode] = radio
        option = cookie_option_widget(dialog, mode, radio, description)
        dialog.advanced_cookie_option_frames[mode] = option
        left_layout.addWidget(option)
        radio.toggled.connect(
            lambda checked, selected=mode: dialog.advanced_cookie_mode_changed(selected) if checked else None
        )

    dialog.advanced_cookie_browser_combo = NoWheelComboBox()
    for browser in COOKIE_BROWSERS:
        dialog.advanced_cookie_browser_combo.addItem(browser.title(), browser)
    dialog.advanced_cookie_browser_combo.currentIndexChanged.connect(dialog.advanced_cookie_browser_changed)
    dialog.advanced_cookie_browser_row = form_row("浏览器", dialog.advanced_cookie_browser_combo)
    left_layout.addWidget(dialog.advanced_cookie_browser_row)

    file_row = QWidget()
    file_row.setStyleSheet("background: transparent;")
    file_layout = QHBoxLayout(file_row)
    file_layout.setContentsMargins(0, 0, 0, 0)
    file_layout.setSpacing(8)
    dialog.advanced_cookies_input = QLineEdit()
    dialog.advanced_cookies_input.setPlaceholderText("选择本地 cookies.txt 文件")
    dialog.advanced_cookies_input.textChanged.connect(dialog.advanced_cookies_file_changed)
    dialog.advanced_cookies_pick_btn = QPushButton("选择")
    dialog.advanced_cookies_pick_btn.setObjectName("smallSecondaryButton")
    dialog.advanced_cookies_pick_btn.setIcon(dialog.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton))
    dialog.advanced_cookies_pick_btn.clicked.connect(dialog.pick_advanced_cookies_file)
    file_layout.addWidget(dialog.advanced_cookies_input, 1)
    file_layout.addWidget(dialog.advanced_cookies_pick_btn)
    dialog.advanced_cookies_file_row = form_row("cookies.txt", file_row)
    left_layout.addWidget(dialog.advanced_cookies_file_row)

    dialog.advanced_cookies_status = QLabel("")
    dialog.advanced_cookies_status.setWordWrap(True)
    dialog.advanced_cookies_status.setStyleSheet("color: #64748b; font-weight: 400;")
    left_layout.addWidget(dialog.advanced_cookies_status)
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
    info_title = QLabel("当前选项说明")
    info_title.setStyleSheet("font-size: 14px; font-weight: 600; color: #172033;")
    info_body = QLabel()
    info_body.setWordWrap(True)
    info_body.setStyleSheet("color: #475569; line-height: 150%; font-weight: 400;")
    dialog.advanced_cookie_info_body = info_body
    right_layout.addWidget(info_title)
    right_layout.addWidget(info_body)
    right_layout.addStretch(1)
    content_layout.addWidget(right, 2)

    layout.addLayout(content_layout, 1)
    dialog.sync_cookie_access_from_main()
    return page


def cookie_option_widget(dialog, mode: str, radio: QRadioButton, description: str) -> QFrame:
    frame = QFrame()
    frame.setObjectName("cookieOption")
    frame.setCursor(Qt.CursorShape.PointingHandCursor)
    frame.installEventFilter(dialog)
    dialog.advanced_cookie_option_modes[frame] = mode
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(12, 10, 12, 10)
    layout.setSpacing(4)
    desc_label = QLabel(description)
    desc_label.setWordWrap(True)
    desc_label.setStyleSheet("color: #64748b; background: transparent; font-weight: 400;")
    desc_label.setCursor(Qt.CursorShape.PointingHandCursor)
    desc_label.installEventFilter(dialog)
    dialog.advanced_cookie_option_modes[desc_label] = mode
    radio.setCursor(Qt.CursorShape.PointingHandCursor)
    layout.addWidget(radio)
    layout.addWidget(desc_label)
    return frame
