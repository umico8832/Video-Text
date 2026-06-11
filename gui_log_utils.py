from __future__ import annotations

import re
import time
from dataclasses import dataclass


ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


@dataclass(frozen=True)
class FailureLogParts:
    reason: str
    suggestions: list[str]
    details: list[str]


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


def parse_failure_log(message: str) -> FailureLogParts:
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
    return FailureLogParts(reason, suggestions, details)
