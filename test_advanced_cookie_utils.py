from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from advanced_cookie_utils import (
    cookie_file_status,
    cookie_option_description,
    cookie_option_frame_style,
    cookie_option_radio_style,
)


class AdvancedCookieUtilsTest(unittest.TestCase):
    def test_cookie_option_description_falls_back_to_none(self):
        self.assertIn("不会读取浏览器 Cookie", cookie_option_description("none"))
        self.assertEqual(cookie_option_description("unknown"), cookie_option_description("none"))

    def test_cookie_option_styles_reflect_selection(self):
        self.assertIn("#f5f9ff", cookie_option_frame_style(True))
        self.assertIn("#ffffff", cookie_option_frame_style(False))
        self.assertIn("#1d4ed8", cookie_option_radio_style(True))
        self.assertIn("#172033", cookie_option_radio_style(False))

    def test_cookie_file_status_modes(self):
        self.assertIn("不会向下载流程传递", cookie_file_status("none", ""))
        self.assertIn("Chrome", cookie_file_status("browser", "", "chrome"))
        self.assertIn("请选择 cookies.txt", cookie_file_status("file", ""))

    def test_cookie_file_status_for_existing_and_missing_file(self):
        with TemporaryDirectory() as directory:
            cookies_file = Path(directory) / "cookies.txt"
            cookies_file.write_text("# Netscape", encoding="utf-8")

            self.assertIn("将使用所选", cookie_file_status("file", str(cookies_file)))
            self.assertIn("当前路径不存在", cookie_file_status("file", str(Path(directory) / "missing.txt")))


if __name__ == "__main__":
    unittest.main()
