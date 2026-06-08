#!/usr/bin/env python3
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from ui_components import ToolStatusCard


def build_environment_tab(dialog) -> QWidget:
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
    dialog.update_tools_button = QPushButton("更新 yt-dlp")
    dialog.redetect_button = QPushButton("重新检测")
    dialog.restore_button = QPushButton("恢复使用内置工具")
    dialog.update_tools_button.setObjectName("smallSecondaryButton")
    dialog.redetect_button.setObjectName("smallSecondaryButton")
    dialog.restore_button.setObjectName("linkButton")
    dialog.restore_button.setFlat(True)
    dialog.restore_button.setCursor(Qt.CursorShape.PointingHandCursor)
    dialog.update_tools_button.clicked.connect(dialog.update_tools)
    dialog.redetect_button.clicked.connect(dialog.run_detection)
    dialog.restore_button.clicked.connect(dialog.restore_builtin_tools)
    tools_header.addWidget(tools_title, 1)
    tools_header.addWidget(dialog.redetect_button)
    left.addLayout(tools_header)

    dialog.ffmpeg_card = ToolStatusCard(
        "FFmpeg",
        dialog.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon),
        show_version=False,
    )
    dialog.ytdlp_card = ToolStatusCard(
        "yt-dlp",
        dialog.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon),
    )
    dialog.ffmpeg_card.path_box.clicked.connect(lambda: dialog.choose_tool_path("ffmpeg"))
    dialog.ytdlp_card.path_box.clicked.connect(lambda: dialog.choose_tool_path("yt_dlp"))
    left.addWidget(dialog.ffmpeg_card)
    left.addWidget(dialog.ytdlp_card)

    light_actions = QHBoxLayout()
    light_actions.setContentsMargins(2, 2, 0, 0)
    light_actions.setSpacing(12)
    light_actions.addWidget(dialog.restore_button, 0, Qt.AlignmentFlag.AlignLeft)
    light_actions.addStretch(1)
    light_actions.addWidget(dialog.update_tools_button, 0, Qt.AlignmentFlag.AlignRight)
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
