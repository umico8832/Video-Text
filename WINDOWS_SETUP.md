# Windows portable setup

This project is intended to be distributed as a lightweight portable Windows tool.
Users provide Python. The app creates and uses a local `.venv` next to the project
files.

## User quick start

1. Install Python 3.12 from https://www.python.org/downloads/windows/.
2. During installation, enable `Add python.exe to PATH`.
3. Unzip this project.
4. Double-click `视频字幕提取.exe` if it is included.
5. If the exe is missing or blocked, double-click `启动软件.bat`.

On first launch, the launcher will:

- create `.venv` if it does not exist;
- upgrade pip;
- install packages from `requirements.txt`;
- start `video_text_gui.py`.

Later launches reuse the existing `.venv`. Dependencies are reinstalled only when
`requirements.txt` changes or the environment is missing its requirement stamp.

## What is not bundled by default

The portable package should not include:

- `.venv`
- `.launcher-build`
- `build`
- `dist`
- `*.spec`
- `__pycache__`
- `outputs`
- `*.log`
- Whisper model caches
- NVIDIA / CUDA GPU runtime packages

Whisper models are downloaded on first use. GPU acceleration packages should be
installed from the GUI only when needed.

## GUI environment setup

After the GUI opens, use `检查环境` first.

The GUI can prepare application-level dependencies such as `yt-dlp`,
`imageio-ffmpeg`, `faster-whisper`, and the local FFmpeg link. CUDA/GPU support is
optional and does not block basic subtitle extraction.

## Developer: build the lightweight launcher exe

Run:

```bat
build_launcher.bat
```

The launcher exe will be created at:

```text
dist\视频字幕提取.exe
```

The build script also copies the exe to the project root as:

```text
视频字幕提取.exe
```

This exe is only a launcher. It does not bundle the full GUI application,
PySide6, Whisper, model files, or GPU libraries.

For release, package the root `视频字幕提取.exe` with:

- `video_text_gui.py`
- `extract_subtitle.py`
- `launcher.py`
- `requirements.txt`
- `启动软件.bat`
- `WINDOWS_SETUP.md`

Do not package the local development `.venv`.
