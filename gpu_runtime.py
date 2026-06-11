from __future__ import annotations

import os
import platform
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
IS_WINDOWS = platform.system() == "Windows"


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
