import unittest

from gui_cookie_utils import selected_cookie_browser


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


if __name__ == "__main__":
    unittest.main()
