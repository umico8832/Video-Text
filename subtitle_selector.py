from __future__ import annotations

from typing import Any


ZH_ALIASES = (
    "zh",
    "zh-cn",
    "zh-hans",
    "zh-sg",
    "zh-hant",
    "zh-tw",
    "cmn",
    "zho",
    "chi",
    "chinese",
    "中文",
    "简体",
    "繁体",
)

EN_ALIASES = (
    "en",
    "en-us",
    "en-gb",
    "en-au",
    "en-ca",
    "eng",
    "english",
)

SUBTITLE_LANGUAGE_LABELS = {
    "zh": "中文字幕",
    "en": "英文字幕",
}

SUBTITLE_EXT_PRIORITY = {
    "srt": 0,
    "vtt": 1,
    "json3": 2,
    "json": 3,
    "ass": 4,
    "ssa": 5,
}


def subtitle_language_aliases(language: str | None) -> tuple[str, ...]:
    return EN_ALIASES if language == "en" else ZH_ALIASES


def subtitle_language_label(language: str | None) -> str:
    return SUBTITLE_LANGUAGE_LABELS.get(language or "zh", "目标语言字幕")


def lang_score(lang: str, language: str | None = "zh") -> int | None:
    normalized = lang.lower()
    if normalized == "danmaku":
        return None
    for idx, alias in enumerate(subtitle_language_aliases(language)):
        if alias in normalized:
            return idx
    return None


def choose_subtitle(
    info: dict[str, Any],
    language: str | None = "zh",
) -> tuple[str, dict[str, Any], str] | None:
    candidates: list[tuple[int, int, int, str, dict[str, Any], str]] = []

    for source_name, source_priority in (("subtitles", 0), ("automatic_captions", 1)):
        subtitles = info.get(source_name) or {}
        for lang, entries in subtitles.items():
            score = lang_score(lang, language)
            if score is None:
                continue
            for entry in entries or []:
                ext = (entry.get("ext") or "").lower()
                if not entry.get("url"):
                    continue
                ext_priority = SUBTITLE_EXT_PRIORITY.get(ext, 99)
                candidates.append(
                    (source_priority, score, ext_priority, lang, entry, source_name)
                )

    if not candidates:
        return None

    candidates.sort(key=lambda item: item[:3])
    _, _, _, lang, entry, source_name = candidates[0]
    return lang, entry, source_name
