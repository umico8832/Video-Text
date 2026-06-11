from __future__ import annotations

from PySide6.QtWidgets import QMessageBox, QWidget


def ask_confirmation(
    parent: QWidget,
    title: str,
    text: str,
    informative_text: str,
    accept_text: str,
) -> bool:
    message_box = QMessageBox(parent)
    message_box.setIcon(QMessageBox.Icon.Question)
    message_box.setWindowTitle(title)
    message_box.setText(text)
    message_box.setInformativeText(informative_text)
    continue_button = message_box.addButton(accept_text, QMessageBox.ButtonRole.AcceptRole)
    message_box.addButton("取消", QMessageBox.ButtonRole.RejectRole)
    message_box.exec()
    return message_box.clickedButton() is continue_button


def confirm_model_deploy(
    parent: QWidget,
    model_name: str,
    model_source: str,
    models_dir: str,
) -> bool:
    if model_source == "preset":
        return ask_confirmation(
            parent,
            "确认下载/部署模型",
            f"即将下载/部署 Whisper 模型：{model_name}",
            "该操作可能需要联网，并占用一定磁盘空间。\n"
            f"模型将保存到：{models_dir}\n\n"
            "是否继续？",
            "继续部署",
        )
    return ask_confirmation(
        parent,
        "确认下载/部署模型",
        f"即将检查本地 Whisper 模型目录：{model_name}",
        "该操作不会下载模型，只会检查所选目录是否可用。\n\n"
        "是否继续？",
        "继续部署",
    )


def confirm_missing_model_download(parent: QWidget, display_name: str) -> bool:
    return ask_confirmation(
        parent,
        "需要下载 Whisper 模型",
        f"当前未检测到本地 Whisper 模型：{display_name}。",
        "继续识别需要下载该模型，可能占用一定时间和磁盘空间。\n是否现在下载并继续？",
        "下载并继续",
    )


def confirm_gpu_install(parent: QWidget) -> bool:
    return ask_confirmation(
        parent,
        "确认安装 GPU 加速组件",
        "即将安装 GPU 加速组件。",
        "该操作会安装 NVIDIA CUDA 相关 Python 包，适用于 NVIDIA 显卡用户。\n"
        "它不会安装显卡驱动，也不会保证所有 CUDA 环境问题都能自动修复。\n"
        "安装可能耗时，并会修改当前 Python 虚拟环境。\n\n"
        "是否继续？",
        "继续安装",
    )


def confirm_ytdlp_update(parent: QWidget) -> bool:
    return ask_confirmation(
        parent,
        "确认更新 yt-dlp",
        "即将更新 yt-dlp 下载组件。",
        "该操作可能需要联网，只会更新 yt-dlp，不会更新 FFmpeg。\n"
        "如果当前使用的是手动指定的外部 yt-dlp，请确认是否继续。\n\n"
        "是否继续？",
        "继续更新",
    )
