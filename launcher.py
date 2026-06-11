#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

from process_utils import subprocess_hidden_kwargs


APP_NAME = "视频字幕提取"
PYTHON_VERSION = "3.12"
LOG_NAME = "launcher.log"
REQ_STAMP_NAME = ".requirements.sha256"


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


ROOT = app_dir()
LOG_PATH = ROOT / LOG_NAME
VENV_DIR = ROOT / ".venv"
VENV_PYTHON = VENV_DIR / "Scripts" / "python.exe"
VENV_PYTHONW = VENV_DIR / "Scripts" / "pythonw.exe"
REQUIREMENTS = ROOT / "requirements.txt"
GUI_SCRIPT = ROOT / "video_text_gui.py"
REQ_STAMP = VENV_DIR / REQ_STAMP_NAME


def log(message: str) -> None:
    if getattr(sys, "stdout", None) is not None:
        print(message, flush=True)
    with LOG_PATH.open("a", encoding="utf-8") as file:
        file.write(message + "\n")


def configure_stdio() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None or not hasattr(stream, "reconfigure"):
            continue
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def pause_on_failure() -> None:
    if os.name == "nt":
        if getattr(sys, "stdin", None) is None:
            return
        try:
            input("\n按回车键退出...")
        except (EOFError, RuntimeError):
            pass


def run(cmd: list[str], *, cwd: Path = ROOT) -> None:
    log("> " + " ".join(cmd))
    process = subprocess.Popen(
        cmd,
        cwd=str(cwd),
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
        line = line.rstrip()
        if line:
            log(line)
    code = process.wait()
    if code != 0:
        raise RuntimeError(f"命令执行失败，退出码 {code}: {' '.join(cmd)}")


def python_version_ok(cmd: list[str]) -> bool:
    try:
        result = subprocess.run(
            [
                *cmd,
                "-c",
                "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            **subprocess_hidden_kwargs(),
        )
        return result.returncode == 0 and result.stdout.strip() == PYTHON_VERSION
    except OSError:
        return False


def find_system_python() -> list[str]:
    candidates = [
        ["py", f"-{PYTHON_VERSION}"],
        ["python"],
    ]
    for candidate in candidates:
        if python_version_ok(candidate):
            return candidate
    raise RuntimeError(
        f"未找到 Python。请先安装 Python {PYTHON_VERSION}，并在安装时勾选 Add python.exe to PATH。"
    )


def requirements_hash() -> str:
    if not REQUIREMENTS.exists():
        raise RuntimeError(f"缺少依赖文件：{REQUIREMENTS}")
    return hashlib.sha256(REQUIREMENTS.read_bytes()).hexdigest()


def requirements_installed() -> bool:
    if not VENV_PYTHON.exists() or not VENV_PYTHONW.exists():
        return False
    if not REQ_STAMP.exists():
        return False
    return REQ_STAMP.read_text(encoding="utf-8").strip() == requirements_hash()


def create_venv() -> None:
    if VENV_PYTHON.exists() and VENV_PYTHONW.exists():
        return
    python_cmd = find_system_python()
    log(f"创建虚拟环境：{VENV_DIR}")
    run([*python_cmd, "-m", "venv", str(VENV_DIR)])


def install_requirements() -> None:
    log("安装/更新基础依赖")
    run([str(VENV_PYTHON), "-m", "pip", "install", "--upgrade", "pip"])
    run([str(VENV_PYTHON), "-m", "pip", "install", "-r", str(REQUIREMENTS)])
    REQ_STAMP.write_text(requirements_hash(), encoding="utf-8")


def start_gui() -> None:
    if not GUI_SCRIPT.exists():
        raise RuntimeError(f"缺少 GUI 入口文件：{GUI_SCRIPT}")
    python_for_gui = VENV_PYTHONW if VENV_PYTHONW.exists() else VENV_PYTHON
    log(f"启动 {APP_NAME}")
    gui_log = LOG_PATH.open("a", encoding="utf-8")
    subprocess.Popen(
        [str(python_for_gui), str(GUI_SCRIPT)],
        cwd=str(ROOT),
        stdout=gui_log,
        stderr=subprocess.STDOUT,
        close_fds=True,
        **subprocess_hidden_kwargs(),
    )


def main() -> int:
    configure_stdio()
    LOG_PATH.write_text("", encoding="utf-8")
    log(f"{APP_NAME} 启动器")
    log(f"项目目录：{ROOT}")
    create_venv()
    if not requirements_installed():
        install_requirements()
    else:
        log("基础依赖已就绪")
    start_gui()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        log(f"启动失败：{exc}")
        log(f"详细日志：{LOG_PATH}")
        pause_on_failure()
        raise SystemExit(1)
