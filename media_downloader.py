from __future__ import annotations

import json
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

import imageio_ffmpeg
import yt_dlp


ROOT = Path(__file__).resolve().parent
IS_WINDOWS = platform.system() == "Windows"

BROWSER_HEADERS = {
    "Referer": "https://www.bilibili.com",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0 Safari/537.36"
    ),
}


def venv_tool_path(name: str) -> Path:
    scripts_dir = ROOT / ".venv" / ("Scripts" if IS_WINDOWS else "bin")
    executable = f"{name}.exe" if IS_WINDOWS and not name.endswith(".exe") else name
    return scripts_dir / executable


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


def download_subtitle(entry: dict[str, Any], target: Path) -> None:
    req = Request(entry["url"], headers=BROWSER_HEADERS)
    with urlopen(req, timeout=60) as response:
        target.write_bytes(response.read())


def download_audio(
    url: str,
    workdir: Path,
    cookies: str | None,
    ffmpeg_path: str | None = None,
    yt_dlp_path: str | None = None,
    log_callback: Any | None = None,
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

    opts = ydl_base_opts(
        cookies=cookies,
        quiet=True,
        ffmpeg_path=ffmpeg_path,
        cookies_from_browser=cookies_from_browser,
    )
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
