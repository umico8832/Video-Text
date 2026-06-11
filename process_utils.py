from __future__ import annotations

import os
import subprocess


def subprocess_hidden_kwargs() -> dict:
    if os.name != "nt":
        return {}
    if hasattr(subprocess, "CREATE_NO_WINDOW"):
        return {"creationflags": subprocess.CREATE_NO_WINDOW}
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    return {"startupinfo": startupinfo}
