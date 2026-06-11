import unittest

from gui_status_utils import FAILED_COLOR, NEUTRAL_COLOR, READY_COLOR, status_badge_state, status_from_log


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

    def test_status_badge_state_prefers_ready_when_not_failed(self):
        self.assertEqual(
            status_badge_state("环境状态：已就绪", "当前状态：准备就绪"),
            ("已就绪", READY_COLOR),
        )

    def test_status_badge_state_marks_failure(self):
        self.assertEqual(
            status_badge_state("环境状态：环境未就绪", "当前状态：准备就绪"),
            ("环境未就绪", FAILED_COLOR),
        )
        self.assertEqual(
            status_badge_state("环境状态：未检查", "当前状态：提取失败：网络错误"),
            ("提取失败：网络错误", FAILED_COLOR),
        )

    def test_status_badge_state_uses_current_status_when_env_unchecked(self):
        self.assertEqual(
            status_badge_state("环境状态：未检查", "当前状态：正在获取视频信息"),
            ("正在获取视频信息", NEUTRAL_COLOR),
        )


if __name__ == "__main__":
    unittest.main()
