from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import ctranslate2

from subtitle_parser import clean_lines


LogCallback = Any


def log(message: str, callback: LogCallback | None = None) -> None:
    if callback:
        callback(message)
    else:
        print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def is_gpu_runtime_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(
        marker in message
        for marker in (
            "libcu",
            "cublas",
            "cudnn",
            "cuda",
            ".dll",
            "cannot be loaded",
            "not found",
        )
    )


def detect_device() -> str:
    try:
        compute_types = ctranslate2.get_supported_compute_types("cuda")
        if compute_types:
            return "cuda"
    except Exception:
        pass
    return "cpu"


def transcribe_audio(
    audio_path: Path,
    model_name: str,
    device: str,
    compute_type: str,
    log_callback: LogCallback | None = None,
    model_display_name: str | None = None,
    model_is_local: bool | None = None,
    language: str = "zh",
) -> str:
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError(f"模型加载失败：Whisper 依赖缺失，请先安装 faster-whisper。\n详情：{exc}") from exc

    if device == "auto":
        device = detect_device()
    if compute_type == "auto":
        compute_type = "int8_float16" if device == "cuda" else "int8"

    display_name = (model_display_name or model_name).strip()
    if model_is_local is None:
        model_is_local = Path(model_name).is_dir()
    if model_is_local:
        log(f"正在加载本地 Whisper 模型：{display_name} / {device} / {compute_type}", log_callback)
    else:
        log(f"开始下载 Whisper 模型：{display_name} / {device} / {compute_type}", log_callback)
    try:
        model = WhisperModel(model_name, device=device, compute_type=compute_type)
    except Exception as exc:
        if device != "cpu" and is_gpu_runtime_error(exc):
            log(f"模型加载失败：GPU 模式不可用，已切换为 CPU int8。\n详情：{exc}", log_callback)
            device = "cpu"
            compute_type = "int8"
            model = WhisperModel(model_name, device="cpu", compute_type="int8")
        else:
            raise

    log("正在识别音频内容...", log_callback)
    try:
        segments, info = model.transcribe(
            str(audio_path),
            language=language,
            vad_filter=True,
            beam_size=5,
        )
    except Exception as exc:
        if device != "cpu" and is_gpu_runtime_error(exc):
            log(f"识别失败：GPU 运行库不可用，已切换为 CPU int8 后重试。\n详情：{exc}", log_callback)
            model = WhisperModel(model_name, device="cpu", compute_type="int8")
            segments, info = model.transcribe(
                str(audio_path),
                language=language,
                vad_filter=True,
                beam_size=5,
            )
        else:
            raise
    duration = getattr(info, "duration", None) or 0
    lines: list[str] = []
    last_reported = -1
    for segment in segments:
        if segment.text.strip():
            lines.append(segment.text.strip())
        if duration:
            current = int((segment.end / duration) * 100)
            if current >= last_reported + 10:
                last_reported = current
                log(f"识别进度约 {min(current, 100)}%", log_callback)
    return clean_lines(lines)


def ensure_local_whisper_model(
    model_name: str,
    log_callback: LogCallback | None = None,
    download_model_name: str | None = None,
    download_dir: str | Path | None = None,
) -> str:
    try:
        from model_config import get_official_model_dir, is_preset_model, is_valid_model_dir
    except ImportError:
        return model_name

    model_value = model_name.strip()
    target_dir = Path(download_dir) if download_dir else None
    source_model = (download_model_name or "").strip()
    if not source_model and is_preset_model(model_value):
        source_model = model_value
        target_dir = get_official_model_dir(model_value)
    if not source_model or target_dir is None:
        return model_name

    if is_valid_model_dir(target_dir):
        log(f"已检测到本地模型：{source_model}", log_callback)
        return str(target_dir)

    try:
        from faster_whisper.utils import download_model
    except ImportError as exc:
        raise RuntimeError(f"模型下载失败：Whisper 依赖缺失，请先安装 faster-whisper。\n详情：{exc}") from exc

    target_dir.mkdir(parents=True, exist_ok=True)
    log(f"开始下载 Whisper 模型：{source_model}", log_callback)
    log(f"Whisper 模型将保存到：{target_dir}", log_callback)
    download_model(source_model, output_dir=str(target_dir))
    if not is_valid_model_dir(target_dir):
        raise RuntimeError("下载完成，但模型目录缺少基本模型文件")
    log(f"Whisper 模型已下载完成：{source_model}", log_callback)
    log(f"Whisper 模型已下载到本地目录：{target_dir}", log_callback)
    return str(target_dir)
