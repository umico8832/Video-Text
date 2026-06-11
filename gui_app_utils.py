from __future__ import annotations

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication


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
