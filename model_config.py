from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent
MODELS_DIR = ROOT / "models"
MODEL_PLACEHOLDER = ""
LOCAL_MODEL_VALUE = "__local__"
LOCAL_MODEL_LABEL = "本地模型目录"
AVAILABLE_SUFFIX = "  ✅ 可用"
MISSING_WHISPER_MODEL_MESSAGE = "未找到可用字幕，需要选择识别模型后再试。"

MODEL_RESOURCE_INFO = {
    "tiny": {
        "disk": "1GB 以内",
        "memory": "4GB+",
        "vram": "不强制，CPU 可用",
        "scenario": "快速测试、很短视频、验证流程",
        "note": "速度最快，资源占用最低，准确率较低。",
    },
    "tiny.en": {
        "disk": "1GB 以内",
        "memory": "4GB+",
        "vram": "不强制，CPU 可用",
        "scenario": "英文快速测试、很短视频、验证流程",
        "note": "速度最快，资源占用最低，准确率较低。英文专用，不建议用于中文视频。",
    },
    "base": {
        "disk": "1GB 以内",
        "memory": "4GB+",
        "vram": "不强制，CPU 可用",
        "scenario": "短视频、快速预览、配置一般的电脑",
        "note": "比 tiny 稍稳，但仍不适合高要求转写。",
    },
    "base.en": {
        "disk": "1GB 以内",
        "memory": "4GB+",
        "vram": "不强制，CPU 可用",
        "scenario": "英文短视频、快速预览、配置一般的电脑",
        "note": "比 tiny 稍稳，但仍不适合高要求转写。英文专用，不建议用于中文视频。",
    },
    "small": {
        "disk": "约 2GB",
        "memory": "8GB+",
        "vram": "2GB+ 更稳，CPU 也可用但会慢",
        "scenario": "普通中文/英文视频、首次正式使用",
        "note": "速度和识别质量比较均衡。",
    },
    "small.en": {
        "disk": "约 2GB",
        "memory": "8GB+",
        "vram": "2GB+ 更稳，CPU 也可用但会慢",
        "scenario": "普通英文视频、首次正式使用",
        "note": "速度和识别质量比较均衡。英文专用，不建议用于中文视频。",
    },
    "medium": {
        "disk": "约 4GB",
        "memory": "8GB-16GB+",
        "vram": "4GB+ 更稳",
        "scenario": "较长视频、对识别质量要求更高的内容",
        "note": "比 small 更慢，占用更高。",
    },
    "medium.en": {
        "disk": "约 4GB",
        "memory": "8GB-16GB+",
        "vram": "4GB+ 更稳",
        "scenario": "较长英文视频、对识别质量要求更高的内容",
        "note": "比 small 更慢，占用更高。英文专用，不建议用于中文视频。",
    },
    "large-v1": {
        "disk": "约 6GB+",
        "memory": "16GB+",
        "vram": "6GB-8GB+ 更稳",
        "scenario": "长视频、口音较重、背景噪声较多、识别质量要求较高的内容",
        "note": "下载和加载更慢，资源占用更高；低显存机器可考虑 small、medium、turbo 或 int8/CPU 模式。",
    },
    "large-v2": {
        "disk": "约 6GB+",
        "memory": "16GB+",
        "vram": "6GB-8GB+ 更稳",
        "scenario": "长视频、口音较重、背景噪声较多、识别质量要求较高的内容",
        "note": "下载和加载更慢，资源占用更高；低显存机器可考虑 small、medium、turbo 或 int8/CPU 模式。",
    },
    "large-v3": {
        "disk": "约 6GB+",
        "memory": "16GB+",
        "vram": "6GB-8GB+ 更稳",
        "scenario": "长视频、口音较重、背景噪声较多、识别质量要求较高的内容",
        "note": "下载和加载更慢，资源占用更高；低显存机器可考虑 small、medium、turbo 或 int8/CPU 模式。",
    },
    "large": {
        "disk": "约 6GB+",
        "memory": "16GB+",
        "vram": "6GB-8GB+ 更稳",
        "scenario": "长视频、口音较重、背景噪声较多、识别质量要求较高的内容",
        "note": "large 是 large-v3 的别名；下载和加载较慢，资源占用较高。",
    },
    "large-v3-turbo": {
        "disk": "约 3GB-5GB",
        "memory": "8GB-16GB+",
        "vram": "4GB+ 更稳",
        "scenario": "在较高识别质量和速度之间取得平衡",
        "note": "通常比 large-v3 更偏速度；实际效果仍取决于音频质量和语言场景。",
    },
    "turbo": {
        "disk": "约 3GB-5GB",
        "memory": "8GB-16GB+",
        "vram": "4GB+ 更稳",
        "scenario": "在较高识别质量和速度之间取得平衡",
        "note": "turbo 是 large-v3-turbo 的别名；实际效果仍取决于音频质量和语言场景。",
    },
    "distil-small.en": {
        "disk": "参考 small 级别",
        "memory": "8GB+",
        "vram": "2GB-4GB+ 更稳",
        "scenario": "英文视频、希望降低资源占用或提高速度",
        "note": "英文相关蒸馏模型。英文专用，不建议用于中文视频。",
    },
    "distil-medium.en": {
        "disk": "参考 medium 级别",
        "memory": "8GB+",
        "vram": "2GB-4GB+ 更稳",
        "scenario": "英文视频、希望降低资源占用或提高速度",
        "note": "英文相关蒸馏模型。英文专用，不建议用于中文视频。",
    },
    "distil-large-v2": {
        "disk": "约 3GB-6GB",
        "memory": "8GB-16GB+",
        "vram": "4GB+ 更稳",
        "scenario": "减少 large 系列资源占用，同时保留较高识别能力",
        "note": "蒸馏模型，效果取决于语言、音频质量和场景；中文视频建议优先考虑通用 small/medium/large/turbo。",
    },
    "distil-large-v3": {
        "disk": "约 3GB-6GB",
        "memory": "8GB-16GB+",
        "vram": "4GB+ 更稳",
        "scenario": "减少 large 系列资源占用，同时保留较高识别能力",
        "note": "蒸馏模型，效果取决于语言、音频质量和场景；中文视频建议优先考虑通用 small/medium/large/turbo。",
    },
    "distil-large-v3.5": {
        "disk": "约 3GB-6GB",
        "memory": "8GB-16GB+",
        "vram": "4GB+ 更稳",
        "scenario": "减少 large 系列资源占用，同时保留较高识别能力",
        "note": "蒸馏模型，效果取决于语言、音频质量和场景；中文视频建议优先考虑通用 small/medium/large/turbo。",
    },
}
UNIVERSAL_MODELS = [
    "tiny",
    "base",
    "small",
    "medium",
    "large-v1",
    "large-v2",
    "large-v3",
    "large",
    "distil-large-v2",
    "distil-large-v3",
    "distil-large-v3.5",
    "large-v3-turbo",
    "turbo",
]
ENGLISH_ONLY_MODELS = [
    "tiny.en",
    "base.en",
    "small.en",
    "medium.en",
    "distil-small.en",
    "distil-medium.en",
]
OFFICIAL_MODELS = UNIVERSAL_MODELS + ENGLISH_ONLY_MODELS
MODEL_CHOICES = (
    [("请选择识别模型（需手动确认下载）", MODEL_PLACEHOLDER)]
    + [(name, name) for name in UNIVERSAL_MODELS]
    + [(f"{name}（英文专用）", name) for name in ENGLISH_ONLY_MODELS]
    + [(LOCAL_MODEL_LABEL, LOCAL_MODEL_VALUE)]
)
MODELS = OFFICIAL_MODELS


@dataclass(frozen=True)
class ModelSelection:
    selected_value: str
    local_value: str = ""


@dataclass(frozen=True)
class ModelRuntimeSelection:
    model: str
    display_name: str
    is_local: bool
    requires_download: bool
    error_message: str = ""
    download_model: str = ""
    download_dir: str = ""


def normalize_model_value(model: str | None) -> str:
    return str(model or "").strip()


def is_preset_model(model: str | None) -> bool:
    return normalize_model_value(model) in OFFICIAL_MODELS


def is_english_only_model(model: str | None) -> bool:
    return normalize_model_value(model) in ENGLISH_ONLY_MODELS


def is_local_model_source(model_source: str | None, model: str | None) -> bool:
    model_value = normalize_model_value(model)
    return model_source in {"local", "custom"} and bool(model_value)


def is_local_model_choice(selected_value: str | None) -> bool:
    return selected_value == LOCAL_MODEL_VALUE


def get_official_model_dir(
    model: str,
    models_dir: str | Path | None = None,
) -> Path:
    if not is_preset_model(model):
        raise ValueError(f"不是官方 preset 模型：{model}")
    base_dir = Path(models_dir) if models_dir is not None else MODELS_DIR
    return base_dir / normalize_model_value(model)


def is_valid_model_dir(model_dir: str | Path | None) -> bool:
    if not model_dir:
        return False
    directory = Path(model_dir)
    if not directory.is_dir():
        return False
    required_files = (directory / "config.json", directory / "model.bin")
    metadata_files = (
        directory / "tokenizer.json",
        directory / "preprocessor_config.json",
    )
    has_vocabulary = any(directory.glob("vocabulary.*"))
    return all(path.is_file() for path in required_files) and (
        any(path.is_file() for path in metadata_files) or has_vocabulary
    )


def scan_deployed_models(models_dir: str | Path | None = None) -> set[str]:
    return {
        model
        for model in OFFICIAL_MODELS
        if is_valid_model_dir(get_official_model_dir(model, models_dir))
    }


def get_model_display_label(
    model: str,
    deployed_models: set[str] | None = None,
) -> str:
    if is_english_only_model(model):
        label = f"{model}（英文专用）"
    elif model == LOCAL_MODEL_VALUE:
        return LOCAL_MODEL_LABEL
    else:
        label = model
    if deployed_models and model in deployed_models:
        return f"{label}{AVAILABLE_SUFFIX}"
    return label


def get_model_choices(deployed_models: set[str] | None = None) -> list[tuple[str, str]]:
    return [
        (get_model_display_label(value, deployed_models) if value else label, value)
        for label, value in MODEL_CHOICES
    ]


def resolve_preset_model_for_extract(
    model: str | None,
    models_dir: str | Path | None = None,
) -> str:
    model_value = normalize_model_value(model)
    if not is_preset_model(model_value):
        return model_value
    local_dir = get_official_model_dir(model_value, models_dir)
    if is_valid_model_dir(local_dir):
        return str(local_dir)
    return model_value


def resolve_model_for_runtime(
    selected_value: str | None,
    local_value: str | None = None,
    models_dir: str | Path | None = None,
) -> ModelRuntimeSelection:
    if is_local_model_choice(selected_value):
        model = normalize_model_value(local_value)
        if not model:
            return ModelRuntimeSelection("", "", False, False, "请选择本地模型目录。")
        if is_valid_model_dir(model):
            return ModelRuntimeSelection(model, model, True, False)
        if Path(model).is_dir():
            return ModelRuntimeSelection(
                model,
                model,
                False,
                False,
                "本地模型目录缺少基本模型文件。",
            )
        return ModelRuntimeSelection(model, model, False, False, "本地模型目录不存在。")

    model = normalize_model_value(selected_value)
    if not model:
        return ModelRuntimeSelection("", "", False, False, MISSING_WHISPER_MODEL_MESSAGE)
    if is_preset_model(model):
        local_dir = get_official_model_dir(model, models_dir)
        if is_valid_model_dir(local_dir):
            return ModelRuntimeSelection(str(local_dir), model, True, False)
        return ModelRuntimeSelection(
            str(local_dir),
            model,
            True,
            True,
            download_model=model,
            download_dir=str(local_dir),
        )

    if is_valid_model_dir(model):
        return ModelRuntimeSelection(model, model, True, False)
    if Path(model).exists():
        return ModelRuntimeSelection(model, model, False, False, "本地模型目录不可用。")
    return ModelRuntimeSelection(model, model, False, True)


def get_model_description(
    model: str | None,
    model_source: str | None = None,
    cuda_ok: bool = False,
) -> str:
    model_value = normalize_model_value(model)
    if not model_value:
        return "当前模型说明：请选择模型；模型只会在需要语音识别时加载，可能在首次使用时下载。"
    if model_value == LOCAL_MODEL_VALUE or model_source in {"local", "custom"}:
        return (
            "当前模型说明：\n"
            "支持已经下载好的本地 CTranslate2 模型目录。请确认目录兼容 faster-whisper。\n"
            "资源建议：推荐磁盘、内存和显存取决于具体模型\n"
            "说明：软件不会自动下载本地模型目录对应的远程模型。"
        )

    info = MODEL_RESOURCE_INFO[model_value]
    text = (
        "当前模型说明：\n"
        f"推荐磁盘：{info['disk']}　建议内存：{info['memory']}　建议显存：{info['vram']}\n"
        f"适合场景：{info['scenario']}\n"
        f"说明：{info['note']} 以上为经验参考，实际占用受 device、compute_type、音频长度、"
        "显卡驱动、CUDA、beam_size 等影响；模型仅在需要语音识别时加载，首次使用时可能下载。"
    )
    if cuda_ok and model_value in ("tiny", "base"):
        text += "\n检测到 GPU 可用，建议选择 medium 或 large-v3 以获得更好效果。"
    elif not cuda_ok and model_value in ("medium", "large-v3"):
        text += "\n未检测到 GPU，使用 CPU 运行此模型可能较慢，建议选择 small 或更小的模型。"
    return text


def resolve_model_from_settings(settings: dict) -> ModelSelection:
    model = normalize_model_value(settings.get("model"))
    model_source = settings.get("model_source")
    if is_preset_model(model):
        return ModelSelection(model, "")
    if is_local_model_source(model_source, model):
        return ModelSelection(LOCAL_MODEL_VALUE, model)
    if model:
        return ModelSelection(LOCAL_MODEL_VALUE, model)
    return ModelSelection(MODEL_PLACEHOLDER, "")


def resolve_selected_model(selected_value: str | None, local_value: str | None = None) -> str:
    if selected_value == LOCAL_MODEL_VALUE:
        return normalize_model_value(local_value)
    return normalize_model_value(selected_value)


def get_model_settings_fields(selected_value: str | None, local_value: str | None = None) -> dict[str, str]:
    model = resolve_selected_model(selected_value, local_value)
    if not selected_value:
        return {}
    model_source = "local" if selected_value == LOCAL_MODEL_VALUE else "preset"
    return {"model_source": model_source, "model": model}
