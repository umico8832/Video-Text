from __future__ import annotations


READY_COLOR = "#16a34a"
FAILED_COLOR = "#dc2626"
NEUTRAL_COLOR = "#172033"


def status_from_log(message: str) -> str | None:
    if "开始环境检查" in message or "环境检查线程已启动" in message:
        return "环境检查中"
    if "环境已就绪" in message:
        return "准备就绪"
    if "环境未就绪" in message:
        return "环境未就绪，请检查配置"
    if "获取视频信息" in message:
        return "正在获取视频信息"
    if "查找视频自带中文字幕" in message:
        return "正在查找已有中文字幕"
    if "查找视频自带英文字幕" in message:
        return "正在查找已有英文字幕"
    if "已找到视频自带中文字幕" in message or "已找到视频自带英文字幕" in message:
        return "正在下载字幕"
    if "未找到可用中文字幕" in message or "未找到可用英文字幕" in message:
        return "正在准备语音识别"
    if "下载音频" in message or "音频下载完成" in message:
        return "正在下载音频"
    if "正在加载本地 Whisper 模型" in message or "开始下载 Whisper 模型" in message:
        return "正在加载识别模型"
    if "已取消：未下载 Whisper 模型" in message:
        return "已取消"
    if "正在识别音频内容" in message or "识别进度" in message:
        return "正在语音识别"
    if "字幕文本已保存到" in message:
        return "正在保存结果"
    return None


def status_badge_state(env_status_text: str, current_status_text: str) -> tuple[str, str]:
    env_text = env_status_text.replace("环境状态：", "").strip()
    state_text = current_status_text.replace("当前状态：", "").strip()
    ready = "就绪" in env_text or "准备就绪" in state_text
    failed = "未就绪" in env_text or "失败" in state_text or "缺少" in state_text
    color = READY_COLOR if ready and not failed else FAILED_COLOR if failed else NEUTRAL_COLOR
    summary = env_text if env_text and env_text != "未检查" else state_text
    return summary or "未检查", color
