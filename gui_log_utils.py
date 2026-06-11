from __future__ import annotations

import re
import time


ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def timestamp() -> str:
    return time.strftime("%H:%M:%S")


def clean_log_text(message: str) -> str:
    return ANSI_RE.sub("", message)


def failure_summary(message: str) -> str:
    first_line = next((line.strip() for line in message.splitlines() if line.strip()), message.strip())
    if first_line.startswith("Bilibili 获取失败"):
        return "Bilibili 获取失败"
    if first_line.startswith("读取 Chrome Cookie 失败"):
        return "读取 Chrome Cookie 失败"
    if first_line.startswith("读取 Edge Cookie 失败"):
        return "读取 Edge Cookie 失败"
    if first_line.startswith("读取 Firefox Cookie 失败"):
        return "读取 Firefox Cookie 失败"
    return first_line.rstrip("。")
