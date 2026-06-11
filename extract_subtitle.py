#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
from html import unescape
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "outputs"
IS_WINDOWS = platform.system() == "Windows"
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

BROWSER_HEADERS = {
    "Referer": "https://www.bilibili.com",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0 Safari/537.36"
    ),
}

ZH_ALIASES = (
    "zh",
    "zh-cn",
    "zh-hans",
    "zh-sg",
    "zh-hant",
    "zh-tw",
    "cmn",
    "zho",
    "chi",
    "chinese",
    "中文",
    "简体",
    "繁体",
)

EN_ALIASES = (
    "en",
    "en-us",
    "en-gb",
    "en-au",
    "en-ca",
    "eng",
    "english",
)

SUBTITLE_LANGUAGE_LABELS = {
    "zh": "中文字幕",
    "en": "英文字幕",
}

SUBTITLE_EXT_PRIORITY = {
    "srt": 0,
    "vtt": 1,
    "json3": 2,
    "json": 3,
    "ass": 4,
    "ssa": 5,
}


def venv_tool_path(name: str) -> Path:
    scripts_dir = ROOT / ".venv" / ("Scripts" if IS_WINDOWS else "bin")
    executable = f"{name}.exe" if IS_WINDOWS and not name.endswith(".exe") else name
    return scripts_dir / executable


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

import ctranslate2
import imageio_ffmpeg
import yt_dlp

LogCallback = Any
MISSING_WHISPER_MODEL_MESSAGE = "未找到可用字幕，需要选择识别模型后再试。"


def log(message: str, callback: LogCallback | None = None) -> None:
    if callback:
        callback(message)
    else:
        print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def is_bilibili_412_error(url: str, error: str) -> bool:
    text = f"{url}\n{error}".lower()
    return (
        "bilibili" in text
        and ("http error 412" in text or "precondition failed" in text)
    )


def is_browser_cookie_database_error(error: str) -> bool:
    text = error.lower()
    return (
        "could not copy chrome cookie database" in text
        or ("could not copy" in text and "cookie database" in text)
    )


def is_browser_cookie_dpapi_error(error: str) -> bool:
    return "failed to decrypt with dpapi" in error.lower()


def compact_error_detail(error: str) -> str:
    lines = [line.strip() for line in str(error).splitlines() if line.strip()]
    return "\n".join(lines[-6:])


def browser_display_name(browser: str | None) -> str:
    if not browser:
        return "浏览器"
    normalized = str(browser).strip().lower()
    names = {
        "chrome": "Chrome",
        "edge": "Edge",
        "firefox": "Firefox",
    }
    return names.get(normalized, normalized.title())


def cookie_file_display_name(cookies: str | None) -> str:
    if not cookies:
        return "cookies.txt"
    name = Path(cookies).name
    return name or "cookies.txt"


def format_download_error(url: str, exc: Exception, fallback: str, cookies_from_browser: str | None = None) -> str:
    detail = compact_error_detail(str(exc))
    if is_browser_cookie_database_error(detail):
        browser_name = browser_display_name(cookies_from_browser)
        return (
            f"读取 {browser_name} Cookie 失败，Cookie 未被使用。\n"
            f"原因可能是 {browser_name} 仍在后台运行，或 Cookie 数据库被占用。\n\n"
            "建议：\n"
            f"1. 完全关闭 {browser_name}；\n"
            "2. 改用 cookies.txt 文件方式。\n\n"
            f"详情：{detail}"
        )
    if is_browser_cookie_dpapi_error(detail):
        browser_name = browser_display_name(cookies_from_browser)
        return (
            f"读取 {browser_name} Cookie 失败，Cookie 未被使用。\n"
            "原因是浏览器 Cookie 解密失败。\n\n"
            "建议：\n"
            "1. 改用 cookies.txt 文件方式；\n"
            "2. 或尝试 Firefox Cookie。\n\n"
            f"详情：{detail}"
        )
    if is_bilibili_412_error(url, detail):
        return (
            "Bilibili 获取失败：B 站可能拦截了未登录或异常网络请求。\n\n"
            "建议：\n"
            "1. 优先使用 cookies.txt 文件方式；\n"
            "2. 或尝试可用的浏览器 Cookie。\n\n"
            f"详情：{detail}"
        )
    return f"{fallback}\n详情：{detail}"


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


def sanitize_filename(value: str, max_len: int = 120) -> str:
    value = re.sub(r"[\\/:*?\"<>|]+", "_", value).strip()
    value = re.sub(r"\s+", " ", value)
    return value[:max_len].strip(" .") or "video"


def resolve_ffmpeg_path(ffmpeg_path: str | None = None) -> str:
    if ffmpeg_path and Path(ffmpeg_path).exists():
        return ffmpeg_path
    local = venv_tool_path("ffmpeg")
    if local.exists():
        return str(local)
    found = shutil.which("ffmpeg")
    if found:
        return found
    return imageio_ffmpeg.get_ffmpeg_exe()


def resolve_yt_dlp_path(yt_dlp_path: str | None = None) -> str | None:
    if yt_dlp_path and Path(yt_dlp_path).exists():
        return yt_dlp_path
    local = venv_tool_path("yt-dlp")
    if local.exists():
        return str(local)
    return shutil.which("yt-dlp")


def subprocess_hidden_kwargs() -> dict:
    if not IS_WINDOWS:
        return {}
    if hasattr(subprocess, "CREATE_NO_WINDOW"):
        return {"creationflags": subprocess.CREATE_NO_WINDOW}
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    return {"startupinfo": startupinfo}


def should_use_yt_dlp_executable(yt_dlp_path: str | None = None) -> bool:
    return bool(yt_dlp_path and Path(yt_dlp_path).exists())


def add_yt_dlp_access_options(
    cmd: list[str],
    cookies: str | None = None,
    ffmpeg_path: str | None = None,
    cookies_from_browser: str | None = None,
) -> None:
    cmd.extend(["--add-header", f"Referer:{BROWSER_HEADERS['Referer']}"])
    cmd.extend(["--add-header", f"User-Agent:{BROWSER_HEADERS['User-Agent']}"])
    resolved_ffmpeg = resolve_ffmpeg_path(ffmpeg_path)
    if resolved_ffmpeg:
        cmd.extend(["--ffmpeg-location", resolved_ffmpeg])
    if cookies_from_browser:
        cmd.extend(["--cookies-from-browser", cookies_from_browser])
    elif cookies:
        cmd.extend(["--cookies", cookies])


def ydl_base_opts(
    cookies: str | None = None,
    quiet: bool = True,
    ffmpeg_path: str | None = None,
    cookies_from_browser: str | None = None,
) -> dict[str, Any]:
    opts: dict[str, Any] = {
        "http_headers": BROWSER_HEADERS,
        "quiet": quiet,
        "no_warnings": quiet,
        "noplaylist": True,
        "ffmpeg_location": resolve_ffmpeg_path(ffmpeg_path),
    }
    if cookies_from_browser:
        opts["cookiesfrombrowser"] = (cookies_from_browser,)
    elif cookies:
        opts["cookiefile"] = cookies
    return opts


def get_info_with_executable(
    url: str,
    yt_dlp_path: str,
    cookies: str | None,
    ffmpeg_path: str | None = None,
    cookies_from_browser: str | None = None,
) -> dict[str, Any]:
    cmd = [
        yt_dlp_path,
        "--dump-single-json",
        "--skip-download",
        "--no-playlist",
        "--quiet",
        "--no-warnings",
    ]
    add_yt_dlp_access_options(cmd, cookies, ffmpeg_path, cookies_from_browser)
    cmd.append(url)
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        check=False,
        **subprocess_hidden_kwargs(),
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(detail or f"yt-dlp 执行失败，退出码：{result.returncode}")
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"yt-dlp 返回的视频信息不是有效 JSON。\n详情：{exc}") from exc
    if not isinstance(data, dict):
        raise RuntimeError("yt-dlp 返回的视频信息格式不可用。")
    return data


def get_info(
    url: str,
    cookies: str | None,
    ffmpeg_path: str | None = None,
    yt_dlp_path: str | None = None,
    cookies_from_browser: str | None = None,
) -> dict[str, Any]:
    if should_use_yt_dlp_executable(yt_dlp_path):
        return get_info_with_executable(
            url,
            str(yt_dlp_path),
            cookies,
            ffmpeg_path=ffmpeg_path,
            cookies_from_browser=cookies_from_browser,
        )
    opts = ydl_base_opts(
        cookies=cookies,
        ffmpeg_path=ffmpeg_path,
        cookies_from_browser=cookies_from_browser,
    )
    opts["skip_download"] = True
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=False)


def subtitle_language_aliases(language: str | None) -> tuple[str, ...]:
    return EN_ALIASES if language == "en" else ZH_ALIASES


def subtitle_language_label(language: str | None) -> str:
    return SUBTITLE_LANGUAGE_LABELS.get(language or "zh", "目标语言字幕")


def lang_score(lang: str, language: str | None = "zh") -> int | None:
    normalized = lang.lower()
    if normalized == "danmaku":
        return None
    for idx, alias in enumerate(subtitle_language_aliases(language)):
        if alias in normalized:
            return idx
    return None


def choose_subtitle(
    info: dict[str, Any],
    language: str | None = "zh",
) -> tuple[str, dict[str, Any], str] | None:
    candidates: list[tuple[int, int, int, str, dict[str, Any], str]] = []

    for source_name, source_priority in (("subtitles", 0), ("automatic_captions", 1)):
        subtitles = info.get(source_name) or {}
        for lang, entries in subtitles.items():
            score = lang_score(lang, language)
            if score is None:
                continue
            for entry in entries or []:
                ext = (entry.get("ext") or "").lower()
                if not entry.get("url"):
                    continue
                ext_priority = SUBTITLE_EXT_PRIORITY.get(ext, 99)
                candidates.append(
                    (source_priority, score, ext_priority, lang, entry, source_name)
                )

    if not candidates:
        return None

    candidates.sort(key=lambda item: item[:3])
    _, _, _, lang, entry, source_name = candidates[0]
    return lang, entry, source_name


def download_subtitle(entry: dict[str, Any], target: Path) -> None:
    req = Request(entry["url"], headers=BROWSER_HEADERS)
    with urlopen(req, timeout=60) as response:
        target.write_bytes(response.read())


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


def download_audio(
    url: str,
    workdir: Path,
    cookies: str | None,
    ffmpeg_path: str | None = None,
    yt_dlp_path: str | None = None,
    log_callback: LogCallback | None = None,
    cookies_from_browser: str | None = None,
) -> Path:
    audio_template = str(workdir / "audio.%(ext)s")

    if should_use_yt_dlp_executable(yt_dlp_path):
        cmd = [
            str(yt_dlp_path),
            "--newline",
            "-f",
            "bestaudio/best",
            "-o",
            audio_template,
            "--extract-audio",
            "--audio-format",
            "mp3",
            "--audio-quality",
            "192K",
            "--no-playlist",
        ]
        add_yt_dlp_access_options(cmd, cookies, ffmpeg_path, cookies_from_browser)
        cmd.append(url)
        process = subprocess.Popen(
            cmd,
            cwd=str(workdir),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            **subprocess_hidden_kwargs(),
        )
        assert process.stdout is not None
        for line in process.stdout:
            line = line.strip()
            if line and log_callback:
                log_callback(line)
        exit_code = process.wait()
        if exit_code != 0:
            raise RuntimeError(f"yt-dlp 音频下载失败，退出码：{exit_code}")

        candidates = sorted(workdir.glob("audio.*"))
        if not candidates:
            raise RuntimeError("音频下载后没有找到输出文件")
        preferred = [item for item in candidates if item.suffix.lower() == ".mp3"]
        return preferred[0] if preferred else candidates[0]

    def hook(status: dict[str, Any]) -> None:
        if status.get("status") == "downloading":
            percent = status.get("_percent_str", "").strip()
            speed = status.get("_speed_str", "").strip()
            eta = status.get("_eta_str", "").strip()
            if percent:
                message = f"正在下载音频：{percent} {speed} ETA {eta}"
                if log_callback:
                    log_callback(message)
                else:
                    print(f"\r    {message}", end="", flush=True)
        elif status.get("status") == "finished":
            if log_callback:
                log_callback("音频下载完成，正在转码为 MP3")
            else:
                print("\r    音频下载完成，正在转码...".ljust(60), flush=True)

    opts = ydl_base_opts(cookies=cookies, quiet=True, ffmpeg_path=ffmpeg_path, cookies_from_browser=cookies_from_browser)
    opts.update(
        {
            "format": "bestaudio/best",
            "outtmpl": audio_template,
            "progress_hooks": [hook],
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ],
        }
    )
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])

    candidates = sorted(workdir.glob("audio.*"))
    if not candidates:
        raise RuntimeError("音频下载后没有找到输出文件")
    preferred = [item for item in candidates if item.suffix.lower() == ".mp3"]
    return preferred[0] if preferred else candidates[0]


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
            device = "cpu"
            compute_type = "int8"
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


def build_output_path(info: dict[str, Any], output_dir: str | Path | None = None) -> tuple[str, str, Path]:
    title = sanitize_filename(info.get("title") or info.get("id") or "video")
    video_id = sanitize_filename(str(info.get("id") or "video"))
    if output_dir is None:
        text_output_dir = OUTPUT_DIR
    else:
        text_output_dir = Path(output_dir)
        text_output_dir.mkdir(parents=True, exist_ok=True)
    return title, video_id, text_output_dir / f"{title}.{video_id}.txt"


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
    raw_path = OUTPUT_DIR / f"{title}.{video_id}.{lang}.{ext}"
    try:
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
