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
- `models`
- `settings.json`
- `cookies.txt`
- `*.log`
- Whisper model caches
- NVIDIA / CUDA GPU runtime packages

Whisper models are downloaded on first use. GPU acceleration packages should be
installed from the GUI only when needed.

## Runtime tools and release manifest

Current code resolves bundled tools from the project-local virtual environment:

- FFmpeg: `.venv\Scripts\ffmpeg.exe`
- yt-dlp: `.venv\Scripts\yt-dlp.exe`

The GUI can prepare these tools during environment setup, but `.venv` is a local
runtime environment and should not be committed or included in the normal release
archive.

If FFmpeg and yt-dlp are later shipped as repository-owned runtime files, use a
stable bundled tools directory such as:

```text
tools\ffmpeg\bin\ffmpeg.exe
tools\yt-dlp\yt-dlp.exe
```

In that case, update the application path resolution and release script to copy
that directory, then add a matching `.gitignore` exception for only that bundled
tools directory.

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

- `launcher.py`
- `video_text_gui.py`
- `extract_subtitle.py`
- `workers.py`
- `settings_manager.py`
- `model_config.py`
- `env_checker.py`
- `model_picker_dialog.py`
- `ui_components.py`
- `advanced_settings_dialog.py`
- `advanced_env_tab.py`
- `advanced_model_tab.py`
- `advanced_cookies_tab.py`
- `requirements.txt`
- `README.md`
- `WINDOWS_SETUP.md`
- `启动软件.bat`
- bundled runtime tools directory, only after the code and release script are
  updated to use it

Do not package:

- `.venv`
- `.launcher-build`
- `build`
- `dist`
- `outputs`
- `models`
- `settings.json`
- `cookies.txt`
- `*.log`
- `.git`
