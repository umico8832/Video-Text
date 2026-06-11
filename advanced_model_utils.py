from __future__ import annotations

from pathlib import Path

from model_config import is_local_model_choice, is_valid_model_dir


STATUS_LABEL_COLORS = {
    "ok": ("#166534", "#dcfce7", "#bbf7d0"),
    "bad": ("#b91c1c", "#fee2e2", "#fecaca"),
    "pending": ("#475569", "#f1f5f9", "#e2e8f0"),
    "unknown": ("#334155", "#ffffff", "#e2e8f0"),
}


def model_action_status(
    selected_value: str | None,
    local_model_dir: str,
    deployed_models: set[str],
) -> str:
    if is_local_model_choice(selected_value):
        local_dir = local_model_dir.strip()
        if not local_dir:
            return "请选择本地模型目录。"
        if is_valid_model_dir(local_dir):
            return "本地模型目录可用。"
        if Path(local_dir).is_dir():
            return "本地模型目录缺少基本模型文件。"
        return "本地模型目录不存在。"
    if selected_value:
        return "已部署，可离线使用。" if selected_value in deployed_models else "未部署，可点击下载/部署。"
    return "请选择 Whisper 模型。"


def status_label_style(state: str = "unknown") -> str:
    color, bg, border = STATUS_LABEL_COLORS.get(state, STATUS_LABEL_COLORS["unknown"])
    return f"""
            color: {color};
            background: {bg};
            border: 1px solid {border};
            border-radius: 7px;
            padding: 8px 10px;
            font-weight: 500;
        """


def run_info_status(report: dict | None) -> tuple[tuple[str, str], tuple[str, str], tuple[str, str]]:
    whisper = (report or {}).get("whisper") or {}
    cuda = (report or {}).get("cuda") or {}
    whisper_ok = whisper.get("ok")
    cuda_ok = cuda.get("ok")
    return (
        (
            f"语音识别：{'可用' if whisper_ok else '不可用' if whisper else '未检测'}",
            "ok" if whisper_ok else "bad" if whisper else "unknown",
        ),
        (
            f"GPU 加速：{'可用' if cuda_ok else '不可用' if cuda else '未检测'}",
            "ok" if cuda_ok else "bad" if cuda else "unknown",
        ),
        (
            f"faster-whisper 版本：{whisper.get('version') or '未知'}",
            "unknown",
        ),
    )
