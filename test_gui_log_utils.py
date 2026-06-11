import unittest

from gui_log_utils import clean_log_text, failure_summary


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


if __name__ == "__main__":
    unittest.main()
