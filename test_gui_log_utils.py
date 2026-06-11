import unittest

from gui_log_utils import clean_log_text, failure_summary, parse_failure_log


class GuiLogUtilsTest(unittest.TestCase):
    def test_clean_log_text_removes_ansi_sequences(self):
        self.assertEqual(clean_log_text("\x1b[31m失败\x1b[0m"), "失败")

    def test_failure_summary_uses_first_non_empty_line(self):
        self.assertEqual(failure_summary("\n普通错误。\n详情：更多"), "普通错误")

    def test_failure_summary_compacts_known_cookie_errors(self):
        self.assertEqual(
            failure_summary("读取 Chrome Cookie 失败，Cookie 未被使用。\n详情：x"),
            "读取 Chrome Cookie 失败",
        )

    def test_parse_failure_log_extracts_reason_suggestions_and_details(self):
        parsed = parse_failure_log(
            "\x1b[31m下载失败\x1b[0m\n\n"
            "建议：\n"
            "1. 检查网络\n"
            "2. 更新 yt-dlp\n"
            "详情：HTTP Error 412\n"
            "trace line"
        )

        self.assertEqual(parsed.reason, "下载失败")
        self.assertEqual(parsed.suggestions, ["1. 检查网络", "2. 更新 yt-dlp"])
        self.assertEqual(parsed.details, ["HTTP Error 412", "trace line"])

    def test_parse_failure_log_falls_back_for_empty_message(self):
        parsed = parse_failure_log("")

        self.assertEqual(parsed.reason, "未知错误")
        self.assertEqual(parsed.suggestions, [])
        self.assertEqual(parsed.details, [])


if __name__ == "__main__":
    unittest.main()
