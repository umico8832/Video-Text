import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from advanced_settings_dialog import AdvancedSettingsDialog
from video_text_gui import MainWindow


class GuiSmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def tearDown(self):
        self.app.processEvents()

    def test_main_window_constructs_core_controls(self):
        window = MainWindow(auto_check=False)
        try:
            self.assertEqual(window.windowTitle(), "视频字幕提取")
            self.assertTrue(hasattr(window, "url_input"))
            self.assertTrue(hasattr(window, "model_combo"))
            self.assertTrue(hasattr(window, "start_button"))
            self.assertTrue(hasattr(window, "log_view"))
            self.assertGreater(window.model_combo.count(), 0)
        finally:
            window.close()

    def test_advanced_settings_dialog_constructs_tabs(self):
        window = MainWindow(auto_check=False)
        dialog = AdvancedSettingsDialog(window, auto_detect=False)
        try:
            self.assertEqual(dialog.windowTitle(), "高级设置")
            self.assertEqual(dialog.tabs.count(), 3)
            self.assertTrue(hasattr(dialog, "advanced_model_combo"))
            self.assertTrue(hasattr(dialog, "advanced_cookie_info_body"))
            self.assertTrue(hasattr(dialog, "ffmpeg_card"))
        finally:
            dialog.close()
            window.close()


if __name__ == "__main__":
    unittest.main()
