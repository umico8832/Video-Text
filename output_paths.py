from __future__ import annotations

import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "outputs"


def sanitize_filename(value: str, max_len: int = 120) -> str:
    value = re.sub(r"[\\/:*?\"<>|]+", "_", value).strip()
    value = re.sub(r"\s+", " ", value)
    return value[:max_len].strip(" .") or "video"


def build_output_path(info: dict[str, Any], output_dir: str | Path | None = None) -> tuple[str, str, Path]:
    title = sanitize_filename(info.get("title") or info.get("id") or "video")
    video_id = sanitize_filename(str(info.get("id") or "video"))
    if output_dir is None:
        text_output_dir = OUTPUT_DIR
    else:
        text_output_dir = Path(output_dir)
        text_output_dir.mkdir(parents=True, exist_ok=True)
    return title, video_id, text_output_dir / f"{title}.{video_id}.txt"
