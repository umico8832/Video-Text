# Video-Text

Windows desktop tool for extracting Chinese subtitles from online videos. It first tries to download existing subtitles with `yt-dlp`; if no suitable subtitles are available, it downloads audio and transcribes it with `faster-whisper`.

## Features

- PySide6 desktop GUI
- YouTube and Bilibili link processing through `yt-dlp`
- Existing subtitle download with Whisper fallback
- SRT, VTT, ASS/SSA, JSON and JSON3 parsing
- Optional CUDA acceleration through `faster-whisper`
- Lightweight launcher that prepares the Python environment

## Requirements

- Windows 10/11
- Python 3.12 recommended
- FFmpeg, provided by `imageio-ffmpeg` or installed separately

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
```

## Run

```powershell
.\.venv\Scripts\python launcher.py
```

You can also run `启动软件.bat` on Windows.

## Configuration

Copy `settings.example.json` to `settings.json` if you want to prepare defaults manually. Local paths, cookies and generated outputs are intentionally ignored by git.

## Build Launcher

```powershell
.\build_launcher.ps1
```

The packaged executable is generated locally and is not committed to the repository.
