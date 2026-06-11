#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal

import extract_subtitle
from model_config import (
    get_official_model_dir,
    is_preset_model,
    is_valid_model_dir,
)
from env_checker import (
    GPU_PACKAGES,
    REQUIRED_ENV_KEYS,
    check_environment,
    ensure_ffmpeg_link,
    install_command,
    missing_required_env,
    packages_for_missing,
    run_command_with_log,
)


class EnvWorker(QObject):
    log = Signal(str)
    done = Signal(bool, dict)

    def __init__(self, ffmpeg_path: str, yt_dlp_path: str, action: str):
        super().__init__()
        self.ffmpeg_path = ffmpeg_path.strip()
        self.yt_dlp_path = yt_dlp_path.strip()
        self.action = action

    def run(self) -> None:
        try:
            self.log.emit("环境检查线程已启动")
            if self.action == "update_ytdlp":
                self.update_ytdlp()
            elif self.action == "install_gpu":
                self.install_gpu()
            elif self.action == "prepare":
                self.update_ytdlp()
            report = self.check()
            missing = missing_required_env(report)
            if missing and self.action == "prepare":
                self.log.emit(f"检测到缺失依赖：{', '.join(missing)}，开始准备当前项目环境")
                self.install(missing)
                report = self.check()
            ok = all(report.get(name, {}).get("ok") for name in REQUIRED_ENV_KEYS)
            self.done.emit(ok, report)
        except Exception as exc:
            self.log.emit(f"环境任务失败：请检查当前 Python 环境或网络连接。\n详情：{exc}")
            self.done.emit(False, {})

    def check(self) -> dict:
        return check_environment(self.ffmpeg_path, self.yt_dlp_path, self.log.emit)

    def install(self, missing: list[str]) -> None:
        packages = packages_for_missing(missing)
        if not packages:
            return
        run_command_with_log(install_command(*packages), self.log.emit)
        if "ffmpeg" in missing:
            ensure_ffmpeg_link()

    def update_ytdlp(self) -> None:
        self.log.emit("开始更新 yt-dlp 下载组件")
        run_command_with_log(install_command("yt-dlp", upgrade=True), self.log.emit)

    def install_gpu(self) -> None:
        self.log.emit("开始安装 NVIDIA CUDA 相关 Python 组件")
        run_command_with_log(install_command(*GPU_PACKAGES), self.log.emit)


class ExtractWorker(QObject):
    log = Signal(str)
    done = Signal(bool, str)

    def __init__(
        self,
        url: str,
        model: str | None,
        device: str,
        cookies: str,
        ffmpeg: str,
        yt_dlp: str,
        cookies_from_browser: str | None = None,
        output_dir: str = "",
        model_display_name: str | None = None,
        model_is_local: bool | None = None,
        model_download_name: str | None = None,
        model_download_dir: str | None = None,
        subtitle_language: str = "zh",
    ):
        super().__init__()
        self.url = url
        self.model = model
        self.device = device
        self.cookies = cookies.strip() or None
        self.ffmpeg = ffmpeg.strip() or None
        self.yt_dlp = yt_dlp.strip() or None
        self.cookies_from_browser = cookies_from_browser
        self.output_dir = output_dir.strip() or None
        self.model_display_name = model_display_name
        self.model_is_local = model_is_local
        self.model_download_name = model_download_name
        self.model_download_dir = model_download_dir
        self.subtitle_language = subtitle_language

    def run(self) -> None:
        try:
            self.log.emit("字幕获取线程已启动")
            result = extract_subtitle.extract(
                url=self.url,
                model=self.model,
                device=self.device,
                compute_type="auto",
                cookies=self.cookies,
                ffmpeg_path=self.ffmpeg,
                yt_dlp_path=self.yt_dlp,
                log_callback=self.log.emit,
                cookies_from_browser=self.cookies_from_browser,
                output_dir=self.output_dir,
                model_display_name=self.model_display_name,
                model_is_local=self.model_is_local,
                model_download_name=self.model_download_name,
                model_download_dir=self.model_download_dir,
                subtitle_language=self.subtitle_language,
            )
            self.done.emit(True, str(result))
        except Exception as exc:
            self.done.emit(False, str(exc))


class ModelDeployWorker(QObject):
    done = Signal(bool, str)

    def __init__(self, model_source: str, model: str, models_dir: str | Path | None = None):
        super().__init__()
        self.model_source = model_source
        self.model = model.strip()
        self.models_dir = Path(models_dir) if models_dir else None

    def run(self) -> None:
        try:
            if self.model_source == "local":
                directory = Path(self.model)
                if not directory.is_dir():
                    self.done.emit(False, "本地模型目录不存在")
                elif not is_valid_model_dir(directory):
                    self.done.emit(False, "本地模型目录缺少基本模型文件")
                else:
                    self.done.emit(True, "本地模型目录可用")
                return

            if self.model_source != "preset" or not is_preset_model(self.model):
                raise ValueError("请先选择识别模型")

            from faster_whisper.utils import download_model

            model_dir = get_official_model_dir(self.model, self.models_dir)
            model_dir.mkdir(parents=True, exist_ok=True)
            download_model(self.model, output_dir=str(model_dir))
            if not is_valid_model_dir(model_dir):
                raise RuntimeError("下载完成，但模型目录缺少基本模型文件")
            self.done.emit(True, "已部署")
        except Exception as exc:
            self.done.emit(False, f"模型部署失败：{exc}")
