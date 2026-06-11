import unittest

from gui_cookie_utils import build_cookie_request, cookie_mode_label, selected_cookie_browser


class FakeCombo:
    def __init__(self, data=None, index=0):
        self.data = data
        self.index = index

    def currentData(self):
        return self.data

    def currentIndex(self):
        return self.index


class GuiCookieUtilsTest(unittest.TestCase):
    def test_selected_cookie_browser_prefers_combo_data(self):
        self.assertEqual(
            selected_cookie_browser(FakeCombo("Edge", index=0), ("chrome", "edge")),
            "edge",
        )

    def test_selected_cookie_browser_uses_index_fallback(self):
        self.assertEqual(
            selected_cookie_browser(FakeCombo(None, index=1), ("chrome", "edge")),
            "edge",
        )

    def test_selected_cookie_browser_falls_back_to_chrome(self):
        self.assertEqual(
            selected_cookie_browser(FakeCombo(None, index=99), ("chrome", "edge")),
            "chrome",
        )

    def test_cookie_mode_label_uses_known_label_and_fallbacks(self):
        modes = (
            {"name": "none", "label": "不使用 Cookies"},
            {"name": "file", "label": "使用 cookies.txt 文件"},
        )

        self.assertEqual(cookie_mode_label(modes, "file"), "使用 cookies.txt 文件")
        self.assertEqual(cookie_mode_label(modes, "browser"), "browser")
        self.assertEqual(cookie_mode_label(modes, None), "未知")

    def test_build_cookie_request_for_browser_mode(self):
        request = build_cookie_request("browser", "ignored.txt", "edge")

        self.assertEqual(request.cookies, "")
        self.assertEqual(request.cookies_from_browser, "edge")
        self.assertEqual(request.log_message, "正在尝试从浏览器 Edge 读取 Cookies...")

    def test_build_cookie_request_for_file_mode(self):
        request = build_cookie_request("file", "C:/temp/cookies.txt", "chrome")

        self.assertEqual(request.cookies, "C:/temp/cookies.txt")
        self.assertIsNone(request.cookies_from_browser)
        self.assertEqual(request.log_message, "已选择 cookies.txt 文件：cookies.txt，本次请求将使用该文件。")

    def test_build_cookie_request_for_empty_file_mode(self):
        request = build_cookie_request("file", "", "chrome")

        self.assertEqual(request.cookies, "")
        self.assertIsNone(request.cookies_from_browser)
        self.assertEqual(request.log_message, "已选择 cookies.txt 文件模式，但尚未填写文件路径。")

    def test_build_cookie_request_for_disabled_mode(self):
        request = build_cookie_request("none", "ignored.txt", "chrome")

        self.assertEqual(request.cookies, "")
        self.assertIsNone(request.cookies_from_browser)
        self.assertEqual(request.log_message, "未启用 Cookies，本次请求不会使用登录态。")


if __name__ == "__main__":
    unittest.main()
