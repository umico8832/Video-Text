#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import platform
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import yt_dlp

from download_errors import (
    browser_display_name,
    compact_error_detail,
    cookie_file_display_name,
    format_download_error,
    is_bilibili_412_error,
    is_browser_cookie_database_error,
    is_browser_cookie_dpapi_error,
)
from media_downloader import (
    BROWSER_HEADERS,
    add_yt_dlp_access_options,
    download_audio,
    download_subtitle,
    get_info,
    get_info_with_executable,
    resolve_ffmpeg_path,
    resolve_yt_dlp_path,
    should_use_yt_dlp_executable,
    subprocess_hidden_kwargs,
    venv_tool_path,
    ydl_base_opts,
)
from output_paths import OUTPUT_DIR, build_output_path, sanitize_filename
from subtitle_parser import (
    clean_lines,
    parse_ass,
    parse_json_subtitle,
    parse_vtt_or_srt,
    subtitle_to_text,
)
from subtitle_selector import (
    EN_ALIASES,
    SUBTITLE_EXT_PRIORITY,
    SUBTITLE_LANGUAGE_LABELS,
    ZH_ALIASES,
    choose_subtitle,
    lang_score,
    subtitle_language_aliases,
    subtitle_language_label,
)
from transcriber import (
    detect_device,
    ensure_local_whisper_model,
    is_gpu_runtime_error,
    transcribe_audio,
)


ROOT = Path(__file__).resolve().parent
IS_WINDOWS = platform.system() == "Windows"
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

def nvidia_library_dirs() -> list[Path]:
    candidates: list[Path] = []
    if IS_WINDOWS:
        candidates.extend((ROOT / ".venv" / "Lib" / "site-packages").glob("nvidia/*/bin"))
        candidates.extend((ROOT / ".venv" / "Lib" / "site-packages").glob("nvidia/*/lib"))
    else:
        for site_packages in (ROOT / ".venv" / "lib").glob("python*/site-packages"):
            candidates.extend(site_packages.glob("nvidia/*/lib"))
    return [path for path in candidates if path.is_dir()]


def ensure_nvidia_library_path() -> None:
    library_dirs = nvidia_library_dirs()
    if not library_dirs:
        return
    if IS_WINDOWS:
        for path in library_dirs:
            try:
                os.add_dll_directory(str(path))
            except (AttributeError, OSError):
                pass
        current = os.environ.get("PATH", "")
        existing = [item for item in current.split(os.pathsep) if item]
        missing = [str(path) for path in library_dirs if str(path) not in existing]
        if missing:
            os.environ["PATH"] = os.pathsep.join(missing + existing)
        return
    current = os.environ.get("LD_LIBRARY_PATH", "")
    existing = [item for item in current.split(":") if item]
    missing = [str(path) for path in library_dirs if str(path) not in existing]
    if not missing:
        return
    merged = missing + existing
    os.environ["LD_LIBRARY_PATH"] = ":".join(dict.fromkeys(merged))
    running_script = bool(sys.argv and sys.argv[0] not in {"-c", "-"})
    if running_script and os.environ.get("VIDEO_TEXT_EXTRACTION_REEXEC") != "1":
        os.environ["VIDEO_TEXT_EXTRACTION_REEXEC"] = "1"
        os.execv(sys.executable, [sys.executable, *sys.argv])


ensure_nvidia_library_path()

LogCallback = Any
MISSING_WHISPER_MODEL_MESSAGE = "未找到可用字幕，需要选择识别模型后再试。"


def log(message: str, callback: LogCallback | None = None) -> None:
    if callback:
        callback(message)
    else:
        print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def log_cookie_usage(
    cookies: str | None,
    cookies_from_browser: str | None = None,
    log_callback: LogCallback | None = None,
) -> None:
    if cookies_from_browser:
        browser_name = browser_display_name(cookies_from_browser)
        log(f"已启用 {browser_name} Cookies，本次请求将使用浏览器登录态。", log_callback)
    elif cookies:
        log(f"已使用 cookies.txt 文件：{cookie_file_display_name(cookies)}。", log_callback)


def extract_existing_subtitle(
    info: dict[str, Any],
    title: str,
    video_id: str,
    output_path: Path,
    log_callback: LogCallback | None = None,
    subtitle_language: str = "zh",
) -> Path | None:
    language_label = subtitle_language_label(subtitle_language)
    log(f"正在查找视频自带{language_label}...", log_callback)
    selected = choose_subtitle(info, subtitle_language)
    if not selected:
        return None

    lang, entry, source_name = selected
    ext = (entry.get("ext") or "vtt").lower()
    source_label = "人工字幕" if source_name == "subtitles" else "自动字幕"
    log(f"已找到视频自带{language_label}：{source_label} {lang} / {ext}，开始下载字幕...", log_callback)
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="subtitle-", dir=str(output_path.parent)) as temp_dir:
            raw_path = Path(temp_dir) / f"{title}.{video_id}.{lang}.{ext}"
            download_subtitle(entry, raw_path)
            output_path.write_text(subtitle_to_text(raw_path, ext), encoding="utf-8")
    except Exception as exc:
        raise RuntimeError(f"保存失败：无法下载或写入字幕文本，请检查输出目录权限。\n详情：{exc}") from exc
    log(f"字幕文本已保存到：{output_path}", log_callback)
    return output_path


def transcribe_missing_subtitle(
    url: str,
    model: str | None,
    device: str,
    compute_type: str,
    cookies: str | None,
    output_path: Path,
    ffmpeg_path: str | None = None,
    yt_dlp_path: str | None = None,
    log_callback: LogCallback | None = None,
    cookies_from_browser: str | None = None,
    model_display_name: str | None = None,
    model_is_local: bool | None = None,
    model_download_name: str | None = None,
    model_download_dir: str | Path | None = None,
    whisper_language: str = "zh",
) -> Path:
    language_label = subtitle_language_label(whisper_language)
    log(f"未找到可用{language_label}，开始下载音频并准备语音识别...", log_callback)
    model_name = (model or "").strip()
    if not model_name:
        raise RuntimeError(MISSING_WHISPER_MODEL_MESSAGE)

    if model_display_name is None:
        model_display_name = model_download_name or model_name
    local_model_name = ensure_local_whisper_model(
        model_name,
        log_callback=log_callback,
        download_model_name=model_download_name,
        download_dir=model_download_dir,
    )
    if local_model_name != model_name:
        model_name = local_model_name
        model_is_local = True

    with tempfile.TemporaryDirectory(prefix="video-text-", dir=str(ROOT)) as temp_dir:
        workdir = Path(temp_dir)
        try:
            audio_path = download_audio(
                url,
                workdir,
                cookies,
                ffmpeg_path=ffmpeg_path,
                yt_dlp_path=yt_dlp_path,
                log_callback=log_callback,
                cookies_from_browser=cookies_from_browser,
            )
        except Exception as exc:
            raise RuntimeError(
                format_download_error(
                    url,
                    exc,
                    "下载失败：无法下载音频。请检查网络、链接或 Cookies 设置。",
                    cookies_from_browser,
                )
            ) from exc
        log("音频下载完成，开始语音识别...", log_callback)
        text = transcribe_audio(
            audio_path,
            model_name,
            device,
            compute_type,
            log_callback=log_callback,
            model_display_name=model_display_name,
            model_is_local=model_is_local,
            language=whisper_language,
        )
        try:
            output_path.write_text(text, encoding="utf-8")
        except Exception as exc:
            raise RuntimeError(f"保存失败：无法写入输出目录，请检查目录权限。\n详情：{exc}") from exc
        log(f"字幕文本已保存到：{output_path}", log_callback)
        return output_path


def extract(
    url: str,
    model: str | None,
    device: str,
    compute_type: str,
    cookies: str | None,
    ffmpeg_path: str | None = None,
    yt_dlp_path: str | None = None,
    log_callback: LogCallback | None = None,
    cookies_from_browser: str | None = None,
    output_dir: str | Path | None = None,
    model_display_name: str | None = None,
    model_is_local: bool | None = None,
    model_download_name: str | None = None,
    model_download_dir: str | Path | None = None,
    subtitle_language: str = "zh",
) -> Path:
    OUTPUT_DIR.mkdir(exist_ok=True)

    log("正在获取视频信息...", log_callback)
    try:
        info = get_info(
            url,
            cookies,
            ffmpeg_path=ffmpeg_path,
            yt_dlp_path=yt_dlp_path,
            cookies_from_browser=cookies_from_browser,
        )
    except Exception as exc:
        raise RuntimeError(
            format_download_error(
                url,
                exc,
                "下载失败：无法获取视频信息。请检查链接是否有效，或稍后重试。",
                cookies_from_browser,
            )
        ) from exc
    log_cookie_usage(cookies, cookies_from_browser, log_callback)
    title, video_id, output_path = build_output_path(info, output_dir)

    subtitle_output = extract_existing_subtitle(
        info,
        title,
        video_id,
        output_path,
        log_callback,
        subtitle_language=subtitle_language,
    )
    if subtitle_output is not None:
        return subtitle_output

    return transcribe_missing_subtitle(
        url,
        model,
        device,
        compute_type,
        cookies,
        output_path,
        ffmpeg_path=ffmpeg_path,
        yt_dlp_path=yt_dlp_path,
        log_callback=log_callback,
        cookies_from_browser=cookies_from_browser,
        model_display_name=model_display_name,
        model_is_local=model_is_local,
        model_download_name=model_download_name,
        model_download_dir=model_download_dir,
        whisper_language=subtitle_language,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="从 B 站 / YouTube 视频提取字幕纯文本")
    parser.add_argument("url", nargs="?", help="视频链接；不传则进入交互输入")
    parser.add_argument("--model", default="large-v3", help="Whisper 模型，默认 large-v3")
    parser.add_argument("--device", default="auto", choices=["auto", "cuda", "cpu"], help="推理设备")
    parser.add_argument("--compute-type", default="auto", help="例如 int8_float16、float16、int8")
    parser.add_argument("--cookies", help="cookies.txt 路径；B 站字幕或会员视频可能需要")
    parser.add_argument("--ffmpeg", help="ffmpeg 可执行文件路径")
    parser.add_argument("--yt-dlp", help="yt-dlp 可执行文件路径")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    url = args.url or input("请输入 B 站或 YouTube 视频链接：").strip()
    if not url:
        print("没有输入链接。")
        return 1

    try:
        from model_config import is_english_only_model

        subtitle_language = "en" if is_english_only_model(args.model) else "zh"
        result = extract(
            url=url,
            model=args.model,
            device=args.device,
            compute_type=args.compute_type,
            cookies=args.cookies,
            ffmpeg_path=args.ffmpeg,
            yt_dlp_path=args.yt_dlp,
            subtitle_language=subtitle_language,
        )
    except KeyboardInterrupt:
        print("\n已取消。")
        return 130
    except Exception as exc:
        print(f"\n失败：{exc}", file=sys.stderr)
        print("提示：B 站部分字幕/高清资源需要登录 cookies，可用 --cookies cookies.txt。", file=sys.stderr)
        return 1

    print(f"\n完成：{result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
