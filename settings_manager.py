from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from model_config import MODELS_DIR, get_model_settings_fields


ROOT = Path(__file__).resolve().parent
SETTINGS_FILE = ROOT / "settings.json"
DEFAULT_OUTPUT_DIR = ROOT / "outputs"
DEFAULT_MODEL_DIR = MODELS_DIR


def default_settings() -> dict:
    return {
        "url": "",
        "ffmpeg": "",
        "yt_dlp": "",
        "cookies": "",
        "output_dir": DEFAULT_OUTPUT_DIR.name,
        "model_dir": DEFAULT_MODEL_DIR.name,
        "device": "auto",
        "cookie_mode": "none",
        "cookies_browser": "chrome",
    }


def load_settings() -> dict:
    if not SETTINGS_FILE.exists():
        return default_settings()
    try:
        loaded = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return default_settings()
    if not isinstance(loaded, dict):
        return default_settings()

    settings = default_settings()
    settings.update(loaded)
    return settings


def save_settings(settings: dict) -> None:
    payload = json.dumps(settings, ensure_ascii=False, indent=2)
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp_name = ""
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=SETTINGS_FILE.parent,
            delete=False,
        ) as temp_file:
            temp_file.write(payload)
            temp_file.write("\n")
            temp_name = temp_file.name
        os.replace(temp_name, SETTINGS_FILE)
    finally:
        if temp_name and Path(temp_name).exists():
            Path(temp_name).unlink()


def normalize_output_dir(value: str | None) -> str:
    text = str(value or "").strip()
    return text or DEFAULT_OUTPUT_DIR.name


def is_default_output_dir(value: str | None) -> bool:
    value = str(value or "").strip()
    if not value:
        return True
    path = Path(value)
    if path.name != DEFAULT_OUTPUT_DIR.name:
        return False
    candidate = path if path.is_absolute() else ROOT / path
    return candidate.resolve() == DEFAULT_OUTPUT_DIR.resolve()


def selected_output_dir(value: str | None) -> str:
    value = str(value or "").strip()
    if is_default_output_dir(value):
        return ""
    return value


def normalize_model_dir(value: str | None) -> str:
    text = str(value or "").strip()
    return text or DEFAULT_MODEL_DIR.name


def build_settings_payload(values: dict) -> dict:
    settings = {
        "url": str(values.get("url", "")).strip(),
        "ffmpeg": str(values.get("ffmpeg", "")).strip(),
        "yt_dlp": str(values.get("yt_dlp", "")).strip(),
        "cookies": str(values.get("cookies", "")).strip(),
        "output_dir": str(values.get("output_dir", "")).strip(),
        "model_dir": normalize_model_dir(values.get("model_dir")),
        "device": values.get("device", "auto"),
        "cookie_mode": values.get("cookie_mode", "none"),
        "cookies_browser": values.get("cookies_browser", "chrome"),
    }
    settings.update(
        get_model_settings_fields(
            values.get("selected_model"),
            values.get("local_model"),
        )
    )
    return settings
