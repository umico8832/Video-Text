#!/usr/bin/env python3
from __future__ import annotations

import importlib.metadata
import platform
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable


ROOT = Path(__file__).resolve().parent
REQUIRED_ENV_KEYS = ("ffmpeg", "yt-dlp", "whisper")
GPU_PACKAGES = ["nvidia-cublas-cu12", "nvidia-cudnn-cu12"]
IS_WINDOWS = platform.system() == "Windows"

LogCallback = Callable[[str], None]
SENSITIVE_COMMAND_MARKERS = ("token", "password", "passwd", "secret", "cookie")


def subprocess_hidden_kwargs() -> dict:
    if not IS_WINDOWS:
        return {}
    if hasattr(subprocess, "CREATE_NO_WINDOW"):
        return {"creationflags": subprocess.CREATE_NO_WINDOW}
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    return {"startupinfo": startupinfo}


def path_exists(value: str | None) -> bool:
    return bool(value and value.strip()) and Path(value.strip()).exists()


def local_bin(name: str) -> Path:
    scripts_dir = ROOT / ".venv" / ("Scripts" if IS_WINDOWS else "bin")
    executable = f"{name}.exe" if IS_WINDOWS and not name.endswith(".exe") else name
    return scripts_dir / executable


def same_file(path_a: str | Path | None, path_b: str | Path | None) -> bool:
    if not path_a or not path_b:
        return False
    try:
        return Path(path_a).resolve() == Path(path_b).resolve()
    except Exception:
        return str(path_a) == str(path_b)


def install_command(*packages: str, upgrade: bool = False) -> list[str]:
    uv = shutil.which("uv") or str(Path.home() / ".local" / "bin" / "uv")
    if Path(uv).exists() or shutil.which("uv"):
        cmd = [uv, "pip", "install"]
    else:
        cmd = [sys.executable, "-m", "pip", "install"]
    if upgrade:
        cmd.append("--upgrade")
    cmd.extend(packages)
    return cmd


def package_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return ""


def check_python_package(module_name: str) -> dict:
    version = package_version(module_name)
    return {
        "ok": bool(version),
        "path": module_name,
        "version": version,
    }


def check_command_available(path_or_command: str) -> dict:
    found = path_or_command if path_exists(path_or_command) else shutil.which(path_or_command)
    return {
        "ok": bool(found),
        "path": found or "",
        "source": "用户指定" if path_exists(path_or_command) else "系统 PATH" if found else "缺失",
    }


def command_version(path_or_command: str, timeout: int = 5) -> str:
    if not path_or_command:
        return ""
    try:
        result = subprocess.run(
            [path_or_command, "-version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
            check=False,
            **subprocess_hidden_kwargs(),
        )
    except Exception:
        return ""
    first_line = (result.stdout or "").splitlines()[0].strip() if result.stdout else ""
    return first_line


def ytdlp_version(path_or_command: str, timeout: int = 5) -> str:
    if not path_or_command:
        return ""
    try:
        result = subprocess.run(
            [path_or_command, "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
            check=False,
            **subprocess_hidden_kwargs(),
        )
    except Exception:
        return ""
    first_line = (result.stdout or "").splitlines()[0].strip() if result.stdout else ""
    return first_line


def check_ffmpeg(ffmpeg_path: str | None = None) -> dict:
    configured_ffmpeg = str(ffmpeg_path or "").strip()
    bundled_ffmpeg_path = local_bin("ffmpeg")
    if configured_ffmpeg:
        ok = path_exists(configured_ffmpeg)
        source = "内置工具" if ok and same_file(configured_ffmpeg, bundled_ffmpeg_path) else "手动指定"
        return {
            "ok": ok,
            "path": configured_ffmpeg,
            "source": source,
            "version": command_version(configured_ffmpeg) if ok else "",
            "error": "" if ok else "指定路径不存在",
        }
    bundled_ffmpeg = str(bundled_ffmpeg_path) if bundled_ffmpeg_path.exists() else None
    system_ffmpeg = shutil.which("ffmpeg")
    ffmpeg = bundled_ffmpeg or system_ffmpeg
    ffmpeg_source = "内置工具" if bundled_ffmpeg else "系统 PATH" if system_ffmpeg else "缺失"
    return {
        "ok": bool(ffmpeg),
        "path": ffmpeg or "",
        "source": ffmpeg_source,
        "version": command_version(ffmpeg) if ffmpeg else "",
    }


def check_ytdlp(yt_dlp_path: str | None = None) -> dict:
    configured_ytdlp = str(yt_dlp_path or "").strip()
    bundled_ytdlp_path = local_bin("yt-dlp")
    if configured_ytdlp:
        ok = path_exists(configured_ytdlp)
        source = "内置工具" if ok and same_file(configured_ytdlp, bundled_ytdlp_path) else "手动指定"
        return {
            "ok": ok,
            "path": configured_ytdlp,
            "source": source,
            "version": ytdlp_version(configured_ytdlp) if ok else "",
            "error": "" if ok else "指定路径不存在",
        }
    bundled_ytdlp = str(bundled_ytdlp_path) if bundled_ytdlp_path.exists() else None
    system_ytdlp = shutil.which("yt-dlp")
    ytdlp = bundled_ytdlp or system_ytdlp
    ytdlp_source = "内置工具" if bundled_ytdlp else "系统 PATH" if system_ytdlp else "缺失"
    return {
        "ok": bool(ytdlp),
        "path": ytdlp or "",
        "source": ytdlp_source,
        "version": ytdlp_version(ytdlp) if ytdlp else package_version("yt-dlp"),
    }


def check_faster_whisper() -> dict:
    whisper_version = package_version("faster-whisper")
    whisper_ok = bool(whisper_version)
    whisper_error = ""
    try:
        from faster_whisper import WhisperModel  # noqa: F401
    except Exception as exc:
        whisper_ok = False
        whisper_error = str(exc)
    return {
        "ok": whisper_ok,
        "path": "faster-whisper",
        "version": whisper_version,
        "error": whisper_error,
    }


def check_imageio_ffmpeg() -> dict:
    try:
        import imageio_ffmpeg

        path = imageio_ffmpeg.get_ffmpeg_exe()
        return {
            "ok": bool(path and Path(path).exists()),
            "path": path or "",
            "source": "imageio-ffmpeg",
            "version": package_version("imageio-ffmpeg"),
        }
    except Exception as exc:
        return {
            "ok": False,
            "path": "",
            "source": "imageio-ffmpeg",
            "version": package_version("imageio-ffmpeg"),
            "error": str(exc),
        }


def check_cuda_support() -> dict:
    cuda_ok = False
    compute_types: list[str] = []
    cuda_detail = "未检测到可用 CUDA，将使用 CPU 或按需安装 GPU 加速组件"
    try:
        import ctranslate2

        compute_types = sorted(ctranslate2.get_supported_compute_types("cuda"))
        cuda_ok = bool(compute_types)
        if cuda_ok:
            cuda_detail = "支持精度：" + ", ".join(compute_types)
    except Exception as exc:
        cuda_detail = f"不可用：{exc}"

    gpu_packages_ok = all(package_version(name) for name in GPU_PACKAGES)
    if cuda_ok and not gpu_packages_ok:
        cuda_detail = f"{cuda_detail}；尚未安装 Python CUDA 用户态库，任务中会在失败时回退 CPU"
    return {
        "ok": cuda_ok,
        "path": "可选 GPU 加速",
        "source": "已安装 GPU 组件" if gpu_packages_ok else "未安装 GPU 组件",
        "detail": cuda_detail,
        "compute_types": compute_types,
        "gpu_packages_ok": gpu_packages_ok,
        "optional": True,
    }


def check_environment(ffmpeg_path: str | None = None, yt_dlp_path: str | None = None, log: LogCallback | None = None) -> dict:
    emit = log or (lambda _message: None)

    emit("检查 FFmpeg")
    ffmpeg = check_ffmpeg(ffmpeg_path)
    if ffmpeg["ok"]:
        emit(f"FFmpeg 已找到：{ffmpeg['source']} / {ffmpeg['path']}")
    else:
        emit("FFmpeg 缺失：未在用户指定路径、软件目录或系统 PATH 中找到")

    emit("检查 yt-dlp")
    ytdlp = check_ytdlp(yt_dlp_path)
    if ytdlp["ok"]:
        version_detail = f" / 版本 {ytdlp['version']}" if ytdlp.get("version") else ""
        emit(f"yt-dlp 已找到：{ytdlp['source']} / {ytdlp['path']}{version_detail}")
    else:
        emit("yt-dlp 缺失：未在用户指定路径、软件环境或系统 PATH 中找到")

    emit("检查 Whisper 依赖")
    whisper = check_faster_whisper()
    if whisper["ok"]:
        version_detail = f" 版本 {whisper['version']}" if whisper.get("version") else ""
        emit(f"Whisper 依赖已就绪：faster-whisper{version_detail}")
    else:
        detail = f"；原因：{whisper['error']}" if whisper.get("error") else ""
        emit(f"Whisper 依赖缺失：无法导入 faster-whisper{detail}")

    emit("检查 CUDA/GPU 加速状态")
    cuda = check_cuda_support()
    if cuda["ok"]:
        emit(f"CUDA 可用：{cuda['detail']}")
    else:
        emit(f"CUDA 不可用：将使用 CPU；原因：{cuda['detail']}")

    return {
        "ffmpeg": ffmpeg,
        "yt-dlp": ytdlp,
        "whisper": {
            "ok": whisper["ok"],
            "path": whisper["path"],
            "version": whisper["version"],
        },
        "cuda": cuda,
    }


def missing_required_env(report: dict) -> list[str]:
    return [
        name for name in REQUIRED_ENV_KEYS
        if not report.get(name, {}).get("ok")
    ]


def packages_for_missing(missing: list[str]) -> list[str]:
    packages: list[str] = []
    if "yt-dlp" in missing:
        packages.append("yt-dlp")
    if "ffmpeg" in missing:
        packages.append("imageio-ffmpeg")
    if "whisper" in missing:
        packages.append("faster-whisper")
    return packages


def format_command_for_log(cmd: list[str]) -> str:
    safe_parts: list[str] = []
    hide_next = False
    for part in cmd:
        lowered = part.lower()
        if hide_next:
            safe_parts.append("***")
            hide_next = False
            continue
        if any(marker in lowered for marker in SENSITIVE_COMMAND_MARKERS):
            if "=" in part:
                key, _value = part.split("=", 1)
                safe_parts.append(f"{key}=***")
            else:
                safe_parts.append(part)
                hide_next = part.startswith("-")
            continue
        safe_parts.append(part)
    return " ".join(shlex.quote(part) for part in safe_parts)


def run_command_with_log(cmd: list[str], log: LogCallback, cwd: Path = ROOT) -> None:
    log(f"执行命令：{format_command_for_log(cmd)}")
    process = subprocess.Popen(
        cmd,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        **subprocess_hidden_kwargs(),
    )
    assert process.stdout is not None
    for line in process.stdout:
        line = line.strip()
        if line:
            log(line)
    exit_code = process.wait()
    if exit_code != 0:
        raise RuntimeError(f"命令执行失败，退出码：{exit_code}")


def ensure_ffmpeg_link() -> None:
    target = local_bin("ffmpeg")
    if target.exists():
        return
    try:
        import imageio_ffmpeg

        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        import extract_subtitle

        ffmpeg = extract_subtitle.resolve_ffmpeg_path()
    if ffmpeg and Path(ffmpeg).exists() and Path(ffmpeg) != target:
        target.parent.mkdir(parents=True, exist_ok=True)
        if IS_WINDOWS:
            shutil.copy2(ffmpeg, target)
        else:
            target.symlink_to(ffmpeg)


def build_env_summary(report: dict, ok: bool) -> str:
    cuda_data = report.get("cuda") or {}
    if ok and cuda_data and not cuda_data.get("ok"):
        return "已就绪，GPU 不可用，将使用 CPU"
    return "已就绪" if ok else "需要准备环境"


def format_env_report(report: dict) -> str:
    parts = []
    for name in ("ffmpeg", "yt-dlp", "whisper", "cuda"):
        data = report.get(name)
        if not data:
            continue
        if data.get("optional"):
            mark = "可选可用" if data["ok"] else "可选未启用"
        else:
            mark = "可用" if data["ok"] else "缺失"
        details = [f"{name}: {mark}"]
        if data.get("version"):
            details.append(f"版本 {data['version']}")
        if data.get("source"):
            details.append(data["source"])
        if data.get("path"):
            details.append(data["path"])
        if data.get("detail"):
            details.append(data["detail"])
        parts.append(" / ".join(details))
    return "\n".join(parts)
