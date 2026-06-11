from __future__ import annotations

import json
import re
from html import unescape
from pathlib import Path
from typing import Any


def clean_lines(lines: list[str]) -> str:
    cleaned: list[str] = []
    previous = ""
    for line in lines:
        line = unescape(line)
        line = re.sub(r"<[^>]+>", "", line)
        line = re.sub(r"\{\\.*?\}", "", line)
        line = line.replace("\\N", "\n")
        parts = [part.strip() for part in line.splitlines()]
        for part in parts:
            part = re.sub(r"\s+", " ", part).strip()
            if not part or part == previous:
                continue
            cleaned.append(part)
            previous = part
    return "\n".join(cleaned).strip() + "\n"


def parse_vtt_or_srt(text: str) -> str:
    lines: list[str] = []
    skip_block = False
    raw_lines = text.splitlines()
    for index, raw_line in enumerate(raw_lines):
        line = raw_line.strip("\ufeff").strip()
        if not line:
            skip_block = False
            continue
        if line.upper().startswith(("WEBVTT", "STYLE", "REGION", "NOTE")):
            skip_block = True
            continue
        if skip_block:
            continue
        if re.fullmatch(r"\d+", line):
            continue
        if "-->" in line:
            continue
        following_lines = (item.strip() for item in raw_lines[index + 1 :])
        next_non_empty = next((item for item in following_lines if item), "")
        if re.fullmatch(r"[a-zA-Z0-9_-]+", line) and "-->" in next_non_empty:
            continue
        lines.append(line)
    return clean_lines(lines)


def parse_ass(text: str) -> str:
    format_fields: list[str] | None = None
    lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.lower().startswith("format:"):
            format_fields = [item.strip().lower() for item in line.split(":", 1)[1].split(",")]
            continue
        if not line.lower().startswith("dialogue:"):
            continue
        payload = line.split(":", 1)[1].strip()
        text_index = format_fields.index("text") if format_fields and "text" in format_fields else 9
        parts = payload.split(",", text_index)
        if len(parts) > text_index:
            lines.append(parts[text_index])
    return clean_lines(lines)


def parse_json_subtitle(text: str) -> str:
    data = json.loads(text)
    lines: list[str] = []

    if isinstance(data, dict) and isinstance(data.get("events"), list):
        for event in data["events"]:
            segs = event.get("segs") or []
            value = "".join(seg.get("utf8", "") for seg in segs).strip()
            if value:
                lines.append(value)
        return clean_lines(lines)

    if isinstance(data, dict) and isinstance(data.get("body"), list):
        for item in data["body"]:
            value = item.get("content") or item.get("text")
            if value:
                lines.append(str(value))
        return clean_lines(lines)

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key in {"content", "text", "utf8"} and isinstance(item, str):
                    lines.append(item)
                else:
                    walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(data)
    return clean_lines(lines)


def subtitle_to_text(path: Path, ext: str) -> str:
    text = path.read_text(encoding="utf-8-sig", errors="ignore")
    ext = ext.lower()
    if ext in {"vtt", "srt"}:
        return parse_vtt_or_srt(text)
    if ext in {"ass", "ssa"}:
        return parse_ass(text)
    if ext in {"json", "json3"}:
        return parse_json_subtitle(text)
    return parse_vtt_or_srt(text)
