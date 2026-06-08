from __future__ import annotations

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListView,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


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
