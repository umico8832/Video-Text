import unittest

from gui_status_utils import status_from_log


class GuiStatusUtilsTest(unittest.TestCase):
    def test_status_from_environment_log(self):
        self.assertEqual(status_from_log("环境检查线程已启动"), "环境检查中")
        self.assertEqual(status_from_log("环境已就绪"), "准备就绪")

    def test_status_from_subtitle_log(self):
        self.assertEqual(status_from_log("正在查找视频自带中文字幕..."), "正在查找已有中文字幕")
        self.assertEqual(status_from_log("已找到视频自带英文字幕：人工字幕 en / vtt"), "正在下载字幕")

    def test_status_from_transcribe_log(self):
        self.assertEqual(status_from_log("正在识别音频内容..."), "正在语音识别")
        self.assertEqual(status_from_log("字幕文本已保存到：out.txt"), "正在保存结果")

    def test_status_from_unknown_log(self):
        self.assertIsNone(status_from_log("普通日志"))


if __name__ == "__main__":
    unittest.main()
