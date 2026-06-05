from __future__ import annotations

from dataclasses import dataclass


MODEL_PLACEHOLDER = ""
CUSTOM_MODEL_VALUE = "__custom__"
CUSTOM_MODEL_LABEL = "自定义模型路径 / Hugging Face 模型名"
MISSING_WHISPER_MODEL_MESSAGE = "未找到可用字幕，需要选择识别模型后再试。"

MODEL_INFO = {
    "tiny": {"desc": "速度最快，精度较低，适合快速预览或配置较低的设备。适合中文和英文音频。"},
    "base": {"desc": "速度较快，精度一般，适合日常使用。适合中文和英文音频。"},
    "small": {"desc": "速度与精度平衡，适合大多数场景。适合中文和英文音频。"},
    "medium": {"desc": "精度较高，需要较多系统内存和显存。适合中文和英文音频。"},
    "large-v1": {"desc": "大模型版本，精度较高，需要较多系统内存和显存。适合中文和英文音频。"},
    "large-v2": {"desc": "大模型版本，精度较高，需要较多系统内存和显存。适合中文和英文音频。"},
    "large-v3": {"desc": "最高精度，需要大量系统内存和显存，推荐有 GPU 的用户使用。适合中文和英文音频。"},
    "large": {"desc": "large 是 large-v3 的别名。适合中文和英文音频。"},
    "distil-large-v2": {"desc": "distil 模型。适合中文和英文音频。"},
    "distil-large-v3": {"desc": "distil 模型。适合中文和英文音频。"},
    "distil-large-v3.5": {"desc": "distil 模型。适合中文和英文音频。"},
    "large-v3-turbo": {"desc": "turbo 模型。适合中文和英文音频。"},
    "turbo": {"desc": "turbo 是 large-v3-turbo 的别名。适合中文和英文音频。"},
    "tiny.en": {"desc": "英文专用，不建议用于中文视频。"},
    "base.en": {"desc": "英文专用，不建议用于中文视频。"},
    "small.en": {"desc": "英文专用，不建议用于中文视频。"},
    "medium.en": {"desc": "英文专用，不建议用于中文视频。"},
    "distil-small.en": {"desc": "distil 模型。英文专用，不建议用于中文视频。"},
    "distil-medium.en": {"desc": "distil 模型。英文专用，不建议用于中文视频。"},
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
    [("请选择识别模型（不会自动下载）", MODEL_PLACEHOLDER)]
    + [(name, name) for name in UNIVERSAL_MODELS]
    + [(f"{name}（英文专用）", name) for name in ENGLISH_ONLY_MODELS]
    + [(CUSTOM_MODEL_LABEL, CUSTOM_MODEL_VALUE)]
)
MODELS = OFFICIAL_MODELS


@dataclass(frozen=True)
class ModelSelection:
    selected_value: str
    custom_value: str = ""


def normalize_model_value(model: str | None) -> str:
    return str(model or "").strip()


def is_preset_model(model: str | None) -> bool:
    return normalize_model_value(model) in OFFICIAL_MODELS


def is_english_only_model(model: str | None) -> bool:
    return normalize_model_value(model) in ENGLISH_ONLY_MODELS


def is_custom_model_source(model_source: str | None, model: str | None) -> bool:
    model_value = normalize_model_value(model)
    return model_source == "custom" and bool(model_value)


def is_custom_model_choice(selected_value: str | None) -> bool:
    return selected_value == CUSTOM_MODEL_VALUE


def get_model_display_label(model: str) -> str:
    if is_english_only_model(model):
        return f"{model}（英文专用）"
    if model == CUSTOM_MODEL_VALUE:
        return CUSTOM_MODEL_LABEL
    return model


def get_model_description(
    model: str | None,
    model_source: str | None = None,
    cuda_ok: bool = False,
) -> str:
    model_value = normalize_model_value(model)
    if not model_value:
        return "当前模型说明：请选择模型；模型只会在需要语音识别时加载，可能在首次使用时下载。"
    if model_value == CUSTOM_MODEL_VALUE or model_source == "custom":
        return (
            "当前模型说明：请确认本地目录或 Hugging Face 模型名兼容 faster-whisper / CTranslate2；"
            "模型只会在需要语音识别时加载，可能在首次使用时下载。"
        )

    info = MODEL_INFO.get(model_value, {"desc": ""})
    text = f"当前模型说明：{info['desc']} 模型只会在需要语音识别时加载，可能在首次使用时下载。"
    if cuda_ok and model_value in ("tiny", "base"):
        text += "\n检测到 GPU 可用，建议选择 medium 或 large-v3 以获得更好效果。"
    elif not cuda_ok and model_value in ("medium", "large-v3"):
        text += "\n未检测到 GPU，使用 CPU 运行此模型可能较慢，建议选择 small 或更小的模型。"
    return text


def resolve_model_from_settings(settings: dict) -> ModelSelection:
    model = normalize_model_value(settings.get("model"))
    model_source = settings.get("model_source")
    if is_custom_model_source(model_source, model):
        return ModelSelection(CUSTOM_MODEL_VALUE, model)
    if is_preset_model(model):
        return ModelSelection(model, "")
    if model:
        return ModelSelection(CUSTOM_MODEL_VALUE, model)
    return ModelSelection(MODEL_PLACEHOLDER, "")


def resolve_selected_model(selected_value: str | None, custom_value: str | None = None) -> str:
    if selected_value == CUSTOM_MODEL_VALUE:
        return normalize_model_value(custom_value)
    return normalize_model_value(selected_value)


def get_model_settings_fields(selected_value: str | None, custom_value: str | None = None) -> dict[str, str]:
    model = resolve_selected_model(selected_value, custom_value)
    if not selected_value:
        return {}
    model_source = "custom" if selected_value == CUSTOM_MODEL_VALUE else "preset"
    return {"model_source": model_source, "model": model}
