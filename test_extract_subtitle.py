import json
import sys
import types
import unittest
from types import SimpleNamespace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from extract_subtitle import (
    build_output_path,
    choose_subtitle,
    extract_existing_subtitle,
    format_download_error,
    get_info,
    parse_ass,
    parse_json_subtitle,
    parse_vtt_or_srt,
    sanitize_filename,
    transcribe_audio,
)


class SubtitleSelectionTest(unittest.TestCase):
    def test_choose_subtitle_prefers_manual_chinese_over_auto(self):
        manual_entry = {"ext": "vtt", "url": "https://example.test/manual.vtt"}
        auto_entry = {"ext": "srt", "url": "https://example.test/auto.srt"}
        selected = choose_subtitle(
            {
                "subtitles": {"zh-CN": [manual_entry]},
                "automatic_captions": {"zh-CN": [auto_entry]},
            }
        )

        self.assertEqual(selected, ("zh-CN", manual_entry, "subtitles"))

    def test_choose_subtitle_prefers_higher_priority_extension(self):
        srt_entry = {"ext": "srt", "url": "https://example.test/sub.srt"}
        vtt_entry = {"ext": "vtt", "url": "https://example.test/sub.vtt"}
        selected = choose_subtitle(
            {
                "subtitles": {
                    "zh": [vtt_entry, srt_entry],
                },
            }
        )

        self.assertEqual(selected, ("zh", srt_entry, "subtitles"))

    def test_choose_subtitle_ignores_danmaku_and_entries_without_url(self):
        selected = choose_subtitle(
            {
                "subtitles": {
                    "danmaku": [{"ext": "json", "url": "https://example.test/danmaku"}],
                    "zh": [{"ext": "vtt"}],
                },
                "automatic_captions": {"en": [{"ext": "vtt", "url": "https://example.test/en.vtt"}]},
            }
        )

        self.assertIsNone(selected)

    def test_choose_subtitle_can_target_english(self):
        zh_entry = {"ext": "srt", "url": "https://example.test/zh.srt"}
        en_entry = {"ext": "vtt", "url": "https://example.test/en.vtt"}
        selected = choose_subtitle(
            {
                "subtitles": {
                    "zh-CN": [zh_entry],
                    "en-US": [en_entry],
                },
            },
            language="en",
        )

        self.assertEqual(selected, ("en-US", en_entry, "subtitles"))

    def test_choose_subtitle_prefers_manual_english_over_auto(self):
        manual_entry = {"ext": "vtt", "url": "https://example.test/manual.vtt"}
        auto_entry = {"ext": "srt", "url": "https://example.test/auto.srt"}
        selected = choose_subtitle(
            {
                "subtitles": {"en": [manual_entry]},
                "automatic_captions": {"en": [auto_entry]},
            },
            language="en",
        )

        self.assertEqual(selected, ("en", manual_entry, "subtitles"))

    def test_choose_subtitle_returns_none_when_target_language_missing(self):
        selected = choose_subtitle(
            {
                "subtitles": {"zh-CN": [{"ext": "vtt", "url": "https://example.test/zh.vtt"}]},
            },
            language="en",
        )

        self.assertIsNone(selected)


class TranscribeAudioTest(unittest.TestCase):
    def run_transcribe_with_language(self, language: str) -> list[str]:
        calls = []

        class FakeWhisperModel:
            def __init__(self, *args, **kwargs):
                pass

            def transcribe(self, *args, **kwargs):
                calls.append(kwargs["language"])
                segment = SimpleNamespace(text="hello", end=1)
                info = SimpleNamespace(duration=1)
                return [segment], info

        fake_module = types.SimpleNamespace(WhisperModel=FakeWhisperModel)
        with TemporaryDirectory() as directory, patch.dict(
            sys.modules,
            {"faster_whisper": fake_module},
        ):
            audio_path = Path(directory) / "audio.m4a"
            audio_path.write_text("fake", encoding="utf-8")
            transcribe_audio(
                audio_path,
                "small",
                "cpu",
                "int8",
                language=language,
            )

        return calls

    def test_transcribe_audio_passes_chinese_language(self):
        self.assertEqual(self.run_transcribe_with_language("zh"), ["zh"])

    def test_transcribe_audio_passes_english_language(self):
        self.assertEqual(self.run_transcribe_with_language("en"), ["en"])


class SubtitleParserTest(unittest.TestCase):
    def test_parse_vtt_or_srt_removes_metadata_timing_tags_and_duplicates(self):
        text = """WEBVTT

STYLE
::cue { color: white }

1
00:00:01.000 --> 00:00:02.000
<c>你好&nbsp;世界</c>

2
00:00:03,000 --> 00:00:04,000
你好&nbsp;世界

3
00:00:05,000 --> 00:00:06,000
第二行
"""

        self.assertEqual(parse_vtt_or_srt(text), "你好 世界\n第二行\n")

    def test_parse_vtt_or_srt_keeps_single_word_english_text(self):
        text = """WEBVTT

cue-1
00:00:01.000 --> 00:00:02.000
Hello

2
00:00:03.000 --> 00:00:04.000
world
"""

        self.assertEqual(parse_vtt_or_srt(text), "Hello\nworld\n")

    def test_parse_ass_uses_format_text_field_and_cleans_override_tags(self):
        text = """[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:01.00,0:00:02.00,Default,,0,0,0,,{\\pos(10,10)}第一行\\N第二行
"""

        self.assertEqual(parse_ass(text), "第一行\n第二行\n")

    def test_parse_json_subtitle_handles_youtube_events(self):
        text = json.dumps(
            {
                "events": [
                    {"segs": [{"utf8": "你好"}, {"utf8": "，世界"}]},
                    {"segs": [{"utf8": "第二行"}]},
                ]
            },
            ensure_ascii=False,
        )

        self.assertEqual(parse_json_subtitle(text), "你好，世界\n第二行\n")

    def test_parse_json_subtitle_handles_bilibili_body(self):
        text = json.dumps(
            {
                "body": [
                    {"content": "第一句"},
                    {"text": "第二句"},
                ]
            },
            ensure_ascii=False,
        )

        self.assertEqual(parse_json_subtitle(text), "第一句\n第二句\n")

    def test_parse_json_subtitle_walks_nested_text_fields(self):
        text = json.dumps(
            {
                "nested": [
                    {"payload": {"text": "嵌套文本"}},
                    {"payload": {"content": "更多文本"}},
                ]
            },
            ensure_ascii=False,
        )

        self.assertEqual(parse_json_subtitle(text), "嵌套文本\n更多文本\n")


class ExistingSubtitleExtractionTest(unittest.TestCase):
    @patch("extract_subtitle.download_subtitle")
    def test_existing_subtitle_uses_output_directory_temp_file(self, download_subtitle):
        with TemporaryDirectory() as directory:
            output_dir = Path(directory) / "custom-output"
            output_path = output_dir / "视频.BV123.txt"

            def write_subtitle(_entry, target):
                target.write_text("WEBVTT\n\n00:00:01.000 --> 00:00:02.000\n你好\n", encoding="utf-8")

            download_subtitle.side_effect = write_subtitle

            result = extract_existing_subtitle(
                {
                    "subtitles": {
                        "zh-CN": [
                            {
                                "ext": "vtt",
                                "url": "https://example.test/subtitle.vtt",
                            }
                        ]
                    }
                },
                "视频",
                "BV123",
                output_path,
            )

            self.assertEqual(result, output_path)
            self.assertEqual(output_path.read_text(encoding="utf-8"), "你好\n")
            self.assertFalse(list(output_dir.glob("subtitle-*")))


class FilenameAndErrorFormatTest(unittest.TestCase):
    def test_build_output_path_uses_title_id_and_custom_output_dir(self):
        with TemporaryDirectory() as directory:
            output_dir = Path(directory) / "custom-output"
            title, video_id, output_path = build_output_path(
                {"title": "A/B 视频", "id": "BV:123"},
                output_dir,
            )

            self.assertEqual(title, "A_B 视频")
            self.assertEqual(video_id, "BV_123")
            self.assertEqual(output_path, output_dir / "A_B 视频.BV_123.txt")
            self.assertTrue(output_dir.is_dir())

    def test_sanitize_filename_replaces_invalid_characters_and_trims(self):
        self.assertEqual(
            sanitize_filename('  A/B:C*D?E"F<G>H|.  '),
            "A_B_C_D_E_F_G_H_",
        )
        self.assertEqual(sanitize_filename("   ...   "), "video")
        self.assertEqual(len(sanitize_filename("字" * 130)), 120)

    def test_format_download_error_for_bilibili_412(self):
        message = format_download_error(
            "https://www.bilibili.com/video/BV123",
            RuntimeError("HTTP Error 412: Precondition Failed"),
            "fallback",
        )

        self.assertIn("Bilibili 获取失败", message)
        self.assertIn("cookies.txt", message)
        self.assertIn("HTTP Error 412", message)

    def test_format_download_error_for_browser_cookie_database(self):
        message = format_download_error(
            "https://example.test/video",
            RuntimeError("ERROR: could not copy Chrome cookie database"),
            "fallback",
            cookies_from_browser="chrome",
        )

        self.assertIn("读取 Chrome Cookie 失败", message)
        self.assertIn("Cookie 数据库被占用", message)
        self.assertIn("改用 cookies.txt 文件方式", message)

    def test_format_download_error_for_browser_cookie_dpapi(self):
        message = format_download_error(
            "https://example.test/video",
            RuntimeError("ERROR: failed to decrypt with DPAPI"),
            "fallback",
            cookies_from_browser="edge",
        )

        self.assertIn("读取 Edge Cookie 失败", message)
        self.assertIn("浏览器 Cookie 解密失败", message)
        self.assertIn("尝试 Firefox Cookie", message)

    def test_format_download_error_uses_fallback_for_generic_errors(self):
        message = format_download_error(
            "https://example.test/video",
            RuntimeError("line1\nline2"),
            "无法获取视频信息",
        )

        self.assertEqual(message, "无法获取视频信息\n详情：line1\nline2")


class YtDlpExecutableTest(unittest.TestCase):
    @patch("extract_subtitle.subprocess.run")
    def test_get_info_uses_explicit_yt_dlp_executable(self, run):
        with TemporaryDirectory() as directory:
            yt_dlp_path = Path(directory) / "yt-dlp.exe"
            ffmpeg_path = Path(directory) / "ffmpeg.exe"
            yt_dlp_path.write_text("fake", encoding="utf-8")
            ffmpeg_path.write_text("fake", encoding="utf-8")
            run.return_value = Mock(returncode=0, stdout='{"id": "BV123", "title": "标题"}', stderr="")

            info = get_info(
                "https://example.test/video",
                cookies="cookies.txt",
                ffmpeg_path=str(ffmpeg_path),
                yt_dlp_path=str(yt_dlp_path),
            )

        self.assertEqual(info["id"], "BV123")
        command = run.call_args.args[0]
        self.assertEqual(command[0], str(yt_dlp_path))
        self.assertIn("--dump-single-json", command)
        self.assertIn("--cookies", command)
        self.assertIn("cookies.txt", command)
        self.assertIn("--ffmpeg-location", command)
        self.assertIn(str(ffmpeg_path), command)

    @patch("extract_subtitle.subprocess.run")
    def test_get_info_uses_python_api_without_explicit_executable(self, run):
        with patch("extract_subtitle.yt_dlp.YoutubeDL") as ytdl:
            ytdl.return_value.__enter__.return_value.extract_info.return_value = {"id": "api"}

            info = get_info("https://example.test/video", cookies=None)

        self.assertEqual(info, {"id": "api"})
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
