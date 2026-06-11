from __future__ import annotations

from pathlib import Path

from model_config import is_local_model_choice, is_preset_model, is_valid_model_dir


def model_summary_text(
    selected_model: str | None,
    local_model_dir: str,
    deployed_models: set[str],
) -> str:
    if is_local_model_choice(selected_model):
        return "本地模型" if local_model_dir.strip() else "本地模型未选择"
    if selected_model:
        status = "已部署" if selected_model in deployed_models else "未部署"
        return f"{selected_model}（{status}）"
    return "未选择识别模型"


def device_display_text(device: str) -> str:
    return {
        "auto": "自动选择",
        "cuda": "GPU 模式",
        "cpu": "CPU 模式",
    }.get(device, device)


def selected_model_status(
    selected_model: str | None,
    local_model_dir: str,
    deployed_models: set[str],
) -> str | None:
    if is_local_model_choice(selected_model):
        local_dir = local_model_dir.strip()
        if not local_dir:
            return "未检查"
        if is_valid_model_dir(local_dir):
            return "本地模型目录可用"
        if Path(local_dir).is_dir():
            return "本地模型目录缺少基本模型文件"
        return "本地模型目录不存在"
    if is_preset_model(selected_model):
        return "已部署" if selected_model in deployed_models else "未部署"
    return None
